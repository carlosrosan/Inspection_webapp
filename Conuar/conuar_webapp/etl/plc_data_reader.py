#!/usr/bin/env python3
"""
PLC Data Reader - Sistema Conuar

Este script se encarga únicamente de:
1. Conectar al PLC y leer datos
2. Almacenar los datos raw en la tabla main_plc_readings
3. No procesa ni crea inspecciones

Sistema de inspección de combustible Conuar basado en Modbus
"""

import os
import sys
import django
import time
import logging
from datetime import datetime
from typing import Dict, Optional

# Agregar proyecto Django al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

# Imports de Django
from main.models import PlcReading, SystemConfiguration

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
        logging.FileHandler('logs/plc_data_reader.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PlcDataReader:
    """Clase para leer datos del PLC y almacenarlos en main_plc_readings"""
    
    def __init__(self):
        self.config = SystemConfiguration.get_config()
        self.plc_client = None
        self.is_running = False
        
        # Mapeo de registros PLC (ajustar según configuración del PLC)
        self.register_map = {
            'timestamp_plc': 1,
            'id_inspection': 2,
            'execution_id': 3,
            'control_point_id': 4,
            'execution_type': 5,
            'control_point_label': 6,
            'tipo_combustible': 7,  # Nuevo campo para tipo de combustible
            'x_control_point': 8,
            'y_control_point': 9,
            'z_control_point': 10,
            'plate_angle': 11,
            'control_point_creator': 12,
            'program_creator': 13,
            'program_version': 14,
            'camera_id': 15,
            'filming_type': 16,
            'last_photo_request_timestamp': 17,
            'new_photos_available': 18,  # Flag indicando nuevas fotos
            'photo_count': 19,  # Número de nuevas fotos
            'message_type': 20,  # Tipo de mensaje (1=machine_routine_step, 2=system_message)
            'message_body': 21,  # Cuerpo del mensaje del sistema
            'fuel_rig_id': 22,   # ID del rig de combustible nuclear
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
            
            # Leer todos los registros numéricos
            for field, register in self.register_map.items():
                if field in ['message_body', 'fuel_rig_id']:
                    # Para campos de texto, leer múltiples registros y convertir a string
                    if field == 'message_body':
                        # Leer 10 registros para mensaje (máximo 20 caracteres)
                        result = self.plc_client.read_holding_registers(register, 10)
                        if result:
                            # Convertir registros a string (cada registro = 2 caracteres)
                            chars = []
                            for reg in result:
                                if reg > 0:
                                    chars.append(chr(reg >> 8))
                                    chars.append(chr(reg & 0xFF))
                            data[field] = ''.join(chars).strip('\x00')
                        else:
                            data[field] = ""
                    elif field == 'fuel_rig_id':
                        # Leer 5 registros para fuel_rig_id (máximo 10 caracteres)
                        result = self.plc_client.read_holding_registers(register, 5)
                        if result:
                            chars = []
                            for reg in result:
                                if reg > 0:
                                    chars.append(chr(reg >> 8))
                                    chars.append(chr(reg & 0xFF))
                            data[field] = ''.join(chars).strip('\x00')
                        else:
                            data[field] = ""
                else:
                    # Leer registros numéricos normales
                    result = self.plc_client.read_holding_registers(register, 1)
                    if result:
                        data[field] = result[0]
                    else:
                        logger.warning(f"Error al leer registro {register} para campo {field}")
                        data[field] = 0
            
            # Usar tiempo actual como timestamp del PLC
            data['timestamp_plc'] = datetime.now()
            
            return data
            
        except Exception as e:
            logger.error(f"Error leyendo datos del PLC: {e}")
            return None
    
    def save_plc_reading(self, plc_data: Dict) -> bool:
        """Guardar datos del PLC en la tabla main_plc_readings"""
        try:
            # Determinar el tipo de mensaje basado en el valor del registro
            message_type_value = plc_data.get('message_type', 1)
            message_type = 'machine_routine_step' if message_type_value == 1 else 'system_message'
            
            # Crear registro de lectura PLC
            reading = PlcReading.objects.create(
                timestamp_plc=plc_data['timestamp_plc'],
                id_inspection=plc_data['id_inspection'],
                execution_id=plc_data['execution_id'],
                control_point_id=plc_data['control_point_id'],
                execution_type=plc_data['execution_type'],
                control_point_label=plc_data['control_point_label'],
                tipo_combustible=plc_data['tipo_combustible'],
                x_control_point=float(plc_data['x_control_point']),
                y_control_point=float(plc_data['y_control_point']),
                z_control_point=float(plc_data['z_control_point']),
                plate_angle=float(plc_data['plate_angle']),
                control_point_creator=plc_data['control_point_creator'],
                program_creator=plc_data['program_creator'],
                program_version=plc_data['program_version'],
                camera_id=plc_data['camera_id'],
                filming_type=plc_data['filming_type'],
                last_photo_request_timestamp=plc_data['last_photo_request_timestamp'],
                new_photos_available=bool(plc_data['new_photos_available']),
                photo_count=plc_data['photo_count'],
                message_type=message_type,
                message_body=plc_data.get('message_body', ''),
                fuel_rig_id=plc_data.get('fuel_rig_id', ''),
                processed=False  # Marcar como no procesado
            )
            
            logger.info(f"Lectura PLC guardada - ID: {reading.id}, Inspección: {reading.id_inspection}, Tipo: {message_type}")
            return True
            
        except Exception as e:
            logger.error(f"Error guardando lectura PLC: {e}")
            return False
    
    def run_reading_loop(self, duration_minutes: int = 60):
        """Ejecutar el bucle principal de lectura del PLC"""
        logger.info(f"Iniciando lectura PLC por {duration_minutes} minutos")
        
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
                    # Guardar datos en la base de datos
                    if self.save_plc_reading(plc_data):
                        logger.info(f"Datos PLC leídos y guardados - Inspección: {plc_data['id_inspection']}, "
                                  f"Punto Control: {plc_data['control_point_id']}, "
                                  f"Tipo: {plc_data['execution_type']}")
                    else:
                        logger.error("Error guardando datos del PLC")
                else:
                    logger.warning("No se recibieron datos del PLC")
                
                # Esperar antes de la siguiente lectura
                time.sleep(1.0)  # Leer cada segundo
                
        except KeyboardInterrupt:
            logger.info("Lectura interrumpida por el usuario")
        except Exception as e:
            logger.error(f"Error en bucle de lectura: {e}")
        finally:
            self.is_running = False
            self.disconnect_from_plc()
            logger.info("Lectura PLC detenida")
    
    def stop_reading(self):
        """Detener el bucle de lectura"""
        self.is_running = False
        logger.info("Deteniendo lectura PLC...")

def main():
    """Función principal del sistema de lectura PLC Conuar"""
    print("Lector de Datos PLC - Sistema Conuar")
    print("====================================")
    
    # Obtener configuración
    config = SystemConfiguration.get_config()
    print(f"IP PLC: {config.plc_ip}")
    print(f"Puerto PLC: {config.plc_port}")
    
    # Crear instancia del lector
    reader = PlcDataReader()
    
    try:
        # Ejecutar lectura por 60 minutos (ajustar según necesidad)
        reader.run_reading_loop(duration_minutes=60)
    except Exception as e:
        logger.error(f"Error fatal: {e}")
    finally:
        reader.stop_reading()

if __name__ == "__main__":
    main()
