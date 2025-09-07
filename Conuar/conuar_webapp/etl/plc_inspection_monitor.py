#!/usr/bin/env python3
"""
Monitor de datos del PLC - Sistema Conuar

Este script monitorea un PLC para eventos de inspección y automáticamente:
1. Crea nuevas inspecciones en la base de datos
2. Actualiza contadores de la máquina de inspección
3. Registra eventos del PLC
4. Gestiona capturas de fotos de las cámaras

Sistema de inspección de combustible Conuar basado en Modubs
"""

import os
import sys
import django
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json

# Agregar proyecto Django al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

# Imports de Django
from django.conf import settings
from main.models import (
    Inspection, InspectionMachine, InspectionPhoto, 
    InspectionPlcEvent, SystemConfiguration
)

# Imports de Modbus
try:
    from pyModbusTCP.client import ModbusClient
except ImportError:
    print("Error: pyModbusTCP no está instalado. Ejecute: pip install pyModbusTCP")
    sys.exit(1)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('plc_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PlcInspectionMonitor:
    """Clase principal para monitorear PLC y gestionar inspecciones de combustible Conuar"""
    
    def __init__(self):
        self.config = SystemConfiguration.get_config()
        self.plc_client = None
        self.current_inspection = None
        self.is_running = False
        
        # Mapeo de registros PLC (ajustar según configuración del PLC)
        self.register_map = {
            'timestamp_plc': 1,
            'id_inspection': 2,
            'execution_id': 3,
            'control_point_id': 4,
            'execution_type': 5,
            'control_point_label': 6,
            'x_control_point': 7,
            'y_control_point': 8,
            'z_control_point': 9,
            'plate_angle': 10,
            'control_point_creator': 11,
            'program_creator': 12,
            'program_version': 13,
            'camera_id': 14,
            'filming_type': 15,
            'last_photo_request_timestamp': 16,
            'new_photos_available': 17,  # Flag indicando nuevas fotos
            'photo_count': 18,  # Número de nuevas fotos
        }
        
        # Mapeo de tipos de ejecución
        self.execution_type_map = {
            1: 'automatic',
            2: 'manual', 
            3: 'free'
        }
        
        # Mapeo de tipos de grabación de la cámara
        self.filming_type_map = {
            1: 'video',
            2: 'photo'
        }
    
    def connect_to_plc(self) -> bool:
        """Conectar al PLC usando configuración del sistema Conuar"""
        try:
            self.plc_client = ModbusClient(
                host=self.config.plc_ip,
                port=self.config.plc_port,
                auto_open=True,
                auto_close=False
            )
            
            if self.plc_client.open():
                logger.info(f"Conectado al PLC en {self.config.plc_ip}:{self.config.plc_port}")
                return True
            else:
                logger.error(f"Error al conectar al PLC en {self.config.plc_ip}:{self.config.plc_port}")
                return False
                
        except Exception as e:
            logger.error(f"Error conectando al PLC: {e}")
            return False
    
    def disconnect_from_plc(self):
        """Desconectar del PLC"""
        if self.plc_client:
            self.plc_client.close()
            logger.info("Desconectado del PLC")
    
    def read_plc_data(self) -> Optional[Dict]:
        """Leer todos los registros del PLC y retornar como diccionario"""
        try:
            if not self.plc_client or not self.plc_client.is_open():
                logger.error("Cliente PLC no conectado")
                return None
            
            data = {}
            
            # Leer todos los registros
            for field, register in self.register_map.items():
                result = self.plc_client.read_holding_registers(register, 1)
                if result:
                    data[field] = result[0]
                else:
                    logger.warning(f"Error al leer registro {register} para campo {field}")
                    data[field] = 0
            
            # Convertir campos fuertemente tipados
            data['timestamp_plc'] = datetime.now()  # Usar tiempo actual como timestamp del PLC
            data['execution_type'] = self.execution_type_map.get(data['execution_type'], 'automatic')
            data['filming_type'] = self.filming_type_map.get(data['filming_type'], 'photo')
            
            return data
            
        except Exception as e:
            logger.error(f"Error leyendo datos del PLC: {e}")
            return None
    
    def get_or_create_inspection(self, inspection_id: int) -> Inspection:
        """Obtener o crear inspección con el ID dado para el sistema Conuar"""
        try:
            inspection, created = Inspection.objects.get_or_create(
                id=inspection_id,
                defaults={
                    'title': f'Inspección de Combustible Conuar #{inspection_id}',
                    'description': f'Inspección automática generada por PLC del sistema Conuar #{inspection_id}',
                    'inspection_type': 'quality',
                    'status': 'in_progress',
                    'product_name': 'Combustible Industrial',
                    'product_code': f'COMB-{inspection_id:03d}',
                    'batch_number': f'LOTE-{datetime.now().strftime("%Y%m%d")}-{inspection_id:03d}',
                    'location': 'Planta de Inspección Conuar',
                    'inspector': None,  # Será establecido por el sistema
                }
            )
            
            if created:
                logger.info(f"Creada nueva inspección con ID: {inspection_id}")
            else:
                logger.info(f"Usando inspección existente con ID: {inspection_id}")
            
            return inspection
            
        except Exception as e:
            logger.error(f"Error obteniendo/creando inspección: {e}")
            raise
    
    def update_machine_stats(self, inspection: Inspection):
        """Actualizar estadísticas de la máquina de inspección Conuar"""
        try:
            machine = InspectionMachine.get_machine()
            machine.total_inspections += 1
            machine.inspections_today += 1
            machine.last_inspection = datetime.now()
            machine.current_inspection = inspection
            machine.save()
            
            logger.info(f"Estadísticas de máquina actualizadas - Total: {machine.total_inspections}, Hoy: {machine.inspections_today}")
            
        except Exception as e:
            logger.error(f"Error actualizando estadísticas de máquina: {e}")
    
    def create_plc_event(self, inspection: Inspection, plc_data: Dict) -> InspectionPlcEvent:
        """Crear un nuevo registro de evento PLC para el sistema Conuar"""
        try:
            # Convertir campos de string desde registros (asumiendo que están almacenados como códigos ASCII)
            def register_to_string(register_value: int) -> str:
                """Convertir valor de registro a string (simplificado)"""
                if register_value == 0:
                    return ""
                return f"REG_{register_value}"
            
            event = InspectionPlcEvent.objects.create(
                timestamp_plc=plc_data['timestamp_plc'],
                id_inspection=inspection,
                execution_id=register_to_string(plc_data['execution_id']),
                control_point_id=register_to_string(plc_data['control_point_id']),
                execution_type=plc_data['execution_type'],
                control_point_label=register_to_string(plc_data['control_point_label']),
                x_control_point=float(plc_data['x_control_point']),
                y_control_point=float(plc_data['y_control_point']),
                z_control_point=float(plc_data['z_control_point']),
                plate_angle=float(plc_data['plate_angle']),
                control_point_creator=register_to_string(plc_data['control_point_creator']),
                program_creator=register_to_string(plc_data['program_creator']),
                program_version=register_to_string(plc_data['program_version']),
                camera_id=register_to_string(plc_data['camera_id']),
                filming_type=plc_data['filming_type'],
                last_photo_request_timestamp=plc_data['timestamp_plc'] if plc_data['last_photo_request_timestamp'] else None,
            )
            
            logger.info(f"Creado evento PLC para inspección {inspection.id}, punto de control {event.control_point_id}")
            return event
            
        except Exception as e:
            logger.error(f"Error creando evento PLC: {e}")
            raise
    
    def check_for_new_photos(self, inspection: Inspection, photo_count: int) -> List[str]:
        """Verificar nuevas fotos y retornar lista de rutas de fotos para el sistema Conuar"""
        try:
            if photo_count <= 0:
                return []
            
            # Obtener ruta de carpeta de medios desde configuración
            media_path = self.config.media_storage_path
            if not media_path.startswith('/'):
                media_path = os.path.join(settings.MEDIA_ROOT, media_path)
            
            # Buscar nuevas fotos en la carpeta de medios
            photo_files = []
            if os.path.exists(media_path):
                for file in os.listdir(media_path):
                    if file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                        photo_files.append(file)
            
            # Retornar las fotos más recientes (hasta photo_count)
            photo_files.sort(key=lambda x: os.path.getmtime(os.path.join(media_path, x)), reverse=True)
            return photo_files[:photo_count]
            
        except Exception as e:
            logger.error(f"Error verificando nuevas fotos: {e}")
            return []
    
    def save_photos_to_inspection(self, inspection: Inspection, photo_files: List[str]):
        """Guardar archivos de fotos en la inspección del sistema Conuar"""
        try:
            if not photo_files:
                return
            
            media_path = self.config.media_storage_path
            if not media_path.startswith('/'):
                media_path = os.path.join(settings.MEDIA_ROOT, media_path)
            
            for photo_file in photo_files:
                # Crear ruta relativa para Django
                relative_path = f"inspection_photos/{photo_file}"
                full_path = os.path.join(media_path, photo_file)
                
                if os.path.exists(full_path):
                    # Crear registro de foto
                    photo = InspectionPhoto.objects.create(
                        inspection=inspection,
                        photo=relative_path,
                        caption=f"Foto automática Conuar - {photo_file}",
                        photo_type="automatic",
                    )
                    
                    logger.info(f"Guardada foto {photo_file} en inspección {inspection.id}")
                else:
                    logger.warning(f"Archivo de foto no encontrado: {full_path}")
                    
        except Exception as e:
            logger.error(f"Error guardando fotos en inspección: {e}")
    
    def process_plc_data(self, plc_data: Dict):
        """Procesar datos del PLC y actualizar base de datos del sistema Conuar"""
        try:
            # Obtener o crear inspección
            inspection_id = plc_data['id_inspection']
            if inspection_id <= 0:
                logger.warning("ID de inspección inválido del PLC")
                return
            
            inspection = self.get_or_create_inspection(inspection_id)
            
            # Actualizar estadísticas de máquina
            self.update_machine_stats(inspection)
            
            # Crear evento PLC
            event = self.create_plc_event(inspection, plc_data)
            
            # Verificar nuevas fotos
            photo_count = plc_data.get('photo_count', 0)
            if photo_count > 0:
                photo_files = self.check_for_new_photos(inspection, photo_count)
                if photo_files:
                    self.save_photos_to_inspection(inspection, photo_files)
            
            logger.info(f"Datos del PLC procesados exitosamente para inspección {inspection_id}")
            
        except Exception as e:
            logger.error(f"Error procesando datos del PLC: {e}")
    
    def run_monitoring_loop(self, duration_minutes: int = 60):
        """Ejecutar el bucle principal de monitoreo del sistema Conuar"""
        logger.info(f"Iniciando monitoreo PLC por {duration_minutes} minutos")
        
        if not self.connect_to_plc():
            logger.error("Error al conectar al PLC. Saliendo.")
            return
        
        self.is_running = True
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)
        
        try:
            while self.is_running and time.time() < end_time:
                # Leer datos del PLC
                plc_data = self.read_plc_data()
                
                if plc_data:
                    # Procesar los datos
                    self.process_plc_data(plc_data)
                    
                    # Registrar estado actual
                    logger.info(f"Datos PLC: Inspección={plc_data['id_inspection']}, "
                              f"Punto Control={plc_data['control_point_id']}, "
                              f"Tipo={plc_data['execution_type']}")
                else:
                    logger.warning("No se recibieron datos del PLC")
                
                # Esperar antes de la siguiente lectura
                time.sleep(1.0)  # Leer cada segundo
                
        except KeyboardInterrupt:
            logger.info("Monitoreo interrumpido por el usuario")
        except Exception as e:
            logger.error(f"Error en bucle de monitoreo: {e}")
        finally:
            self.is_running = False
            self.disconnect_from_plc()
            logger.info("Monitoreo PLC detenido")
    
    def stop_monitoring(self):
        """Detener el bucle de monitoreo"""
        self.is_running = False
        logger.info("Deteniendo monitoreo PLC...")

def main():
    """Función principal del sistema de monitoreo PLC Conuar"""
    print("Monitor de Inspección PLC - Sistema Conuar")
    print("==========================================")
    
    # Obtener configuración
    config = SystemConfiguration.get_config()
    print(f"IP PLC: {config.plc_ip}")
    print(f"Puerto PLC: {config.plc_port}")
    print(f"Ruta de Medios: {config.media_storage_path}")
    
    # Crear instancia del monitor
    monitor = PlcInspectionMonitor()
    
    try:
        # Ejecutar monitoreo por 60 minutos (ajustar según necesidad)
        monitor.run_monitoring_loop(duration_minutes=60)
    except Exception as e:
        logger.error(f"Error fatal: {e}")
    finally:
        monitor.stop_monitoring()

if __name__ == "__main__":
    main()
