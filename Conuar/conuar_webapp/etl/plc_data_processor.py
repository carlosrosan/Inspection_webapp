#!/usr/bin/env python3
"""
PLC Data Processor - Sistema Conuar

Este script se encarga de:
1. Leer datos no procesados de la tabla main_plc_readings
2. Crear/actualizar inspecciones en main_inspection
3. Mapear fotos en main_inspectionphoto
4. Actualizar estado de máquina en main_inspectionmachine

Sistema de inspección de combustible Conuar basado en Modbus
"""

import os
import sys
import django
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from django.conf import settings

# Agregar proyecto Django al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

# Imports de Django
from main.models import (
    PlcReading, Inspection, InspectionMachine, InspectionPhoto, 
    InspectionPlcEvent, SystemConfiguration, User
)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('plc_data_processor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PlcDataProcessor:
    """Clase para procesar datos del PLC y actualizar tablas de inspección"""
    
    def __init__(self):
        self.config = SystemConfiguration.get_config()
        self.is_running = False
        
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
        
        # Mapeo de tipos de combustible
        self.tipo_combustible_map = {
            1: 'diesel',
            2: 'gasolina',
            3: 'kerosene',
            4: 'biodiesel',
            5: 'otros'
        }
    
    def get_unprocessed_readings(self, limit: int = 100) -> List[PlcReading]:
        """Obtener lecturas PLC no procesadas"""
        try:
            readings = PlcReading.objects.filter(
                processed=False
            ).order_by('timestamp_plc')[:limit]
            
            logger.info(f"Encontradas {len(readings)} lecturas no procesadas")
            return list(readings)
            
        except Exception as e:
            logger.error(f"Error obteniendo lecturas no procesadas: {e}")
            return []
    
    def get_or_create_inspection(self, inspection_id: int, reading: PlcReading = None) -> Inspection:
        """Obtener o crear inspección con el ID dado para el sistema Conuar"""
        try:
            inspection, created = Inspection.objects.get_or_create(
                id=inspection_id,
                defaults={
                    'title': f'Inspección de Combustible Conuar #{inspection_id}',
                    'description': f'Inspección automática generada por PLC del sistema Conuar #{inspection_id}',
                    'tipo_combustible': self.tipo_combustible_map.get(reading.tipo_combustible, 'diesel') if reading else 'diesel',
                    'status': 'in_progress',
                    'product_name': 'Combustible Industrial',
                    'product_code': f'COMB-{inspection_id:03d}',
                    'batch_number': f'LOTE-{datetime.now().strftime("%Y%m%d")}-{inspection_id:03d}',
                    'location': 'Planta de Inspección Conuar',
                    'inspector': self.get_default_inspector(),
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
    
    def get_default_inspector(self) -> Optional[User]:
        """Obtener inspector por defecto del sistema"""
        try:
            # Buscar un inspector del sistema
            inspector = User.objects.filter(is_inspector=True).first()
            if not inspector:
                # Si no hay inspectores, usar el primer usuario
                inspector = User.objects.first()
            return inspector
        except Exception as e:
            logger.warning(f"No se pudo obtener inspector por defecto: {e}")
            return None
    
    def update_machine_stats(self, inspection: Inspection):
        """Actualizar estadísticas de la máquina de inspección Conuar"""
        try:
            machine = InspectionMachine.get_machine()
            machine.total_inspections += 1
            machine.inspections_today += 1
            machine.last_inspection = datetime.now()
            machine.current_inspection = inspection
            machine.status = 'inspecting'
            machine.current_stage = 'analysis'
            machine.save()
            
            logger.info(f"Estadísticas de máquina actualizadas - Total: {machine.total_inspections}, Hoy: {machine.inspections_today}")
            
        except Exception as e:
            logger.error(f"Error actualizando estadísticas de máquina: {e}")
    
    def create_plc_event(self, inspection: Inspection, reading: PlcReading) -> InspectionPlcEvent:
        """Crear un nuevo registro de evento PLC para el sistema Conuar"""
        try:
            # Convertir campos de string desde registros (asumiendo que están almacenados como códigos ASCII)
            def register_to_string(register_value: int) -> str:
                """Convertir valor de registro a string (simplificado)"""
                if register_value == 0:
                    return ""
                return f"REG_{register_value}"
            
            event = InspectionPlcEvent.objects.create(
                timestamp_plc=reading.timestamp_plc,
                id_inspection=inspection,
                execution_id=register_to_string(reading.execution_id),
                control_point_id=register_to_string(reading.control_point_id),
                execution_type=self.execution_type_map.get(reading.execution_type, 'automatic'),
                control_point_label=register_to_string(reading.control_point_label),
                x_control_point=reading.x_control_point,
                y_control_point=reading.y_control_point,
                z_control_point=reading.z_control_point,
                plate_angle=reading.plate_angle,
                control_point_creator=register_to_string(reading.control_point_creator),
                program_creator=register_to_string(reading.program_creator),
                program_version=register_to_string(reading.program_version),
                camera_id=register_to_string(reading.camera_id),
                filming_type=self.filming_type_map.get(reading.filming_type, 'photo'),
                last_photo_request_timestamp=reading.timestamp_plc if reading.last_photo_request_timestamp else None,
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
    
    def process_reading(self, reading: PlcReading) -> bool:
        """Procesar una lectura individual del PLC"""
        try:
            # Validar datos básicos
            if reading.id_inspection <= 0:
                logger.warning(f"ID de inspección inválido en lectura {reading.id}: {reading.id_inspection}")
                reading.processing_error = "ID de inspección inválido"
                reading.save()
                return False
            
            # Obtener o crear inspección
            inspection = self.get_or_create_inspection(reading.id_inspection, reading)
            
            # Actualizar estadísticas de máquina
            self.update_machine_stats(inspection)
            
            # Crear evento PLC
            self.create_plc_event(inspection, reading)
            
            # Verificar nuevas fotos
            if reading.new_photos_available and reading.photo_count > 0:
                photo_files = self.check_for_new_photos(inspection, reading.photo_count)
                if photo_files:
                    self.save_photos_to_inspection(inspection, photo_files)
            
            # Marcar como procesado
            reading.processed = True
            reading.save()
            
            logger.info(f"Lectura {reading.id} procesada exitosamente para inspección {reading.id_inspection}")
            return True
            
        except Exception as e:
            logger.error(f"Error procesando lectura {reading.id}: {e}")
            reading.processing_error = str(e)
            reading.save()
            return False
    
    def process_all_unprocessed_readings(self, batch_size: int = 100):
        """Procesar todas las lecturas no procesadas"""
        try:
            readings = self.get_unprocessed_readings(limit=batch_size)
            
            if not readings:
                logger.info("No hay lecturas para procesar")
                return
            
            processed_count = 0
            error_count = 0
            
            for reading in readings:
                if self.process_reading(reading):
                    processed_count += 1
                else:
                    error_count += 1
            
            logger.info(f"Procesamiento completado - Exitosos: {processed_count}, Errores: {error_count}")
            
        except Exception as e:
            logger.error(f"Error en procesamiento por lotes: {e}")
    
    def run_processing_loop(self, interval_seconds: int = 30):
        """Ejecutar el bucle principal de procesamiento"""
        logger.info(f"Iniciando procesamiento cada {interval_seconds} segundos")
        
        self.is_running = True
        
        try:
            while self.is_running:
                # Procesar lecturas no procesadas
                self.process_all_unprocessed_readings()
                
                # Esperar antes del siguiente ciclo
                time.sleep(interval_seconds)
                
        except KeyboardInterrupt:
            logger.info("Procesamiento interrumpido por el usuario")
        except Exception as e:
            logger.error(f"Error en bucle de procesamiento: {e}")
        finally:
            self.is_running = False
            logger.info("Procesamiento detenido")
    
    def stop_processing(self):
        """Detener el bucle de procesamiento"""
        self.is_running = False
        logger.info("Deteniendo procesamiento...")

def main():
    """Función principal del sistema de procesamiento PLC Conuar"""
    print("Procesador de Datos PLC - Sistema Conuar")
    print("========================================")
    
    # Crear instancia del procesador
    processor = PlcDataProcessor()
    
    try:
        # Ejecutar procesamiento cada 30 segundos
        processor.run_processing_loop(interval_seconds=30)
    except Exception as e:
        logger.error(f"Error fatal: {e}")
    finally:
        processor.stop_processing()

if __name__ == "__main__":
    main()
