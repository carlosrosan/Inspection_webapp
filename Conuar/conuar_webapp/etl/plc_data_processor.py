#!/usr/bin/env python3
"""
PLC Data Processor - Sistema Conuar

Este script se encarga de:
1. Leer datos no procesados de la tabla plc_data_raw
2. Extraer InSight_3800-AcquisitionID del JSON
3. Buscar foto correspondiente en directorios OK/NOK
4. Crear inspección con estado basado en ubicación de foto
5. Vincular foto a la inspección

Sistema de inspección de combustible Conuar
"""

import os
import sys
import django
import time
import logging
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
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

# Imports de Django
from main.models import PlcDataRaw, Inspection, InspectionPhoto, InspectionMachine, User
from django.core.files import File
from django.conf import settings

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(r'C:\Users\Admin\Documents\Inspection_webapp\Conuar\conuar_webapp\logs\plc_data_processor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class PlcDataProcessor:
    """Clase para procesar datos del PLC y crear inspecciones basadas en fotos"""
    
    def __init__(self):
        self.is_running = False
        
        # Rutas de directorios de fotos
        self.base_photo_path = Path(r"C:\Users\Admin\Documents\Inspection_webapp\Conuar\conuar_webapp\media\inspection_photos")
        self.ok_photo_path = self.base_photo_path / "OK"
        self.nok_photo_path = self.base_photo_path / "NOK"
        
        # Track processed photos to avoid reprocessing
        self.processed_photos: set = set()
        
        # Load existing processed photos from database
        self._load_processed_photos()
        
        # Verificar que los directorios existen
        if not self.ok_photo_path.exists():
            logger.warning(f"Directorio OK no existe: {self.ok_photo_path}")
        if not self.nok_photo_path.exists():
            logger.warning(f"Directorio NOK no existe: {self.nok_photo_path}")
    
    def _load_processed_photos(self):
        """Cargar fotos ya procesadas desde la base de datos"""
        try:
            # Get all photo filenames that have been linked to inspections
            photo_records = InspectionPhoto.objects.all().values_list('photo', flat=True)
            
            for photo_path in photo_records:
                # Extract just the filename from paths like 'inspection_photos/OK/1.bmp'
                if photo_path:
                    filename = Path(photo_path).name
                    self.processed_photos.add(filename)
            
            logger.info(f"Cargadas {len(self.processed_photos)} fotos ya procesadas")
            
        except Exception as e:
            logger.warning(f"No se pudieron cargar fotos procesadas: {e}")
    
    def get_new_photos(self) -> List[Tuple[Path, str]]:
        """
        Obtener lista de fotos nuevas (no procesadas) de directorios OK/NOK
        
        Returns:
            List of tuples: (photo_path, status) where status is 'OK' or 'NOK'
        """
        new_photos = []
        
        try:
            # Check OK directory
            if self.ok_photo_path.exists():
                for photo_file in self.ok_photo_path.iterdir():
                    if photo_file.is_file() and photo_file.suffix.lower() in ['.bmp', '.jpg', '.jpeg', '.png']:
                        if photo_file.name not in self.processed_photos:
                            new_photos.append((photo_file, 'OK'))
            
            # Check NOK directory
            if self.nok_photo_path.exists():
                for photo_file in self.nok_photo_path.iterdir():
                    if photo_file.is_file() and photo_file.suffix.lower() in ['.bmp', '.jpg', '.jpeg', '.png']:
                        if photo_file.name not in self.processed_photos:
                            new_photos.append((photo_file, 'NOK'))
            
            if new_photos:
                logger.info(f"Encontradas {len(new_photos)} fotos nuevas para procesar")
            
            return new_photos
            
        except Exception as e:
            logger.error(f"Error obteniendo fotos nuevas: {e}")
            return []
    
    def get_unprocessed_raw_data(self, limit: int = 100) -> List[PlcDataRaw]:
        """Obtener datos raw no procesados de plc_data_raw"""
        try:
            raw_data = PlcDataRaw.objects.filter(
                processed=False
            ).order_by('timestamp')[:limit]
            
            logger.info(f"Encontrados {len(raw_data)} registros raw no procesados")
            return list(raw_data)
            
        except Exception as e:
            logger.error(f"Error obteniendo datos raw no procesados: {e}")
            return []
    
    def extract_acquisition_id(self, json_data: str) -> Optional[str]:
        """Extraer InSight_3800-AcquisitionID del JSON"""
        try:
            data = json.loads(json_data)
            
            # El campo puede tener o no espacio al inicio
            acquisition_id = data.get(' InSight_3800-AcquisitionID') or data.get('InSight_3800-AcquisitionID')
            
            if acquisition_id:
                # Convertir a string y limpiar
                acquisition_id = str(acquisition_id).strip()
                logger.debug(f"Acquisition ID extraído: {acquisition_id}")
                return acquisition_id
            else:
                logger.warning("Campo InSight_3800-AcquisitionID no encontrado en JSON")
                return None
                
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Error extrayendo acquisition ID: {e}")
            return None
    
    def find_photo_by_id(self, acquisition_id: str) -> Optional[Tuple[Path, str]]:
        """
        Buscar foto por ID en directorios OK/NOK
        
        Returns:
            Tuple[Path, str]: (ruta_completa_foto, estado) donde estado es 'OK' o 'NOK'
            None si no se encuentra la foto
        """
        try:
            # Buscar con extensiones comunes
            extensions = ['.bmp', '.jpg', '.jpeg', '.png']
            
            # Buscar en directorio OK
            for ext in extensions:
                photo_name = f"{acquisition_id}{ext}"
                photo_path = self.ok_photo_path / photo_name
                
                if photo_path.exists():
                    logger.info(f"Foto encontrada en OK: {photo_path}")
                    return (photo_path, 'OK')
            
            # Buscar en directorio NOK
            for ext in extensions:
                photo_name = f"{acquisition_id}{ext}"
                photo_path = self.nok_photo_path / photo_name
                
                if photo_path.exists():
                    logger.info(f"Foto encontrada en NOK: {photo_path}")
                    return (photo_path, 'NOK')
            
            logger.warning(f"No se encontró foto para Acquisition ID: {acquisition_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error buscando foto para ID {acquisition_id}: {e}")
            return None
    
    def get_default_inspector(self) -> User:
        """Obtener inspector por defecto del sistema"""
        try:
            # Buscar usuario system_inspector
            inspector = User.objects.filter(username='system_inspector').first()
            
            if not inspector:
                # Si no existe, crear uno
                inspector = User.objects.create(
                    username='system_inspector',
                    first_name='Sistema',
                    last_name='Inspector',
                    email='system@conuar.com',
                    is_active=True,
                    is_staff=True,
                )
                logger.info("Creado usuario system_inspector")
            
            return inspector
            
        except Exception as e:
            logger.error(f"Error obteniendo inspector por defecto: {e}")
            # Devolver el primer usuario disponible
            return User.objects.first()
    
    def create_inspection_from_photo(
        self, 
        acquisition_id: str, 
        photo_path: Path, 
        photo_status: str,
        raw_data: PlcDataRaw
    ) -> Optional[Inspection]:
        """
        Crear inspección basada en la foto y su ubicación
        
        Args:
            acquisition_id: ID de adquisición de la cámara
            photo_path: Ruta completa de la foto
            photo_status: 'OK' o 'NOK'
            raw_data: Registro raw de donde provienen los datos
        
        Returns:
            Inspection object si se creó exitosamente, None en caso contrario
        """
        try:
            # Determinar el estado de inspección basado en ubicación de foto
            if photo_status == 'OK':
                inspection_status = 'approved'  # Pasa
                defecto_encontrado = False
                result_text = "Inspección APROBADA - Producto cumple con estándares de calidad"
            else:  # NOK
                inspection_status = 'rejected'  # No pasa
                defecto_encontrado = True
                result_text = "Inspección RECHAZADA - Defecto detectado por cámara InSight 3800"
            
            # Obtener inspector por defecto
            inspector = self.get_default_inspector()
            
            # Crear la inspección (usando acquisition_id como base para el ID único)
            # Nota: Usamos el acquisition_id directamente como ID si es numérico
            try:
                inspection_id = int(acquisition_id)
            except ValueError:
                # Si no es numérico, usar un hash o timestamp
                inspection_id = None  # Dejar que Django auto-incremente
            
            # Verificar si ya existe una inspección con este ID
            if inspection_id and Inspection.objects.filter(id=inspection_id).exists():
                logger.warning(f"Ya existe inspección con ID {inspection_id}, se creará con nuevo ID")
                inspection_id = None
            
            # Datos de la inspección
            inspection_data = {
                'title': f'Inspección Combustible Conuar - Foto {acquisition_id}',
                'description': f'Inspección automática generada desde datos PLC - Acquisition ID: {acquisition_id}',
                'tipo_combustible': 'uranio',  # Por defecto
                'status': inspection_status,
                'defecto_encontrado': defecto_encontrado,
                'product_name': 'Combustible Nuclear',
                'product_code': f'COMB-{acquisition_id}',
                'batch_number': f'LOTE-{datetime.now().strftime("%Y%m%d")}-{acquisition_id}',
                'serial_number': f'SN-{acquisition_id}',
                'location': 'Planta de Inspección Conuar - Cámara InSight 3800',
                'inspector': inspector,
                'inspection_date': raw_data.timestamp,
                'completed_date': datetime.now(),
                'result': result_text,
                'notes': f'Procesado automáticamente desde plc_data_raw ID: {raw_data.id}',
            }
            
            # Crear inspección
            if inspection_id:
                inspection_data['id'] = inspection_id
                inspection = Inspection.objects.create(**inspection_data)
            else:
                inspection = Inspection.objects.create(**inspection_data)
            
            logger.info(f"Inspección creada - ID: {inspection.id}, Estado: {inspection_status}, Foto: {photo_path.name}")
            
            return inspection
            
        except Exception as e:
            logger.error(f"Error creando inspección para acquisition ID {acquisition_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def link_photo_to_inspection(
        self, 
        inspection: Inspection, 
        photo_path: Path, 
        photo_status: str
    ) -> Optional[InspectionPhoto]:
        """
        Vincular foto existente a la inspección
        
        Args:
            inspection: Inspección a la que vincular la foto
            photo_path: Ruta completa de la foto
            photo_status: 'OK' o 'NOK'
        
        Returns:
            InspectionPhoto object si se vinculó exitosamente, None en caso contrario
        """
        try:
            # Determinar la ruta relativa para Django
            # La foto ya está en media/inspection_photos/OK o NOK
            relative_path = f"inspection_photos/{photo_status}/{photo_path.name}"
            
            # Crear registro de foto
            photo = InspectionPhoto.objects.create(
                inspection=inspection,
                photo=relative_path,
                caption=f'Foto de cámara InSight 3800 - {photo_path.name}',
                photo_type='camera_insight_3800',
                defecto_encontrado=(photo_status == 'NOK'),
            )
            
            # Mark photo as processed
            self.processed_photos.add(photo_path.name)
            
            logger.info(f"Foto vinculada a inspección {inspection.id}: {relative_path}")
            
            return photo
            
        except Exception as e:
            logger.error(f"Error vinculando foto a inspección {inspection.id}: {e}")
            return None
    
    def update_machine_stats(self, inspection: Inspection):
        """Actualizar estadísticas de la máquina de inspección"""
        try:
            machine = InspectionMachine.get_machine()
            machine.total_inspections += 1
            machine.inspections_today += 1
            machine.last_inspection = datetime.now()
            machine.current_inspection = inspection
            
            # Actualizar contadores de defectos
            if inspection.defecto_encontrado:
                machine.total_defects_found += 1
            
            # Calcular tasa de éxito
            total = machine.total_inspections
            if total > 0:
                approved = Inspection.objects.filter(status='approved').count()
                machine.success_rate = (approved / total) * 100.0
            
            machine.save()
            
            logger.info(f"Estadísticas de máquina actualizadas - Total: {machine.total_inspections}")
            
        except Exception as e:
            logger.error(f"Error actualizando estadísticas de máquina: {e}")
    
    def process_raw_data(self, raw_data: PlcDataRaw) -> bool:
        """
        Procesar un registro raw individual
        
        Steps:
        1. Extraer acquisition ID del JSON
        2. Buscar foto correspondiente en OK/NOK
        3. Si se encuentra foto, crear inspección
        4. Vincular foto a inspección
        5. Actualizar estadísticas de máquina
        6. Marcar como procesado
        
        Returns:
            True si se procesó exitosamente, False en caso contrario
        """
        try:
            logger.info(f"Procesando raw data ID: {raw_data.id}")
            
            # Paso 1: Extraer acquisition ID
            acquisition_id = self.extract_acquisition_id(raw_data.json_data)
            
            if not acquisition_id:
                logger.warning(f"No se pudo extraer acquisition ID de raw data {raw_data.id}")
                raw_data.processed = True  # Marcar como procesado para no reintentarlo
                raw_data.save()
                return False
            
            # Paso 2: Buscar foto
            photo_result = self.find_photo_by_id(acquisition_id)
            
            if not photo_result:
                logger.info(f"No hay foto disponible para acquisition ID {acquisition_id}, se marca como procesado")
                raw_data.processed = True
                raw_data.save()
                return False
            
            photo_path, photo_status = photo_result
            
            # Paso 3: Crear inspección
            inspection = self.create_inspection_from_photo(
                acquisition_id=acquisition_id,
                photo_path=photo_path,
                photo_status=photo_status,
                raw_data=raw_data
            )
            
            if not inspection:
                logger.error(f"No se pudo crear inspección para acquisition ID {acquisition_id}")
                return False
            
            # Paso 4: Vincular foto a inspección
            photo_record = self.link_photo_to_inspection(
                inspection=inspection,
                photo_path=photo_path,
                photo_status=photo_status
            )
            
            if not photo_record:
                logger.warning(f"No se pudo vincular foto a inspección {inspection.id}")
            
            # Paso 5: Actualizar estadísticas de máquina
            self.update_machine_stats(inspection)
            
            # Paso 6: Marcar como procesado
            raw_data.processed = True
            raw_data.save()
            
            logger.info(f"[ÉXITO] Raw data {raw_data.id} procesado - Inspección {inspection.id} creada - Estado: {inspection.status}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error procesando raw data {raw_data.id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def process_new_photos_only(self) -> Dict[str, int]:
        """
        Procesar solo fotos nuevas (detectar nuevas fotos y crear inspecciones)
        REGLA: Solo crea inspección si el nombre de la foto coincide con un InSight_3800-AcquisitionID del CSV
        """
        try:
            # Get new photos
            new_photos = self.get_new_photos()
            
            if not new_photos:
                logger.debug("No hay fotos nuevas para procesar")
                return {'photos': 0, 'inspections': 0, 'errors': 0, 'skipped': 0}
            
            inspections_created = 0
            error_count = 0
            skipped_count = 0
            
            logger.info(f"Procesando {len(new_photos)} fotos nuevas...")
            
            for photo_path, photo_status in new_photos:
                try:
                    # Extract acquisition ID from filename (without extension)
                    acquisition_id = photo_path.stem  # Gets filename without extension
                    
                    # MANDATORY: Find corresponding raw data for this acquisition ID
                    raw_data = self._find_raw_data_for_acquisition_id(acquisition_id)
                    
                    if not raw_data:
                        # SKIP: No matching PLC data - do NOT create inspection
                        logger.warning(
                            f"[SKIP] OMITIDA foto {photo_path.name} - "
                            f"No hay datos PLC con AcquisitionID='{acquisition_id}' en CSV/base de datos"
                        )
                        skipped_count += 1
                        # Mark as "processed" so we don't check again, but don't create inspection
                        self.processed_photos.add(photo_path.name)
                        continue
                    
                    # Found matching PLC data - proceed with inspection creation
                    logger.info(f"[MATCH] Encontrados datos PLC para foto {photo_path.name} (AcquisitionID: {acquisition_id})")
                    
                    # Create inspection
                    inspection = self.create_inspection_from_photo(
                        acquisition_id=acquisition_id,
                        photo_path=photo_path,
                        photo_status=photo_status,
                        raw_data=raw_data
                    )
                    
                    if inspection:
                        # Link photo
                        self.link_photo_to_inspection(inspection, photo_path, photo_status)
                        
                        # Update machine stats
                        self.update_machine_stats(inspection)
                        
                        inspections_created += 1
                        logger.info(f"[OK] Inspección creada para foto {photo_path.name} - Estado: {photo_status}")
                    else:
                        error_count += 1
                        
                except Exception as e:
                    error_count += 1
                    logger.error(f"Error procesando foto {photo_path.name}: {e}")
            
            # Summary
            if inspections_created > 0:
                logger.info(f"[SUCCESS] {inspections_created} nuevas inspecciones creadas")
            if skipped_count > 0:
                logger.info(f"[INFO] {skipped_count} fotos omitidas (sin datos PLC correspondientes)")
            
            return {
                'photos': len(new_photos),
                'inspections': inspections_created,
                'errors': error_count,
                'skipped': skipped_count
            }
            
        except Exception as e:
            logger.error(f"Error procesando fotos nuevas: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {'photos': 0, 'inspections': 0, 'errors': 1, 'skipped': 0}
    
    def _find_raw_data_for_acquisition_id(self, acquisition_id: str) -> Optional[PlcDataRaw]:
        """
        Buscar datos raw que contengan el acquisition ID especificado
        Retorna el registro de plc_data_raw que coincida, o None si no existe
        """
        try:
            # Search for raw data containing this acquisition ID
            raw_data_list = PlcDataRaw.objects.all().order_by('-timestamp')
            
            for raw_data in raw_data_list:
                try:
                    json_obj = json.loads(raw_data.json_data)
                    # Try both with and without leading space
                    acq_id = json_obj.get(' InSight_3800-AcquisitionID') or json_obj.get('InSight_3800-AcquisitionID')
                    
                    # Compare as strings, stripping whitespace
                    if str(acq_id).strip() == str(acquisition_id).strip():
                        logger.debug(f"Encontrado PLC data para AcquisitionID '{acquisition_id}' (raw_data ID: {raw_data.id})")
                        return raw_data
                except json.JSONDecodeError:
                    # Skip invalid JSON
                    continue
                except Exception as e:
                    # Skip problematic records
                    logger.debug(f"Error parseando raw_data ID {raw_data.id}: {e}")
                    continue
            
            # No matching data found
            return None
            
        except Exception as e:
            logger.error(f"Error buscando raw data para acquisition ID {acquisition_id}: {e}")
            return None
    
    def process_all_unprocessed_data(self, batch_size: int = 100):
        """Procesar todos los datos raw no procesados"""
        try:
            logger.info("=" * 80)
            logger.info("Iniciando procesamiento de datos PLC...")
            logger.info("=" * 80)
            
            raw_data_list = self.get_unprocessed_raw_data(limit=batch_size)
            
            if not raw_data_list:
                logger.debug("No hay datos raw para procesar")
                return
            
            processed_count = 0
            error_count = 0
            inspections_created = 0
            
            for raw_data in raw_data_list:
                if self.process_raw_data(raw_data):
                    processed_count += 1
                    # Verificar si se creó inspección (no siempre se crea si no hay foto)
                    if Inspection.objects.filter(
                        notes__contains=f'plc_data_raw ID: {raw_data.id}'
                    ).exists():
                        inspections_created += 1
                else:
                    error_count += 1
            
            if processed_count > 0 or error_count > 0:
                logger.info("=" * 80)
                logger.info("Resumen de procesamiento PLC:")
                logger.info(f"  - Registros procesados: {processed_count}")
                logger.info(f"  - Inspecciones creadas: {inspections_created}")
                logger.info(f"  - Errores: {error_count}")
                logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"Error en procesamiento por lotes: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def monitor_and_process(self, interval_seconds: int = 30):
        """
        Monitorear fotos nuevas y procesar cada N segundos
        Solo crea inspecciones si hay fotos nuevas
        """
        logger.info("=" * 80)
        logger.info("Iniciando monitor de fotos e inspecciones")
        logger.info(f"Intervalo: {interval_seconds} segundos")
        logger.info("Presione Ctrl+C para detener...")
        logger.info("=" * 80)
        
        self.is_running = True
        cycle_count = 0
        
        try:
            while self.is_running:
                cycle_count += 1
                logger.info(f"[Ciclo {cycle_count}] Verificando fotos nuevas...")
                
                # Process new photos
                result = self.process_new_photos_only()
                
                if result['inspections'] > 0 or result['errors'] > 0 or result.get('skipped', 0) > 0:
                    logger.info(
                        f"[Ciclo {cycle_count}] "
                        f"Fotos nuevas: {result['photos']}, "
                        f"Inspecciones creadas: {result['inspections']}, "
                        f"Omitidas: {result.get('skipped', 0)}, "
                        f"Errores: {result['errors']}"
                    )
                
                # Also process any unprocessed PLC data (optional)
                # self.process_all_unprocessed_data()
                
                # Wait before next check
                if self.is_running:
                    time.sleep(interval_seconds)
                
        except KeyboardInterrupt:
            logger.info("Monitor interrumpido por el usuario")
        except Exception as e:
            logger.error(f"Error en monitor: {e}")
            import traceback
            logger.error(traceback.format_exc())
        finally:
            self.is_running = False
            logger.info("Monitor detenido")
    
    def run_processing_loop(self, interval_seconds: int = 30):
        """Ejecutar el bucle principal de procesamiento (legacy method)"""
        # Redirect to new monitor method
        self.monitor_and_process(interval_seconds)
    
    def stop_processing(self):
        """Detener el bucle de procesamiento"""
        self.is_running = False
        logger.info("Deteniendo procesamiento...")


def start_background_monitor(interval_seconds: int = 30):
    """
    Iniciar monitor en background (para uso desde Django startup)
    Monitorea fotos nuevas y crea inspecciones automáticamente
    """
    import threading
    
    def monitor_thread():
        try:
            processor = PlcDataProcessor()
            processor.monitor_and_process(interval_seconds=interval_seconds)
        except Exception as e:
            logger.error(f"Error en thread de monitor de fotos: {e}")
    
    thread = threading.Thread(target=monitor_thread, daemon=True, name="PLCPhotoProcessorMonitor")
    thread.start()
    logger.info(f"Monitor de fotos iniciado en background (cada {interval_seconds}s)")
    
    return thread


def main():
    """Función principal del sistema de procesamiento PLC Conuar"""
    print("=" * 80)
    print("Procesador de Datos PLC - Sistema Conuar")
    print("Creación automática de inspecciones basadas en fotos")
    print("=" * 80)
    print()
    
    # Crear instancia del procesador
    processor = PlcDataProcessor()
    
    try:
        # Opción de modo
        print("Seleccione modo de operación:")
        print("1. Procesar fotos nuevas una vez y salir")
        print("2. Monitorear fotos continuamente (cada 30 segundos)")
        
        try:
            choice = input("Opción (1 o 2): ").strip()
        except:
            choice = "2"  # Default to monitoring
        
        if choice == "1":
            # Process once
            result = processor.process_new_photos_only()
            print(f"\nResultados:")
            print(f"  - Fotos nuevas: {result['photos']}")
            print(f"  - Inspecciones creadas: {result['inspections']}")
            print(f"  - Fotos omitidas (sin PLC data): {result.get('skipped', 0)}")
            print(f"  - Errores: {result['errors']}")
        else:
            # Continuous monitoring
            processor.monitor_and_process(interval_seconds=30)
            
    except Exception as e:
        logger.error(f"Error fatal: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        processor.stop_processing()


if __name__ == "__main__":
    main()
