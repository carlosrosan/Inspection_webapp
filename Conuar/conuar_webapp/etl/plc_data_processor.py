#!/usr/bin/env python3
"""
PLC Data Processor - Sistema Conuar

Este script agrupa lecturas PLC en ciclos, busca fotos en el directorio
STAGING que cumplan el patrón
    {NombreCiclo}-{ID_EC}-{ID}-{Fecha formato DDMMYY}_{Hora formato HHMMss}-{Falla}.bmp
    Ejemplo: Ciclo2-E123-3F-041225_154941-NOK.bmp
Las fotos se matchean SOLO por los primeros 3 campos: {NombreCiclo}-{ID_EC}-{ID}
Un ciclo comienza cuando CicloActivo cambia a TRUE y termina cuando cambia a FALSE.
Cada foto utilizada se mueve a PROCESSED y se vincula a la inspección resultante.

Sistema de inspección de combustible Conuar
"""

import os
import sys
import django
import time
import shutil
import logging
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from django.db import transaction

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

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(r'C:\Users\USER\Documents\GitHub\Inspection_webapp\Conuar\conuar_webapp\logs\plc_data_processor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class PlcDataProcessor:
    """Clase para procesar datos del PLC y crear inspecciones basadas en fotos"""
    
    def __init__(self):
        self.is_running = False
        
        # Rutas de directorios de fotos
        self.base_photo_path = Path(r"C:\Users\USER\Documents\GitHub\Inspection_webapp\Conuar\conuar_webapp\media\inspection_photos")
        self.staging_photo_path = self.base_photo_path / "STAGING"
        self.processed_photo_path = self.base_photo_path / "PROCESSED"
        if not self.staging_photo_path.exists():
            logger.warning(f"Directorio STAGING no existe: {self.staging_photo_path}")
        self.processed_photo_path.mkdir(parents=True, exist_ok=True)

        # Track processed photos to avoid reprocessing
        self.processed_photos: set = set()
        
        # Load existing processed photos from database
        self._load_processed_photos()

    def _get_field_value(self, row: dict, field_name: str, fallback_names: List[str] = None) -> str:
        """
        Safely extract field value from row, handling booleans, None, and empty strings.
        Returns empty string if not found or invalid.
        """
        if fallback_names is None:
            fallback_names = []
        
        # Try main field name and variants
        field_variants = [field_name, f' {field_name}'] + fallback_names
        
        for variant in field_variants:
            value = row.get(variant)
            if value is None:
                continue
            
            # Handle boolean False/True
            if isinstance(value, bool):
                if value is False:
                    return ''  # False means empty/missing
                else:
                    return 'true'  # True as string (unlikely for these fields)
            
            # Convert to string and strip
            value_str = str(value).strip()
            
            # Skip empty strings, "false", "None", etc.
            if value_str and value_str.lower() not in ('false', 'none', 'null', ''):
                return value_str
        
        return ''
    
    def _build_photo_match_prefix(self, row: dict) -> str:
        """
        Build the matching prefix for photos (first 3 fields only):
        {NombreCiclo}-{ID_EC}-{ID}
        This is used to match photos regardless of date/time/falla values.
        """
        try:
            # Handle field names with/without leading spaces, handle booleans/empty values
            nombre_ciclo = self._get_field_value(row, 'NombreCiclo', ['nombre_ciclo'])
            id_ec = self._get_field_value(row, 'ID_EC', ['elemento_combustible'])
            id_value = self._get_field_value(row, 'ID', ['id_puntero', 'PunteroControl'])
            
            if not nombre_ciclo or not id_ec or not id_value:
                raise KeyError(f"Missing required fields for photo matching: NombreCiclo={nombre_ciclo!r}, ID_EC={id_ec!r}, ID={id_value!r}")
            
            # Return only the first 3 fields for matching
            return f"{nombre_ciclo}-{id_ec}-{id_value}"
        except KeyError as exc:
            logger.warning(
                f"Falta campo requerido {exc} en datos PLC para construir prefijo de foto"
            )
            raise

    def _find_staged_photo(self, row: dict) -> Optional[Path]:
        """
        Find photo in STAGING folder matching by first 3 fields only:
        {NombreCiclo}-{ID_EC}-{ID}
        Full format: {NombreCiclo}-{ID_EC}-{ID}-{Fecha formato DDMMYY}_{Hora formato HHMMss}-{Falla}.bmp
        Example: Ciclo2-E123-3F-041225_154941-NOK.bmp
        """
        try:
            # Build match prefix (first 3 fields only)
            match_prefix = self._build_photo_match_prefix(row)
        except KeyError as exc:
            logger.warning(
                f"Falta campo requerido {exc} en datos PLC para construir prefijo de foto"
            )
            return None

        # Search for photos that start with the match prefix
        # Match pattern: {NombreCiclo}-{ID_EC}-{ID}-...
        if not self.staging_photo_path.exists():
            return None
        
        # Try different extensions
        for ext in (".bmp", ".jpg", ".jpeg", ".png"):
            # Look for files starting with the match prefix
            for photo_file in self.staging_photo_path.glob(f"{match_prefix}-*{ext}"):
                # Verify it matches the pattern (starts with our prefix)
                if photo_file.name.startswith(match_prefix + "-"):
                    return photo_file
        
        # Also try exact match if no date/time/falla pattern found
        for ext in (".bmp", ".jpg", ".jpeg", ".png"):
            candidate = self.staging_photo_path / f"{match_prefix}{ext}"
            if candidate.exists():
                return candidate
        
        return None

    def _is_boolean_true(self, value) -> bool:
        """Check if a value represents boolean TRUE"""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes')
        if isinstance(value, (int, float)):
            return value == 1
        return False
    
    def _extract_failure_from_photo_filename(self, photo_path: Path) -> bool:
        """
        Extract failure status from photo filename.
        Photo format: {NombreCiclo}-{ID_EC}-{ID}-{Fecha}_{Hora}-{Falla}.bmp
        Where {Falla} is either 'NOK' (failure) or 'OK' (no failure)
        Returns True if failure detected (NOK), False otherwise (OK or not found)
        """
        if not photo_path:
            return False
        
        filename = photo_path.name
        
        # Check if filename ends with -NOK.bmp or contains -NOK.
        if '-NOK.' in filename.upper() or filename.upper().endswith('-NOK.BMP'):
            return True
        
        # Check if filename ends with -OK.bmp (explicitly OK, no failure)
        if '-OK.' in filename.upper() or filename.upper().endswith('-OK.BMP'):
            return False
        
        # If pattern not found, try to extract from end of filename
        # Pattern: ...-{Falla}.bmp where Falla is NOK or OK
        for ext in ('.bmp', '.jpg', '.jpeg', '.png'):
            if filename.lower().endswith(ext):
                # Remove extension
                name_without_ext = filename[:-len(ext)]
                # Check if it ends with -NOK or -OK
                if name_without_ext.upper().endswith('-NOK'):
                    return True
                elif name_without_ext.upper().endswith('-OK'):
                    return False
                break
        
        # Default: no failure detected if pattern not found
        return False
    
    def _group_raw_rows_by_cycle(self, raw_rows: List[PlcDataRaw]) -> List[List[PlcDataRaw]]:
        """
        Group raw rows into cycles based on CicloActivo changes.
        Cycle starts when CicloActivo changes to TRUE, ends when it changes to FALSE.
        """
        cycles, current = [], []
        collecting = False
        prev_ciclo_activo = False
        
        for raw in raw_rows:
            data = json.loads(raw.json_data)
            # Get CicloActivo value (handle field name with/without leading space)
            ciclo_activo = data.get("CicloActivo") or data.get(" CicloActivo")
            is_active = self._is_boolean_true(ciclo_activo)
            
            # Start collecting when CicloActivo changes from FALSE to TRUE
            if is_active and not collecting:
                collecting = True
                current = []
                prev_ciclo_activo = True
            
            # Collect rows while cycle is active
            if collecting:
                raw._parsed_json = data  # cache for later
                current.append(raw)
                
                # End cycle when CicloActivo changes from TRUE to FALSE
                if not is_active and prev_ciclo_activo:
                    cycles.append(current)
                    current, collecting = [], False
                    prev_ciclo_activo = False
                elif is_active:
                    prev_ciclo_activo = True
        
        # If still collecting at the end, add the current cycle
        if collecting and current:
            cycles.append(current)
        
        return cycles

    def _find_valid_field_in_cycle(self, cycle_rows: List[PlcDataRaw], field_name: str, fallback_names: List[str] = None) -> str:
        """
        Search through cycle rows to find a valid (non-empty) value for a field.
        Useful when first row has empty values but later rows have them.
        """
        if fallback_names is None:
            fallback_names = []
        
        for raw in cycle_rows:
            data = raw._parsed_json
            value = self._get_field_value(data, field_name, fallback_names)
            if value:
                return value
        return ''
    
    def _create_or_fetch_cycle_inspection(self, cycle_rows: List[PlcDataRaw]) -> Tuple[Inspection, bool]:
        first = cycle_rows[0]._parsed_json
        inspector = self.get_default_inspector()
        
        # Get values using new field names, with fallback to old names for compatibility
        # Search through cycle if first row has empty values
        nombre_ciclo = self._get_field_value(first, 'NombreCiclo', ['nombre_ciclo'])
        if not nombre_ciclo:
            nombre_ciclo = self._find_valid_field_in_cycle(cycle_rows, 'NombreCiclo', ['nombre_ciclo'])
            if nombre_ciclo:
                logger.info(f"NombreCiclo encontrado en otra fila del ciclo: {nombre_ciclo}")
            else:
                logger.warning(f"NombreCiclo no encontrado en ningún registro del ciclo")
        
        id_ec = self._get_field_value(first, 'ID_EC', ['elemento_combustible'])
        if not id_ec:
            id_ec = self._find_valid_field_in_cycle(cycle_rows, 'ID_EC', ['elemento_combustible'])
            if id_ec:
                logger.info(f"ID_EC encontrado en otra fila del ciclo: {id_ec}")
            else:
                logger.warning(f"ID_EC no encontrado en ningún registro del ciclo")
        
        # Build datetime from FechaFoto and HoraFoto, or use timestamp from database
        # Handle field names with/without leading spaces, search cycle if needed
        fecha_foto = self._get_field_value(first, 'FechaFoto')
        if not fecha_foto:
            fecha_foto = self._find_valid_field_in_cycle(cycle_rows, 'FechaFoto')
        
        hora_foto = self._get_field_value(first, 'HoraFoto')
        if not hora_foto:
            hora_foto = self._find_valid_field_in_cycle(cycle_rows, 'HoraFoto')
        if fecha_foto and hora_foto:
            # Format: FechaFoto=041225 (DDMMYY), HoraFoto=154941 (HHMMSS) -> 2025-12-04 15:49:41
            try:
                # Assuming format: DDMMYY for date, HHMMSS for time
                if len(fecha_foto) == 6 and len(hora_foto) == 6:
                    # Parse DDMMYY format
                    day = fecha_foto[0:2]
                    month = fecha_foto[2:4]
                    year = "20" + fecha_foto[4:6]
                    # Parse HHMMSS format
                    hour = hora_foto[0:2]
                    minute = hora_foto[2:4]
                    second = hora_foto[4:6]
                    date_str = f"{year}-{month}-{day} {hour}:{minute}:{second}"
                    inspection_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                else:
                    inspection_date = cycle_rows[0].timestamp if hasattr(cycle_rows[0], 'timestamp') else datetime.now()
            except Exception as e:
                logger.warning(f"Error parsing FechaFoto/HoraFoto: {e}, using database timestamp")
                inspection_date = cycle_rows[0].timestamp if hasattr(cycle_rows[0], 'timestamp') else datetime.now()
        else:
            # Fallback to datetime field or database timestamp
            datetime_str = first.get('datetime') or first.get('timestamp')
            if datetime_str:
                try:
                    inspection_date = datetime.fromisoformat(datetime_str.replace('Z','').replace('T',' '))
                except:
                    inspection_date = cycle_rows[0].timestamp if hasattr(cycle_rows[0], 'timestamp') else datetime.now()
            else:
                inspection_date = cycle_rows[0].timestamp if hasattr(cycle_rows[0], 'timestamp') else datetime.now()
        
        # Build natural key for inspection
        natural_key = f"{nombre_ciclo}-{id_ec}-{inspection_date.isoformat()}"
        
        # Check for defects: Falla="1" or "true" means NOK, otherwise OK
        defecto_encontrado = any(
            (self._is_boolean_true(r._parsed_json.get('Falla') or r._parsed_json.get(' Falla'))) or
            (r._parsed_json.get('defecto') == 'NOK')  # fallback for old format
            for r in cycle_rows
        )
        
        inspection, created = Inspection.objects.get_or_create(
            product_code=natural_key,
            defaults={
                "title": f"Inspección {nombre_ciclo}",
                "description": f"Inspección {nombre_ciclo} del elemento combustible {id_ec}",
                "tipo_combustible": "uranio",
                "status": "in_progress",
                "defecto_encontrado": defecto_encontrado,
                "product_name": first.get('nombre_ubicacion') or "Línea Conuar",
                "serial_number": id_ec,
                "batch_number": nombre_ciclo,
                "location": first.get("pos_camara", ""),
                "inspection_date": inspection_date,
                "inspector": inspector,
                "notes": f"Cycle starting at PLC row {cycle_rows[0].id}",
            },
        )
        return inspection, created

    @transaction.atomic
    def process_cycle(self, cycle_rows: List[PlcDataRaw]) -> bool:
        inspection, created = self._create_or_fetch_cycle_inspection(cycle_rows)
        attached = self._link_cycle_photos(inspection, cycle_rows)
        if attached == 0:
            logger.warning(
                f"No se encontraron fotos para el ciclo {inspection.product_code}. "
                "Se marcan las filas como procesadas sin crear inspección."
            )
            for raw in cycle_rows:
                raw.processed = True
                raw.save(update_fields=["processed"])
            if created:
                inspection.delete()
            return False
        inspection.status = "completed"
        inspection.completed_date = datetime.now()
        
        # Defect status is now determined by photos (set in _link_cycle_photos)
        # But also check CSV as fallback if no photos were found
        if attached > 0:
            # Defect status already set by _link_cycle_photos based on photo filenames
            pass
        else:
            # No photos found, use CSV data as fallback
            inspection.defecto_encontrado = any(
                (self._is_boolean_true(r._parsed_json.get('Falla') or r._parsed_json.get(' Falla'))) or
                (r._parsed_json.get('defecto') == 'NOK')  # fallback for old format
                for r in cycle_rows
            )
        
        inspection.save()
        for raw in cycle_rows:
            raw.processed = True
            raw.save(update_fields=["processed"])
        self.update_machine_stats(inspection)
        return True

    def _link_cycle_photos(self, inspection: Inspection, cycle_rows: List[PlcDataRaw]) -> int:
        linked = 0
        # Track which photos we've already linked to avoid duplicates
        linked_photo_names = set()
        # Track defects found in photos for inspection-level defect detection
        defects_found_in_photos = []
        
        # Track the inspection folder (created from first photo name)
        inspection_folder = None
        
        for raw in cycle_rows:
            payload = raw._parsed_json
            
            # Skip rows with missing required fields for photo matching
            nombre_ciclo = self._get_field_value(payload, 'NombreCiclo', ['nombre_ciclo'])
            id_ec = self._get_field_value(payload, 'ID_EC', ['elemento_combustible'])
            id_value = self._get_field_value(payload, 'ID', ['id_puntero', 'PunteroControl'])
            
            if not nombre_ciclo or not id_ec or not id_value:
                # Skip this row - missing required fields for photo matching
                logger.debug(
                    f"Omitiendo fila del ciclo - campos faltantes: "
                    f"NombreCiclo={nombre_ciclo!r}, ID_EC={id_ec!r}, ID={id_value!r}"
                )
                continue
            
            photo_path = self._find_staged_photo(payload)
            if not photo_path:
                logger.warning(
                    f"No se encontró foto en STAGING para ciclo {nombre_ciclo} "
                    f"ID {id_value}"
                )
                continue
            
            # Skip if we've already linked this photo (avoid duplicates)
            if photo_path.name in linked_photo_names:
                logger.debug(f"Foto {photo_path.name} ya vinculada, omitiendo duplicado")
                continue
            
            linked_photo_names.add(photo_path.name)
            
            # Extract defect status from photo filename BEFORE moving (most reliable source)
            defect_from_photo = self._extract_failure_from_photo_filename(photo_path)
            defects_found_in_photos.append(defect_from_photo)
            
            # Also check CSV Falla field as fallback
            falla = self._get_field_value(payload, 'Falla')
            if not falla:
                falla = payload.get('Falla') or payload.get(' Falla', '0')
            defecto_from_csv = self._is_boolean_true(falla) or (payload.get("defecto") == "NOK")
            
            # Use photo filename as primary source, CSV as fallback
            defecto_encontrado = defect_from_photo or defecto_from_csv
            
            logger.info(
                f"Foto {photo_path.name}: defecto_from_photo={defect_from_photo}, "
                f"defecto_from_csv={defecto_from_csv}, defecto_encontrado={defecto_encontrado}"
            )

            # Create inspection folder from first photo name (without extension)
            if inspection_folder is None:
                # Get photo name without extension for folder name
                photo_name_without_ext = photo_path.stem  # Gets filename without extension
                inspection_folder = self.processed_photo_path / photo_name_without_ext
                inspection_folder.mkdir(parents=True, exist_ok=True)
                logger.info(f"Creada carpeta de inspección: {inspection_folder}")
            
            # Move photo to inspection-specific folder
            destination = inspection_folder / photo_path.name
            try:
                shutil.move(str(photo_path), str(destination))
            except FileNotFoundError:
                logger.warning(f"La foto {photo_path} desapareció antes de moverla a PROCESSED")
                continue
            except shutil.Error as exc:
                logger.warning(f"No se pudo mover {photo_path} a {destination}: {exc}")
                continue

            # Update relative path to include the inspection folder
            relative_path = f"inspection_photos/PROCESSED/{inspection_folder.name}/{destination.name}"
            
            InspectionPhoto.objects.create(
                inspection=inspection,
                photo=relative_path,
                caption=f"Ciclo {nombre_ciclo} ID {id_value}",
                photo_type="plc_cycle",
                defecto_encontrado=defecto_encontrado,
            )

            self.processed_photos.add(destination.name)
            linked += 1
        
        # Update inspection defect status based on photos found
        if defects_found_in_photos:
            inspection.defecto_encontrado = any(defects_found_in_photos)
            inspection.save(update_fields=['defecto_encontrado'])
            logger.info(
                f"Inspección {inspection.product_code}: "
                f"defectos encontrados en {sum(defects_found_in_photos)} de {len(defects_found_in_photos)} fotos"
            )

        return linked

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
    
    def process_pending_cycles(self, batch_size: int = 500) -> Dict[str, int]:
        """Agrupa raws PLC en ciclos y crea una inspección por ciclo."""
        summary = {"cycles": 0, "inspections": 0, "errors": 0}

        raw_rows = self.get_unprocessed_raw_data(limit=batch_size)
        if not raw_rows:
            logger.debug("No hay datos PLC pendientes por ciclo.")
            return summary

        cycles = self._group_raw_rows_by_cycle(raw_rows)
        summary["cycles"] = len(cycles)

        logger.info("=" * 80)
        logger.info("Procesamiento de ciclos PLC")
        logger.info(f"Ciclos detectados: {summary['cycles']}")
        logger.info("=" * 80)

        for idx, cycle_rows in enumerate(cycles, start=1):
            try:
                logger.info(
                    f"[Ciclo {idx}/{summary['cycles']}] Procesando filas PLC "
                    f"({cycle_rows[0].id} to {cycle_rows[-1].id})"
                )
                if self.process_cycle(cycle_rows):
                    summary["inspections"] += 1
                else:
                    summary["errors"] += 1
            except Exception:
                summary["errors"] += 1
                logger.exception(f"Error procesando ciclo #{idx}")

        if summary["inspections"]:
            logger.info(f"Inspecciones creadas: {summary['inspections']}")
        if summary["errors"]:
            logger.warning(f"Ciclos con error: {summary['errors']}")

        return summary
    
    def monitor_and_process(self, interval_seconds: int = 30):
        """
        Monitorear periódicamente los datos PLC y procesar ciclos pendientes.
        """
        logger.info("=" * 80)
        logger.info("Iniciando monitor de ciclos PLC e inspecciones")
        logger.info(f"Intervalo: {interval_seconds} segundos")
        logger.info("Presione Ctrl+C para detener...")
        logger.info("=" * 80)
        
        self.is_running = True
        cycle_count = 0
        
        try:
            while self.is_running:
                cycle_count += 1
                logger.info(f"[Ciclo {cycle_count}] Buscando ciclos PLC pendientes...")

                summary = self.process_pending_cycles()
                if summary["cycles"] or summary["inspections"] or summary["errors"]:
                    logger.info(
                        f"[Ciclo {cycle_count}] "
                        f"Ciclos detectados: {summary['cycles']}, "
                        f"Inspecciones creadas: {summary['inspections']}, "
                        f"Errores: {summary['errors']}"
                    )

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
    Monitorea ciclos PLC y crea inspecciones automáticamente
    """
    import threading
    
    def monitor_thread():
        try:
            processor = PlcDataProcessor()
            processor.monitor_and_process(interval_seconds=interval_seconds)
        except Exception as e:
            logger.error(f"Error en thread de monitor de fotos: {e}")
    
    thread = threading.Thread(target=monitor_thread, daemon=True, name="PLCCycleProcessorMonitor")
    thread.start()
    logger.info(f"Monitor de ciclos iniciado en background (cada {interval_seconds}s)")
    
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
        print("Seleccione modo de operación:")
        print("1. Procesar ciclos pendientes una vez y salir")
        print("2. Monitorear continuamente (cada 30 segundos)")
        try:
            choice = input("Opción (1 o 2): ").strip()
        except Exception:
            choice = "2"

        if choice == "1":
            summary = processor.process_pending_cycles()
            print("\nResultados:")
            print(f"  - Ciclos detectados: {summary['cycles']}")
            print(f"  - Inspecciones creadas: {summary['inspections']}")
            print(f"  - Ciclos con error: {summary['errors']}")
        else:
            processor.monitor_and_process(interval_seconds=30)

    except Exception as e:
        logger.error(f"Error fatal: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        processor.stop_processing()


if __name__ == "__main__":
    main()
