#!/usr/bin/env python3
"""
PLC Data Reader - Sistema Conuar

Este script se encarga de:
1. Monitorear archivo CSV con formato JSON cada 30 segundos
2. Detectar nuevas líneas desde la última lectura
3. Almacenar solo los datos nuevos en la tabla plc_data_raw
4. No procesa ni crea inspecciones

Sistema de inspección de combustible Conuar
"""

import os
import sys
import django
import time
import json
import logging
import hashlib
from datetime import datetime
from typing import Dict, Optional, List, Set
from pathlib import Path

# Check if Django is already configured (running within Django app)
# If not, set it up (running as standalone script)
try:
    # Try to access apps to see if Django is already set up
    django.apps.apps.check_apps_ready()
except Exception:
    # Django not set up yet - set it up now (standalone script mode)
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(r"C:\Users\Admin\Documents\Inspection_webapp\Conuar\conuar_webapp\logs\plc_data_reader.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class PlcDataReader:
    """Clase para leer datos de CSV con formato JSON y almacenarlos en plc_data_raw"""
    
    def __init__(self, csv_input_file: str = None):
        self.is_running = False
        
        # Default CSV file path if not provided
        if csv_input_file is None:
            self.csv_input_file = Path(r"C:\Users\Admin\Documents\Inspection_webapp\Conuar\conuar_webapp\etl\Conuar test NodeRed\plc_reads\plc_reads_nodered.csv")
        else:
            self.csv_input_file = Path(csv_input_file)
        
        # Track which lines have been processed using a hash set
        self.processed_hashes: Set[str] = set()
        
        # Load existing hashes from database to avoid reprocessing
        self._load_existing_hashes()
    
    def _load_existing_hashes(self):
        """Cargar hashes de registros ya existentes en la base de datos"""
        try:
            from django.db import connection
            
            with connection.cursor() as cursor:
                # Get hash of all existing json_data
                cursor.execute("SELECT MD5(json_data) as hash FROM plc_data_raw")
                rows = cursor.fetchall()
                
                for row in rows:
                    if row[0]:
                        self.processed_hashes.add(row[0])
                
                logger.info(f"Cargados {len(self.processed_hashes)} hashes de registros existentes")
                
        except Exception as e:
            logger.warning(f"No se pudieron cargar hashes existentes: {e}")
            # Continue anyway - will just check for duplicates differently
    
    def _get_line_hash(self, line: str) -> str:
        """Generar hash MD5 de una línea para detectar duplicados"""
        return hashlib.md5(line.encode('utf-8')).hexdigest()
    
    def check_csv_file(self) -> bool:
        """Verificar que el archivo CSV existe"""
        try:
            if self.csv_input_file.exists():
                logger.debug(f"Archivo CSV encontrado: {self.csv_input_file}")
                return True
            else:
                logger.error(f"Archivo CSV no encontrado: {self.csv_input_file}")
                return False
        except Exception as e:
            logger.error(f"Error verificando archivo CSV: {e}")
            return False
    
    def save_plc_data_raw(self, timestamp: str, json_data: str, line_hash: str) -> bool:
        """Guardar datos en la tabla plc_data_raw usando Django ORM"""
        try:
            from django.db import connection
            
            # Check if this exact data already exists (using hash)
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(*) FROM plc_data_raw 
                    WHERE MD5(json_data) = %s
                """, [line_hash])
                
                count = cursor.fetchone()[0]
                
                if count > 0:
                    logger.debug(f"Registro duplicado detectado, omitiendo...")
                    return False
                
                # Insert new record
                cursor.execute("""
                    INSERT INTO plc_data_raw (timestamp, json_data, created_at)
                    VALUES (%s, %s, NOW())
                """, [timestamp, json_data])
            
            # Add to processed hashes
            self.processed_hashes.add(line_hash)
            
            logger.info(f"[NEW] Dato guardado - Timestamp: {timestamp}")
            return True
            
        except Exception as e:
            logger.error(f"Error guardando datos: {e}")
            return False
    
    def read_new_lines(self) -> List[str]:
        """Leer solo las líneas nuevas del archivo CSV"""
        try:
            new_lines = []
            
            with open(self.csv_input_file, 'r', encoding='utf-8') as csvfile:
                for line in csvfile:
                    line = line.strip()
                    
                    if not line:
                        continue
                    
                    # Calculate hash
                    line_hash = self._get_line_hash(line)
                    
                    # Check if this line is new
                    if line_hash not in self.processed_hashes:
                        new_lines.append((line, line_hash))
            
            return new_lines
            
        except Exception as e:
            logger.error(f"Error leyendo archivo CSV: {e}")
            return []
    
    def process_new_data(self) -> Dict[str, int]:
        """Procesar solo datos nuevos del CSV"""
        if not self.check_csv_file():
            return {'new': 0, 'errors': 0}
        
        new_lines = self.read_new_lines()
        
        if not new_lines:
            logger.debug("No hay nuevas líneas para procesar")
            return {'new': 0, 'errors': 0}
        
        success_count = 0
        error_count = 0
        
        logger.info(f"Encontradas {len(new_lines)} nuevas líneas para procesar")
        
        for line, line_hash in new_lines:
            try:
                # Parse JSON
                json_obj = json.loads(line)
                
                # Extract timestamp
                timestamp = json_obj.get('datetime') or json_obj.get('timestamp') or datetime.now().isoformat()
                
                # Convert timestamp to MySQL datetime format
                if 'T' in timestamp and 'Z' in timestamp:
                    timestamp = timestamp.replace('T', ' ').replace('Z', '')
                
                # Save to database
                if self.save_plc_data_raw(timestamp, line, line_hash):
                    success_count += 1
                else:
                    # Already exists
                    pass
                    
            except json.JSONDecodeError as e:
                error_count += 1
                logger.error(f"Error de parseo JSON: {e}")
            except Exception as e:
                error_count += 1
                logger.error(f"Error procesando línea: {e}")
        
        if success_count > 0:
            logger.info(f"[SUCCESS] {success_count} nuevos registros guardados exitosamente")
        
        if error_count > 0:
            logger.warning(f"[ERROR] {error_count} errores durante el procesamiento")
        
        return {'new': success_count, 'errors': error_count}
    
    def monitor_file(self, interval_seconds: int = 30):
        """Monitorear archivo CSV cada N segundos y procesar datos nuevos"""
        logger.info("=" * 80)
        logger.info("Iniciando monitor de archivo CSV")
        logger.info(f"Archivo: {self.csv_input_file}")
        logger.info(f"Intervalo: {interval_seconds} segundos")
        logger.info("Presione Ctrl+C para detener...")
        logger.info("=" * 80)
        
        self.is_running = True
        cycle_count = 0
        
        try:
            while self.is_running:
                cycle_count += 1
                logger.info(f"[Ciclo {cycle_count}] Verificando archivo CSV...")
                
                result = self.process_new_data()
                
                if result['new'] > 0 or result['errors'] > 0:
                    logger.info(f"[Ciclo {cycle_count}] Nuevos: {result['new']}, Errores: {result['errors']}")
                
                # Wait before next check
                if self.is_running:
                    time.sleep(interval_seconds)
                
        except KeyboardInterrupt:
            logger.info("Monitor interrumpido por el usuario")
        except Exception as e:
            logger.error(f"Error en monitor: {e}")
        finally:
            self.is_running = False
            logger.info("Monitor detenido")
    
    def stop_monitoring(self):
        """Detener el monitor"""
        self.is_running = False
        logger.info("Deteniendo monitor...")


def load_csv_data_to_db(csv_file_path: str = None) -> dict:
    """
    Load CSV data into database - can be called from Django startup
    Returns a dictionary with results
    """
    try:
        # Use default path if not provided
        if csv_file_path is None:
            csv_file_path = r"C:\Users\Admin\Documents\Inspection_webapp\Conuar\conuar_webapp\etl\Conuar test NodeRed\plc_reads\plc_reads_nodered.csv"
        
        # Create reader instance
        reader = PlcDataReader(csv_input_file=str(csv_file_path))
        
        # Process new data
        logger.info(f"Cargando datos nuevos desde: {csv_file_path}")
        result = reader.process_new_data()
        
        return {
            'success': True,
            'new_records': result['new'],
            'errors': result['errors'],
            'message': f"{result['new']} nuevos registros cargados"
        }
    except Exception as e:
        error_msg = f"Error cargando datos CSV: {e}"
        logger.error(error_msg)
        return {
            'success': False,
            'new_records': 0,
            'errors': 1,
            'message': error_msg
        }


def start_background_monitor(interval_seconds: int = 30):
    """
    Iniciar monitor en background (para uso desde Django startup)
    """
    import threading
    
    def monitor_thread():
        try:
            csv_file = r"C:\Users\Admin\Documents\Inspection_webapp\Conuar\conuar_webapp\etl\Conuar test NodeRed\plc_reads\plc_reads_nodered.csv"
            reader = PlcDataReader(csv_input_file=csv_file)
            reader.monitor_file(interval_seconds=interval_seconds)
        except Exception as e:
            logger.error(f"Error en thread de monitor: {e}")
    
    thread = threading.Thread(target=monitor_thread, daemon=True, name="PLCDataReaderMonitor")
    thread.start()
    logger.info(f"Monitor de CSV iniciado en background (cada {interval_seconds}s)")
    
    return thread


def main():
    """Función principal del sistema de lectura de datos CSV Conuar"""
    print("=" * 80)
    print("Monitor de Datos CSV a MySQL - Sistema Conuar")
    print("=" * 80)
    print()
    
    # Get CSV file path
    csv_file = r"C:\Users\Admin\Documents\Inspection_webapp\Conuar\conuar_webapp\etl\Conuar test NodeRed\plc_reads\plc_reads_nodered.csv"
    
    print(f"Archivo CSV: {csv_file}")
    print()
    
    # Create reader instance
    reader = PlcDataReader(csv_input_file=str(csv_file))
    
    try:
        # Option selection
        print("Seleccione modo de operación:")
        print("1. Procesar datos nuevos una vez y salir")
        print("2. Monitorear archivo continuamente (cada 30 segundos)")
        
        try:
            choice = input("Opción (1 o 2): ").strip()
        except:
            choice = "2"  # Default to monitoring
        
        if choice == "1":
            # Process once
            result = reader.process_new_data()
            print(f"\nResultados:")
            print(f"  - Nuevos registros: {result['new']}")
            print(f"  - Errores: {result['errors']}")
        else:
            # Continuous monitoring
            reader.monitor_file(interval_seconds=30)
            
    except Exception as e:
        logger.error(f"Error fatal: {e}")
    finally:
        reader.stop_monitoring()


if __name__ == "__main__":
    main()
