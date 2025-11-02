#!/usr/bin/env python3
"""
PLC Data Reader - Sistema Conuar

Este script se encarga únicamente de:
1. Leer datos de un archivo CSV con formato JSON
2. Almacenar los datos raw en la tabla plc_data_raw
3. No procesa ni crea inspecciones

Sistema de inspección de combustible Conuar
"""

import os
import sys
import django
import time
import json
import logging
from datetime import datetime
from typing import Dict, Optional
from pathlib import Path

# Agregar proyecto Django al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

# Imports de Django
from main.models import SystemConfiguration

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
    """Clase para leer datos de CSV con formato JSON y almacenarlos en plc_data_raw"""
    
    def __init__(self, csv_input_file: str = None):
        self.is_running = False
        
        # Default CSV file path if not provided - using absolute path
        if csv_input_file is None:
            self.csv_input_file = Path(r"C:\Users\Admin\Documents\Inspection_webapp\Conuar\conuar_webapp\etl\Conuar test NodeRed\plc_reads\plc_reads_nodered.csv")
        else:
            self.csv_input_file = Path(csv_input_file)
    
    def check_csv_file(self) -> bool:
        """Verificar que el archivo CSV existe"""
        try:
            if self.csv_input_file.exists():
                logger.info(f"Archivo CSV encontrado: {self.csv_input_file}")
                return True
            else:
                logger.error(f"Archivo CSV no encontrado: {self.csv_input_file}")
                return False
        except Exception as e:
            logger.error(f"Error verificando archivo CSV: {e}")
            return False
    
    def save_plc_data_raw(self, timestamp: str, json_data: str) -> bool:
        """Guardar datos en la tabla plc_data_raw usando Django ORM"""
        try:
            from django.db import connection
            
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO plc_data_raw (timestamp, json_data, created_at)
                    VALUES (%s, %s, NOW())
                """, [timestamp, json_data])
            
            logger.info(f"Datos guardados - Timestamp: {timestamp}, Tamaño: {len(json_data)} bytes")
            return True
            
        except Exception as e:
            logger.error(f"Error guardando datos: {e}")
            return False
    
    def process_csv_file(self):
        """Procesar archivo CSV y guardar cada línea JSON en la base de datos"""
        logger.info(f"Iniciando procesamiento de archivo CSV: {self.csv_input_file}")
        
        if not self.check_csv_file():
            logger.error("Archivo CSV no encontrado. Saliendo.")
            return
        
        self.is_running = True
        row_count = 0
        success_count = 0
        error_count = 0
        start_time = time.time()
        
        try:
            with open(self.csv_input_file, 'r', encoding='utf-8') as csvfile:
                for line_num, line in enumerate(csvfile, 1):
                    line = line.strip()
                    
                    if not line:
                        continue
                    
                    try:
                        # Parsear JSON desde la línea
                        json_obj = json.loads(line)
                        
                        # Extraer timestamp (intentar diferentes nombres de campo)
                        timestamp = json_obj.get('datetime') or json_obj.get('timestamp') or datetime.now().isoformat()
                        
                        # Convertir timestamp a formato MySQL datetime si es necesario
                        if 'T' in timestamp and 'Z' in timestamp:
                            # Formato ISO como "2025-11-02T16:33:20.607Z"
                            timestamp = timestamp.replace('T', ' ').replace('Z', '')
                        
                        # Guardar en la base de datos
                        if self.save_plc_data_raw(timestamp, line):
                            success_count += 1
                            if success_count % 10 == 0:  # Log cada 10 registros
                                logger.info(f"Progreso: {success_count} registros guardados...")
                        else:
                            error_count += 1
                            logger.error(f"Error guardando línea {line_num}")
                        
                        row_count += 1
                        
                    except json.JSONDecodeError as e:
                        error_count += 1
                        logger.error(f"Error de parseo JSON en línea {line_num}: {e}")
                    except Exception as e:
                        error_count += 1
                        logger.error(f"Error procesando línea {line_num}: {e}")
                
        except KeyboardInterrupt:
            logger.info("Procesamiento interrumpido por el usuario")
        except Exception as e:
            logger.error(f"Error leyendo archivo CSV: {e}")
        finally:
            self.is_running = False
            elapsed_time = time.time() - start_time
            
            logger.info("="*60)
            logger.info("Resumen de procesamiento:")
            logger.info(f"Total de líneas procesadas: {row_count}")
            logger.info(f"Guardados exitosamente: {success_count}")
            logger.info(f"Errores: {error_count}")
            logger.info(f"Tiempo transcurrido: {elapsed_time:.1f} segundos")
            logger.info("="*60)
    
    def stop_processing(self):
        """Detener el procesamiento"""
        self.is_running = False
        logger.info("Deteniendo procesamiento de CSV...")

def main():
    """Función principal del sistema de lectura de datos CSV Conuar"""
    print("Procesador de Datos CSV a MySQL - Sistema Conuar")
    print("================================================")
    
    # Obtener ruta del archivo CSV - using absolute path
    csv_file = r"C:\Users\Admin\Documents\Inspection_webapp\Conuar\conuar_webapp\etl\Conuar test NodeRed\plc_reads\plc_reads_nodered.csv"
    
    print(f"Archivo CSV: {csv_file}")
    
    # Crear instancia del lector
    reader = PlcDataReader(csv_input_file=str(csv_file))
    
    try:
        # Procesar archivo CSV
        reader.process_csv_file()
    except Exception as e:
        logger.error(f"Error fatal: {e}")
    finally:
        reader.stop_processing()

if __name__ == "__main__":
    main()
