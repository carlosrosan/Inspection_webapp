#!/usr/bin/env python3
"""
PLC Data Processor - Sistema Conuar

Este script agrupa lecturas PLC en ciclos, busca fotos en el directorio
STAGING que cumplan el patrón
    {NombreCiclo}-{ID_EC}-{ID_Control}-{Fecha formato DDMMYY}_{Hora formato HHMMss}-{Falla}.png
    Ejemplo: Ciclo2-E123-3F-041225_154941-NOK.png
Las fotos se matchean SOLO por los primeros 3 campos: {NombreCiclo}-{ID_EC}-{ID_Control}
Un ciclo comienza cuando CicloActivo cambia a TRUE y termina cuando cambia a FALSE.

Two-phase processing (DB-first pattern):
  Phase 1 (atomic): Create Inspection + InspectionPhoto rows, combine PNG+SVG -> _comb.png
  Phase 2 (post-commit): Move all files (PNG, SVG, _comb.png) from STAGING to PROCESSED

Concurrent Django instances share one MySQL DB: process_pending_cycles uses GET_LOCK so only
one instance runs PLC cycle → inspection creation at a time (avoids duplicate get_or_create races).

PDF generation is disabled; PDFs are created manually via the web UI button.

Sistema de inspección de combustible Conuar
"""

import os
import sys
import django
import time
import shutil
import logging
import json
import re
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

# Import photo unificator (handle both standalone and Django contexts)
try:
    from etl.photo_unificator import unify_photo, unify_photo_png
except ImportError:
    from photo_unificator import unify_photo, unify_photo_png

# Root of the Django project (conuar_webapp/), independent of deployment path
_BASE_DIR = Path(__file__).resolve().parent.parent

# Configurar logging
# Use 'etl.plc_data_processor' logger name to work with Django's LOGGING config
# This ensures logs appear in console when running via manage.py
logger = logging.getLogger('etl.plc_data_processor')

# Only configure basicConfig if not already configured (standalone mode)
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(_BASE_DIR / 'logs' / 'plc_data_processor.log'),
            logging.StreamHandler()
        ]
    )

# MySQL session lock: must be <= 64 chars. Shared across all app instances using the same DB.
MYSQL_PLC_CYCLE_LOCK_NAME = "conuar_plc_pending_cycles"


def _mysql_acquire_plc_cycle_lock_nonblocking() -> bool:
    """
    Try to acquire MySQL advisory lock (GET_LOCK) for PLC batch processing.
    Returns True if this connection holds the lock; False if another session holds it.
    On non-MySQL backends, returns True (no cross-process lock; dev/test only).
    """
    from django.db import connection

    if connection.vendor != "mysql":
        logger.debug(
            "PLC cycle lock skipped (database vendor=%s; GET_LOCK is MySQL-only).",
            connection.vendor,
        )
        return True

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT GET_LOCK(%s, %s)",
                [MYSQL_PLC_CYCLE_LOCK_NAME, 0],
            )
            row = cursor.fetchone()
    except Exception as exc:
        logger.error("GET_LOCK(%r) failed: %s", MYSQL_PLC_CYCLE_LOCK_NAME, exc, exc_info=True)
        return False

    if not row:
        return False
    # GET_LOCK returns 1 = acquired, 0 = already held by another, NULL = error
    return row[0] == 1


def _mysql_release_plc_cycle_lock() -> None:
    from django.db import connection

    if connection.vendor != "mysql":
        return
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT RELEASE_LOCK(%s)", [MYSQL_PLC_CYCLE_LOCK_NAME])
    except Exception as exc:
        logger.warning("RELEASE_LOCK(%r): %s", MYSQL_PLC_CYCLE_LOCK_NAME, exc)


class PlcDataProcessor:
    """Clase para procesar datos del PLC y crear inspecciones basadas en fotos"""
    
    def __init__(self):
        self.is_running = False
        
        # Rutas de directorios de fotos (usar configuración centralizada)
        try:
            from config.paths_config import (
                INSPECTION_PHOTOS_DIR,
                INSPECTION_PHOTOS_STAGING_DIR,
                INSPECTION_PHOTOS_PROCESSED_DIR,
                ensure_directories_exist
            )
            ensure_directories_exist()
            self.base_photo_path = Path(INSPECTION_PHOTOS_DIR)
            self.staging_photo_path = Path(INSPECTION_PHOTOS_STAGING_DIR)
            self.processed_photo_path = Path(INSPECTION_PHOTOS_PROCESSED_DIR)
        except ImportError:
            # Fallback a rutas hardcodeadas si no se puede importar la configuración
            logger.warning("No se pudo importar config.paths_config, usando rutas por defecto")
            self.base_photo_path = _BASE_DIR / 'media' / 'inspection_photos'
            self.staging_photo_path = self.base_photo_path / "STAGING"
            self.processed_photo_path = self.base_photo_path / "PROCESSED"
            self.processed_photo_path.mkdir(parents=True, exist_ok=True)
        
        if not self.staging_photo_path.exists():
            logger.warning(f"Directorio STAGING no existe: {self.staging_photo_path}")

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
        {NombreCiclo}-{ID_EC}-{ID_Control}
        This is used to match photos regardless of date/time/falla values.
        """
        try:
            # Handle field names with/without leading spaces, handle booleans/empty values
            nombre_ciclo = self._get_field_value(row, 'NombreCiclo', ['nombre_ciclo'])
            id_ec = self._get_field_value(row, 'ID_EC', ['elemento_combustible'])
            id_value = self._get_field_value(row, 'ID_Control', ['ID', 'id_puntero', 'PunteroControl'])
            
            if not nombre_ciclo or not id_ec or not id_value:
                raise KeyError(f"Missing required fields for photo matching: NombreCiclo={nombre_ciclo!r}, ID_EC={id_ec!r}, ID_Control={id_value!r}")
            
            # Return only the first 3 fields for matching
            return f"{nombre_ciclo}-{id_ec}-{id_value}"
        except KeyError as exc:
            logger.warning(
                f"Falta campo requerido {exc} en datos PLC para construir prefijo de foto"
            )
            raise

    def _find_staged_photos(self, row: dict, exclude_photo_names: set = None) -> List[Path]:
        """
        Find ALL photos in STAGING folder matching by first 3 fields only:
        {NombreCiclo}-{ID_EC}-{ID_Control}
        Full format: {NombreCiclo}-{ID_EC}-{ID_Control}-{Fecha formato DDMMYY}_{Hora formato HHMMss}-{Falla}{PhotoNumber}.png
        Example: Ciclo2-E123-3F-041225_154941-NOK753.png

        Source photos are PNG (current format) or BMP (legacy).
        Files ending in '_comb.png' are excluded (those are generated output).
        """
        if exclude_photo_names is None:
            exclude_photo_names = set()
        
        try:
            match_prefix = self._build_photo_match_prefix(row)
        except KeyError as exc:
            logger.warning(
                f"Falta campo requerido {exc} en datos PLC para construir prefijo de foto"
            )
            return []

        if not self.staging_photo_path.exists():
            return []
        
        matching_photos = []
        
        for ext in (".png", ".bmp", ".jpg", ".jpeg"):
            for photo_file in self.staging_photo_path.glob(f"{match_prefix}-*{ext}"):
                if photo_file.name.startswith(match_prefix + "-"):
                    if photo_file.stem.endswith('_comb'):
                        continue
                    if photo_file.name not in exclude_photo_names:
                        matching_photos.append(photo_file)
        
        for ext in (".png", ".bmp", ".jpg", ".jpeg"):
            candidate = self.staging_photo_path / f"{match_prefix}{ext}"
            if candidate.exists() and candidate.name not in exclude_photo_names:
                if not candidate.stem.endswith('_comb'):
                    matching_photos.append(candidate)

        matching_photos.sort(key=lambda p: p.name)
        
        return matching_photos

    def _is_boolean_true(self, value) -> bool:
        """Check if a value represents boolean TRUE"""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes')
        if isinstance(value, (int, float)):
            return value == 1
        return False
    
    def _extract_timestamp_from_photo_filename(self, photo_path: Path) -> Optional[datetime]:
        """
        Extract timestamp from photo filename.
        Photo format: {NombreCiclo}-{ID_EC}-{ID_Control}-{Fecha formato DDMMYY}_{Hora formato HHMMss}-{Falla}{PhotoNumber}.bmp
        Example: COMPLETO-UNO-1F-231225_134953-NOK753.bmp
        Returns datetime object if timestamp found, None otherwise.
        """
        if not photo_path:
            return None
        
        filename = photo_path.name
        
        # Pattern: -DDMMYY_HHMMSS- (date and time in filename)
        # Match pattern: -DDMMYY_HHMMSS- where DDMMYY is date and HHMMSS is time
        timestamp_pattern = r'-(\d{6})_(\d{6})-'
        match = re.search(timestamp_pattern, filename)
        
        if match:
            fecha_str = match.group(1)  # DDMMYY
            hora_str = match.group(2)   # HHMMSS
            
            try:
                # Parse DDMMYY format
                day = int(fecha_str[0:2])
                month = int(fecha_str[2:4])
                year = 2000 + int(fecha_str[4:6])  # Assume 20XX
                
                # Parse HHMMSS format
                hour = int(hora_str[0:2])
                minute = int(hora_str[2:4])
                second = int(hora_str[4:6])
                
                # Create datetime object
                photo_timestamp = datetime(year, month, day, hour, minute, second)
                return photo_timestamp
            except (ValueError, IndexError) as e:
                logger.warning(f"Error parsing timestamp from photo filename {filename}: {e}")
                return None
        
        return None
    
    def _extract_failure_from_photo_filename(self, photo_path: Path) -> bool:
        """
        Extract failure status from photo filename.
        Photo format: {NombreCiclo}-{ID_EC}-{ID_Control}-{Fecha}_{Hora}-{Falla}{PhotoNumber}.bmp
        Where {Falla} is either 'NOK' (failure) or 'OK' (no failure)
        And {PhotoNumber} is an optional integer from 1 to 4 digits (e.g., NOK753, OK123)
        Examples: 
          - COMPLETO-UNO-1F-231225_134953-NOK753.bmp (failure)
          - COMPLETO-UNO-1F-231225_134953-OK123.bmp (no failure)
        Returns True if failure detected (NOK), False otherwise (OK or not found)
        """
        if not photo_path:
            return False
        
        filename = photo_path.name
        filename_upper = filename.upper()
        
        # New format: Check for NOK followed by photo number (1-4 digits)
        # Pattern: -NOK[0-9]{1,4}.ext 
        # Pattern matches: -NOK1, -NOK12, -NOK753, -NOK1234
        # Note: Also supports legacy format without numbers (-NOK.ext) for backward compatibility
        nok_pattern = r'-NOK\d{0,4}\.'
        if re.search(nok_pattern, filename_upper):
            return True
        
        # Check if filename contains -OK followed by photo number (1-4 digits) or legacy format
        # Pattern matches: -OK1, -OK12, -OK123, -OK1234, or legacy -OK.ext
        ok_pattern = r'-OK\d{0,4}\.'
        if re.search(ok_pattern, filename_upper):
            return False
        
        # Legacy format support: Check if filename ends with -NOK.ext or contains -NOK.
        if '-NOK.' in filename_upper or filename_upper.endswith('-NOK.BMP'):
            return True
        
        # Legacy format: Check if filename ends with -OK.ext
        if '-OK.' in filename_upper or filename_upper.endswith('-OK.BMP'):
            return False
        
        # If pattern not found, try to extract from end of filename
        # Pattern: ...-{Falla}{PhotoNumber}.ext where Falla is NOK or OK, PhotoNumber is optional digits
        for ext in ('.bmp', '.jpg', '.jpeg', '.png'):
            if filename.lower().endswith(ext):
                # Remove extension
                name_without_ext = filename[:-len(ext)]
                # Check if it ends with -NOK followed by photo number (0-4 digits for backward compatibility)
                # New format: -NOK123, legacy: -NOK
                if re.search(r'-NOK\d{0,4}$', name_without_ext.upper()):
                    return True
                # Check if it ends with -OK followed by photo number (0-4 digits for backward compatibility)
                # New format: -OK123, legacy: -OK
                elif re.search(r'-OK\d{0,4}$', name_without_ext.upper()):
                    return False
                # Legacy: Check if it ends with -NOK or -OK
                elif name_without_ext.upper().endswith('-NOK'):
                    return True
                elif name_without_ext.upper().endswith('-OK'):
                    return False
                break
        
        # Default: no failure detected if pattern not found
        return False
    
    def _group_raw_rows_by_cycle(self, raw_rows: List[PlcDataRaw], wait_time_seconds: int = 300) -> List[List[PlcDataRaw]]:
        """
        Group raw rows into cycles based on CicloActivo changes.
        Cycle starts when CicloActivo changes to TRUE, ends when it changes to FALSE.
        
        IMPORTANT: Only includes cycles that ended at least wait_time_seconds ago.
        This ensures we wait before processing a cycle (creating inspection, inspection folder,
        and moving photos) to allow photos to arrive in STAGING folder after the inspection ends.
        """
        cycles, current = [], []
        collecting = False
        prev_ciclo_activo = False
        
        # Get current time for comparison
        from django.utils import timezone
        try:
            # Use timezone-aware datetime (Django default)
            now = timezone.now()
        except Exception:
            # Fallback to naive datetime if timezone is not configured
            now = datetime.now()
        
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

                #print('debug collecting')
                #print(is_active)
                #print(data)
                #print(raw.timestamp)

                # End cycle when CicloActivo changes from TRUE to FALSE
                if not is_active and prev_ciclo_activo:
                    # This is the moment when the cycle ended (CicloActivo became False)
                    # We need to wait wait_time_seconds before processing this cycle
                    # (creating inspection, inspection folder, and moving photos)
                    cycle_end_time = raw.timestamp
                    
                    # Ensure both datetimes are in the same format for comparison
                    # Convert cycle_end_time to match now's timezone awareness
                    if cycle_end_time.tzinfo is not None and now.tzinfo is None:
                        # Convert timezone-aware to naive for comparison
                        cycle_end_time = cycle_end_time.replace(tzinfo=None)
                    elif cycle_end_time.tzinfo is None and now.tzinfo is not None:
                        # Convert naive to timezone-aware for comparison
                        # Assume naive datetime is in local timezone
                        cycle_end_time = timezone.make_aware(cycle_end_time)
                    time_since_end = (now - cycle_end_time).total_seconds()
                    
                    # Only process this cycle (add to cycles list) if it ended at least wait_time_seconds ago
                    # This ensures photos have time to arrive in STAGING folder
                    if time_since_end >= wait_time_seconds:
                        # Cycle has waited long enough - add it for processing
                        cycles.append(current)
                        logger.info(
                            f"Ciclo completado hace {time_since_end:.1f} segundos "
                            f"(espera mínima: {wait_time_seconds}s) - Procesando ciclo: "
                            f"crear inspección, carpeta de inspección y mover fotos"
                        )
                    else:
                        # Cycle hasn't waited long enough yet - skip it for now
                        # It will be checked again in the next iteration
                        remaining_wait = wait_time_seconds - time_since_end
                        logger.info(
                            f"Ciclo completado hace {time_since_end:.1f} segundos. "
                            f"Esperando {remaining_wait:.1f} segundos más antes de procesar "
                            f"(crear inspección, carpeta y mover fotos) - para que lleguen fotos a STAGING"
                        )
                    
                    # Reset state for next cycle (whether we processed this one or skipped it)
                    current, collecting = [], False
                    prev_ciclo_activo = False
                elif is_active:
                    prev_ciclo_activo = True
        
        # If still collecting at the end, don't add the current cycle (it hasn't ended yet)
        if collecting and current:
            logger.debug("Ciclo aún activo (CicloActivo=True), no se procesará hasta que CicloActivo cambie a False")
            # Don't add it to cycles - it will be processed in the next iteration after it ends


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
    
    def _next_inspection_suffix(self, nombre_ciclo: str, id_ec: str) -> int:
        """
        Devuelve 0 si no existe ninguna inspección para (nombre_ciclo, id_ec).
        Si ya existe product_code "nombre_ciclo-id_ec", devuelve 1; si existe "nombre_ciclo1-id_ec", devuelve 2; etc.
        Así la nueva inspección se crea como "nombre_ciclo", "nombre_ciclo1", "nombre_ciclo2"...
        """
        suffix_str = "-" + id_ec
        existing = Inspection.objects.filter(
            product_code__startswith=nombre_ciclo,
            product_code__endswith=suffix_str,
        ).values_list('product_code', flat=True)
        max_suffix = -1
        for code in existing:
            middle = code[len(nombre_ciclo):-len(suffix_str)] if len(suffix_str) <= len(code) else ""
            if middle == "":
                max_suffix = max(max_suffix, 0)
            elif middle.isdigit():
                max_suffix = max(max_suffix, int(middle))
        return max_suffix + 1
    
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
        
        # inspection_date = when the PLC cycle physically started.
        # Primary source: the first row's CSV datetime (cycle_rows[0].timestamp) — this is the
        # definitive PLC-recorded start time and avoids date-only fields producing midnight values.
        # Fallback chain: CSV datetime string in JSON → FechaFoto+HoraFoto → now().
        inspection_date = None
        if hasattr(cycle_rows[0], 'timestamp') and cycle_rows[0].timestamp:
            inspection_date = cycle_rows[0].timestamp
            if hasattr(inspection_date, 'replace'):
                # Strip timezone info for naive datetime storage
                try:
                    from django.utils import timezone as tz
                    if hasattr(inspection_date, 'tzinfo') and inspection_date.tzinfo is not None:
                        inspection_date = inspection_date.astimezone().replace(tzinfo=None)
                except Exception:
                    pass

        if not inspection_date:
            datetime_str = first.get('datetime') or first.get('timestamp')
            if datetime_str:
                try:
                    inspection_date = datetime.fromisoformat(datetime_str.replace('Z', '').replace('T', ' '))
                except Exception:
                    pass

        if not inspection_date:
            # Final fallback: FechaFoto+HoraFoto (date from photo filenames)
            fecha_foto = self._get_field_value(first, 'FechaFoto')
            if not fecha_foto:
                fecha_foto = self._find_valid_field_in_cycle(cycle_rows, 'FechaFoto')
            hora_foto = self._get_field_value(first, 'HoraFoto')
            if not hora_foto:
                hora_foto = self._find_valid_field_in_cycle(cycle_rows, 'HoraFoto')
            if fecha_foto and hora_foto and len(fecha_foto) == 6 and len(hora_foto) == 6:
                try:
                    date_str = (
                        f"20{fecha_foto[4:6]}-{fecha_foto[2:4]}-{fecha_foto[0:2]} "
                        f"{hora_foto[0:2]}:{hora_foto[2:4]}:{hora_foto[4:6]}"
                    )
                    inspection_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                except Exception as e:
                    logger.warning(f"Error parsing FechaFoto/HoraFoto: {e}")

        if not inspection_date:
            inspection_date = datetime.now()

        # Read operator name from CSV data (new field in plc_reads_noderead.csv)
        operator_name = self._get_field_value(first, 'operator_name', ['Operador', 'OperadorNombre', 'NombreOperador'])
        if not operator_name:
            operator_name = self._find_valid_field_in_cycle(cycle_rows, 'operator_name', ['Operador', 'OperadorNombre', 'NombreOperador']) or ''
        
        # Build natural key for inspection - group by nombre_ciclo and id_ec
        # Si ya existe una inspección con ese product_code, se agrega un entero al nombre_ciclo
        # Ej: "inspeccion_hoy" existe -> nueva "inspeccion_hoy1", luego "inspeccion_hoy2", etc.
        base_key = f"{nombre_ciclo}-{id_ec}"
        suffix = self._next_inspection_suffix(nombre_ciclo, id_ec)
        if suffix == 0:
            natural_key = base_key
        else:
            natural_key = f"{nombre_ciclo}{suffix}-{id_ec}"
            logger.info(
                f"Product code '{base_key}' ya existe. Creando inspección con product_code='{natural_key}'"
            )
        
        # Check for defects: Falla="1" or "true" means NOK, otherwise OK
        defecto_encontrado = any(
            (self._is_boolean_true(r._parsed_json.get('Falla') or r._parsed_json.get(' Falla'))) or
            (r._parsed_json.get('defecto') == 'NOK')  # fallback for old format
            for r in cycle_rows
        )
        
        defaults = {
            "title": f"Inspección {nombre_ciclo}" + (f" ({suffix})" if suffix > 0 else ""),
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
            "operator_name": operator_name,
            "notes": f"Cycle starting at PLC row {cycle_rows[0].id}",
        }
        
        inspection, created = Inspection.objects.get_or_create(
            product_code=natural_key,
            defaults=defaults,
        )

        # Ensure existing inspections also have an inspector assigned
        if not inspection.inspector and inspector:
            inspection.inspector = inspector
            inspection.save(update_fields=['inspector'])
            logger.info(
                f"Inspector asignado a inspección existente {inspection.id}: {inspector.username}"
            )

        return inspection, created

    def process_cycle(self, cycle_rows: List[PlcDataRaw]) -> bool:
        """
        Procesa un ciclo PLC completo y crea/actualiza la inspección asociada.

        Three-phase approach:
          Pre-phase (outside transaction): unify_photo_png() for all cycle photos.
            SVG overlay is CPU-heavy (~2s/photo) and must NOT run inside a transaction;
            a 200-photo cycle would otherwise hold MySQL locks open for ~6 minutes,
            blocking MySQL Workbench and other connections.
          Phase 1 (atomic): Create Inspection + InspectionPhoto rows in DB only.
          Phase 2 (post-commit): Move files from STAGING to PROCESSED.

        PDF generation is disabled; PDFs are created manually via the web UI.
        """
        # === PRE-PHASE: Image processing (outside transaction) ===
        precomputed_combs = self._preprocess_cycle_photos(cycle_rows)

        # === PHASE 1: Database operations (atomic) ===
        pending_moves = []

        with transaction.atomic():
            inspection, created = self._create_or_fetch_cycle_inspection(cycle_rows)

            if not inspection.inspector:
                default_inspector = self.get_default_inspector()
                inspection.inspector = default_inspector
                inspection.save(update_fields=['inspector'])
                logger.info(
                    f"Inspector asignado a inspección {inspection.id}: {default_inspector.username}"
                )

            attached, pending_moves = self._link_cycle_photos(inspection, cycle_rows, precomputed_combs)

            if attached == 0:
                logger.warning(
                    f"No se encontraron fotos para el ciclo {inspection.product_code}. "
                    "Se marcan las filas como procesadas sin crear inspección."
                )
                PlcDataRaw.objects.filter(
                    id__in=[r.id for r in cycle_rows]
                ).update(processed=True)
                if created:
                    inspection.delete()
                return False

            inspection.status = "completed"
            inspection.completed_date = datetime.now()
            inspection.save()
            logger.info(
                f"Inspección {inspection.id} ({inspection.product_code}) guardada "
                f"con {attached} fotos vinculadas"
            )

            # Load arrow_details from CSV and create ArrowDetail rows
            self._import_arrow_details(inspection, cycle_rows)

            PlcDataRaw.objects.filter(
                id__in=[r.id for r in cycle_rows]
            ).update(processed=True)

        # === PHASE 2: File operations (after DB commit) ===
        self._execute_pending_moves(pending_moves, inspection)

        # === Email: HTML report (BD vs STAGING vs PROCESSED) — non-blocking ===
        try:
            from main.services.inspection_photo_report_email import send_inspection_processed_report_email

            send_inspection_processed_report_email(inspection.id)
        except Exception as e:
            logger.error("Error enviando informe por email de inspección %s: %s", inspection.id, e, exc_info=True)

        # === PHASE 3: Non-critical post-processing ===
        self.update_machine_stats(inspection)

        # Auto-generate PDF and save to media/inspection_reports/
        if attached > 0:
            try:
                from main.views import generate_inspection_pdf_to_file
                logger.info(
                    f"Generando PDF para inspección {inspection.id} ({inspection.product_code})..."
                )
                pdf_bytes, pdf_path = generate_inspection_pdf_to_file(
                    inspection.id, save_to_disk=True
                )
                if pdf_path:
                    logger.info(f"PDF generado automáticamente: {pdf_path}")
                else:
                    logger.warning(f"PDF no pudo guardarse en disco para inspección {inspection.id}")
            except Exception as e:
                logger.error(f"Error generando PDF para inspección {inspection.id}: {e}")

        if attached > 0:
            try:
                from etl.digit_prediction_service import predict_digits_for_inspection
                predictions_made = predict_digits_for_inspection(inspection.id)
                if predictions_made > 0:
                    logger.info(
                        f"Digit predictions for inspection {inspection.id}: "
                        f"{predictions_made}"
                    )
            except ImportError as e:
                logger.warning(f"Digit prediction service not available: {e}")
            except Exception as e:
                logger.error(
                    f"Error in digit prediction for inspection {inspection.id}: {e}"
                )
                import traceback
                logger.error(traceback.format_exc())

        return True

    def _import_arrow_details(self, inspection, cycle_rows: List) -> int:
        """
        Read plc_arrow_nodered.csv and create ArrowDetail rows for this inspection.

        Step 1 — raw save: match CSV rows by NombreCiclo + ID_EC, write each matched
                 row verbatim to PlcArrowReadingRaw (plc_arrow_readings_raw table).
        Step 2 — pivot: for each raw row, unpack the 14 wide columns (F0-Xc/Yc …
                 13-Xc/Yc) into individual ArrowDetail rows (main_arrow_details table).

        CSV header:
            datetime, ID_EC, NombreCiclo,
            F0-Xc, F0-Yc,
            1-Xc, 1-Yc, 2-Xc, 2-Yc, … 13-Xc, 13-Yc

        Returns the number of ArrowDetail rows created.
        """
        try:
            from main.models import ArrowDetail, PlcArrowReadingRaw
            import csv

            plc_dir = Path(__file__).parent / 'NodeRed' / 'plc_reads'
            arrow_csv = plc_dir / 'plc_arrow_nodered.csv'
            if not arrow_csv.exists():
                logger.debug("plc_arrow_nodered.csv not found at %s, skipping arrow import", arrow_csv)
                return 0

            # CSV columns: F0-Xc/F0-Yc … F13-Xc/F13-Yc (all with F prefix).
            ARROW_COLS = [(f'F{i}-Xc', f'F{i}-Yc') for i in range(14)]
            # Corresponding model field names on PlcArrowReadingRaw
            RAW_FIELDS = [
                (f'f{i}_xc', f'f{i}_yc') for i in range(14)
            ]

            def _f(val):
                v = str(val).strip().replace(',', '.')
                try:
                    return float(v) if v else None
                except ValueError:
                    return None

            # Match rows for this inspection by NombreCiclo + ID_EC
            nombre_ciclo = (inspection.batch_number or '').strip()
            id_ec = (inspection.serial_number or '').strip()

            matched_raws = []
            with open(arrow_csv, newline='', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    csv_nombre = row.get('NombreCiclo', row.get(' NombreCiclo', '')).strip()
                    csv_id_ec = row.get('ID_EC', row.get(' ID_EC', '')).strip()
                    if csv_nombre != nombre_ciclo or csv_id_ec != id_ec:
                        continue

                    # Parse datetime
                    raw_dt = None
                    dt_str = row.get('datetime', row.get(' datetime', '')).strip()
                    if dt_str:
                        try:
                            raw_dt = datetime.fromisoformat(dt_str.replace('Z', '').replace('T', ' '))
                        except Exception:
                            pass

                    # Build kwargs for PlcArrowReadingRaw
                    raw_kwargs = {
                        'inspection': inspection,
                        'datetime': raw_dt,
                        'id_ec': csv_id_ec,
                        'nombre_ciclo': csv_nombre,
                        'diametro': _f(row.get('diametro', row.get(' diametro', ''))),
                    }
                    for (xc_col, yc_col), (xc_field, yc_field) in zip(ARROW_COLS, RAW_FIELDS):
                        raw_kwargs[xc_field] = _f(row.get(xc_col, ''))
                        raw_kwargs[yc_field] = _f(row.get(yc_col, ''))

                    matched_raws.append(raw_kwargs)

            if not matched_raws:
                logger.debug(
                    "plc_arrow_nodered.csv: no rows match NombreCiclo=%r ID_EC=%r",
                    nombre_ciclo, id_ec,
                )
                return 0

            # Step 1: save raw rows
            PlcArrowReadingRaw.objects.filter(inspection=inspection).delete()
            raw_records = PlcArrowReadingRaw.objects.bulk_create(
                [PlcArrowReadingRaw(**kw) for kw in matched_raws]
            )
            logger.info(
                "PlcArrowReadingRaw: %d filas guardadas para inspección %s",
                len(raw_records), inspection.id,
            )

            # Step 2: average values per position across all matched CSV rows,
            # then save exactly one ArrowDetail row per position (F0-F13).
            # diametro is a single value per inspection — average it too.
            ArrowDetail.objects.filter(inspection=inspection).delete()
            position_xc: dict = {i: [] for i in range(len(RAW_FIELDS))}
            position_yc: dict = {i: [] for i in range(len(RAW_FIELDS))}
            diametro_vals: list = []
            for raw_kw in matched_raws:
                for i, (xc_field, yc_field) in enumerate(RAW_FIELDS):
                    xc_val = raw_kw.get(xc_field)
                    yc_val = raw_kw.get(yc_field)
                    if xc_val is not None:
                        position_xc[i].append(xc_val)
                    if yc_val is not None:
                        position_yc[i].append(yc_val)
                d = raw_kw.get('diametro')
                if d is not None:
                    diametro_vals.append(d)

            diametro_avg = max(diametro_vals) if diametro_vals else None

            detail_rows = []
            for i in range(len(RAW_FIELDS)):
                xc_avg = sum(position_xc[i]) / len(position_xc[i]) if position_xc[i] else None
                yc_avg = sum(position_yc[i]) / len(position_yc[i]) if position_yc[i] else None
                if xc_avg is not None or yc_avg is not None:
                    detail_rows.append(ArrowDetail(
                        inspection=inspection,
                        xc=xc_avg,
                        yc=yc_avg,
                        diametro=diametro_avg,
                    ))

            if detail_rows:
                ArrowDetail.objects.bulk_create(detail_rows)
                logger.info(
                    "ArrowDetail: %d posiciones (promediadas de %d filas CSV) para inspección %s",
                    len(detail_rows), len(matched_raws), inspection.id,
                )

            return len(detail_rows)

        except Exception as e:
            logger.error("Error importando arrow details para inspección %s: %s", inspection.id, e)
            return 0

    def _link_cycle_photos(self, inspection: Inspection, cycle_rows: List[PlcDataRaw],
                            precomputed_combs: dict = None) -> Tuple[int, List[Tuple[Path, str]]]:
        """
        Phase 1 (DB-only): Scan STAGING for matching PNG photos and insert
        InspectionPhoto rows. Must run inside transaction.atomic().

        Image processing (unify_photo_png) is NOT done here — it was already done
        in _preprocess_cycle_photos() before the transaction opened.
        precomputed_combs: {photo_filename: comb_path_or_None} from that pre-phase.

        Returns:
            (linked_count, pending_moves) where pending_moves is a list of
            (source_path, file_type) tuples to move in Phase 2.
        """
        if precomputed_combs is None:
            precomputed_combs = {}
        linked = 0
        linked_photo_names = set()
        defects_found_in_photos = []
        photo_timestamps = []
        pending_moves: List[Tuple[Path, str]] = []

        inspection_folder_name = inspection.product_code.replace(':', '-').replace('/', '-')

        for raw in cycle_rows:
            payload = raw._parsed_json

            nombre_ciclo = self._get_field_value(payload, 'NombreCiclo', ['nombre_ciclo'])
            id_ec = self._get_field_value(payload, 'ID_EC', ['elemento_combustible'])
            id_value = self._get_field_value(payload, 'ID_Control', ['ID', 'id_puntero', 'PunteroControl'])

            if not nombre_ciclo or not id_ec or not id_value:
                logger.warning(
                    f"Omitiendo fila del ciclo - campos faltantes: "
                    f"NombreCiclo={nombre_ciclo!r}, ID_EC={id_ec!r}, ID_Control={id_value!r}"
                )
                continue

            if "tes" in id_value.lower():
                logger.debug(
                    f"Omitiendo fila del ciclo - ID_Control contiene 'tes': "
                    f"ID_Control={id_value!r}"
                )
                continue

            matching_photos = self._find_staged_photos(payload, exclude_photo_names=linked_photo_names)

            if not matching_photos:
                logger.warning(
                    f"No se encontraron fotos en STAGING para ciclo {nombre_ciclo} "
                    f"ID_Control {id_value} (prefijo: {nombre_ciclo}-{id_ec}-{id_value})"
                )
                continue

            logger.info(
                f"Encontradas {len(matching_photos)} fotos para ciclo {nombre_ciclo} "
                f"ID_Control {id_value}: {[p.name for p in matching_photos]}"
            )

            for photo_path in matching_photos:
                if photo_path.name in linked_photo_names:
                    logger.debug(f"Foto {photo_path.name} ya vinculada, omitiendo duplicado")
                    continue

                linked_photo_names.add(photo_path.name)

                photo_timestamp = self._extract_timestamp_from_photo_filename(photo_path)
                if photo_timestamp:
                    photo_timestamps.append(photo_timestamp)
                    logger.debug(f"Timestamp extraído de {photo_path.name}: {photo_timestamp}")

                defect_from_photo = self._extract_failure_from_photo_filename(photo_path)
                defects_found_in_photos.append(defect_from_photo)

                falla = self._get_field_value(payload, 'Falla')
                if not falla:
                    falla = payload.get('Falla') or payload.get(' Falla', '0')
                defecto_from_csv = self._is_boolean_true(falla) or (payload.get("defecto") == "NOK")
                defecto_encontrado = defect_from_photo or defecto_from_csv

                logger.info(
                    f"Foto {photo_path.name}: defecto_from_photo={defect_from_photo}, "
                    f"defecto_from_csv={defecto_from_csv}, defecto_encontrado={defecto_encontrado}"
                )

                # Use pre-computed combined image (processed before transaction opened)
                comb_path = precomputed_combs.get(photo_path.name)

                # InspectionPhoto references the _comb.png if available, else the original PNG
                if comb_path and comb_path.exists():
                    display_filename = comb_path.name
                else:
                    display_filename = photo_path.name

                relative_path = (
                    f"inspection_photos/PROCESSED/"
                    f"{inspection_folder_name}/{display_filename}"
                )

                InspectionPhoto.objects.create(
                    inspection=inspection,
                    photo=relative_path,
                    caption=f"Ciclo {nombre_ciclo} ID_Control {id_value}",
                    photo_type="plc_cycle",
                    defecto_encontrado=defecto_encontrado,
                )

                # Queue files for Phase 2 move (source PNG, SVG, _comb.png)
                pending_moves.append((photo_path, 'png'))
                svg_path = photo_path.with_suffix('.svg')
                if svg_path.exists():
                    pending_moves.append((svg_path, 'svg'))
                if comb_path and comb_path.exists():
                    pending_moves.append((comb_path, 'comb_png'))

                self.processed_photos.add(photo_path.name)
                linked += 1

        # ── Final sweep ──────────────────────────────────────────────────────────
        # Catch photos that arrived in STAGING after their PLC row was already
        # scanned (late file transfers) or whose row had missing/filtered fields.
        # Uses the inspection's batch_number + serial_number as the broad prefix.
        nombre_ciclo_insp = (inspection.batch_number or '').strip()
        id_ec_insp = (inspection.serial_number or '').strip()
        if nombre_ciclo_insp and id_ec_insp and self.staging_photo_path.exists():
            sweep_prefix = f"{nombre_ciclo_insp}-{id_ec_insp}-"
            late_photos: List[Path] = []
            for ext in (".png", ".bmp", ".jpg", ".jpeg"):
                for photo_file in self.staging_photo_path.glob(f"{sweep_prefix}*{ext}"):
                    if photo_file.stem.endswith('_comb'):
                        continue
                    if photo_file.name not in linked_photo_names:
                        late_photos.append(photo_file)
            late_photos.sort(key=lambda p: p.name)
            if late_photos:
                logger.warning(
                    "Final sweep: encontradas %d fotos no vinculadas para inspección %s: %s",
                    len(late_photos), inspection.product_code,
                    [p.name for p in late_photos],
                )
            for photo_path in late_photos:
                # Re-apply the "tes" guard: the main loop already skips PLC rows
                # whose ID_Control contains "tes", but the final sweep scans by
                # prefix only (NombreCiclo-ID_EC-*) and would otherwise pick up
                # test photos like "Ciclo1-E123-TES1-241225_123456-OK.png".
                prefix_parts = self._extract_prefix_from_photo_filename(photo_path)
                if prefix_parts:
                    _, _, id_control_from_file = prefix_parts
                    if "tes" in id_control_from_file.lower():
                        logger.debug(
                            f"Final sweep: omitiendo foto con ID_Control de prueba "
                            f"'{id_control_from_file}': {photo_path.name}"
                        )
                        continue

                linked_photo_names.add(photo_path.name)
                photo_timestamp = self._extract_timestamp_from_photo_filename(photo_path)
                if photo_timestamp:
                    photo_timestamps.append(photo_timestamp)
                defect_from_photo = self._extract_failure_from_photo_filename(photo_path)
                defects_found_in_photos.append(defect_from_photo)
                comb_path = precomputed_combs.get(photo_path.name)
                display_filename = (comb_path.name if comb_path and comb_path.exists()
                                    else photo_path.name)
                relative_path = (
                    f"inspection_photos/PROCESSED/{inspection_folder_name}/{display_filename}"
                )
                InspectionPhoto.objects.create(
                    inspection=inspection,
                    photo=relative_path,
                    caption=f"Ciclo {nombre_ciclo_insp} (late arrival)",
                    photo_type="plc_cycle",
                    defecto_encontrado=defect_from_photo,
                )
                pending_moves.append((photo_path, 'png'))
                svg_path = photo_path.with_suffix('.svg')
                if svg_path.exists():
                    pending_moves.append((svg_path, 'svg'))
                if comb_path and comb_path.exists():
                    pending_moves.append((comb_path, 'comb_png'))
                self.processed_photos.add(photo_path.name)
                linked += 1
                logger.info(f"Final sweep: foto vinculada -> {photo_path.name}")

        if defects_found_in_photos:
            inspection.defecto_encontrado = any(defects_found_in_photos)
            inspection.save(update_fields=['defecto_encontrado'])
            logger.info(
                f"Inspección {inspection.product_code}: "
                f"defectos en {sum(defects_found_in_photos)} de "
                f"{len(defects_found_in_photos)} fotos"
            )

        if photo_timestamps:
            photo_start = min(photo_timestamps)
            photo_finish = max(photo_timestamps)
            inspection.photo_start_timestamp = photo_start
            inspection.photo_finish_timestamp = photo_finish
            inspection.save(update_fields=['photo_start_timestamp', 'photo_finish_timestamp'])
            logger.info(
                f"Inspección {inspection.product_code}: "
                f"timestamps de fotos - Inicio: {photo_start}, Fin: {photo_finish}"
            )

        return linked, pending_moves

    # ------------------------------------------------------------------
    # Pre-phase helpers: image processing outside transaction
    # ------------------------------------------------------------------

    def _is_file_complete(self, path: Path, min_age_seconds: float = 3.0) -> bool:
        """Return True if the file has not been modified in the last min_age_seconds.
        Prevents reading JPG/PNG files that the camera is still transferring."""
        try:
            age = time.time() - path.stat().st_mtime
            return age >= min_age_seconds
        except OSError:
            return False

    def _safe_unify(self, photo_path: Path) -> Optional[Path]:
        """Run unify_photo_png with a file-completeness check. Returns comb_path or None."""
        if not self._is_file_complete(photo_path):
            logger.warning(
                f"Foto reciente/incompleta (posiblemente en transferencia), "
                f"omitiendo unificacion: {photo_path.name}"
            )
            return None
        try:
            comb = unify_photo_png(photo_path)
            if comb:
                logger.info(f"Imagen combinada creada: {comb.name}")
            else:
                logger.debug(f"Sin SVG para {photo_path.name}, se usara PNG original")
            return comb
        except Exception as e:
            logger.error(f"Error al unificar foto {photo_path.name}: {e}")
            return None

    def _preprocess_cycle_photos(self, cycle_rows: List[PlcDataRaw]) -> dict:
        """
        Pre-phase (outside transaction): find all STAGING photos for this cycle
        and run unify_photo_png() on each one.

        unify_photo_png() takes ~2s per photo (SVG overlay).  Running it inside
        transaction.atomic() would hold MySQL locks open for minutes on large cycles
        (200 photos -> ~6 min), causing 'Too many connections' / SQL Logic Errors in
        MySQL Workbench.  This method must be called before transaction.atomic().

        Returns {photo_filename: comb_path_or_None}.
        """
        combs: dict = {}
        if not self.staging_photo_path.exists():
            return combs

        # Determine NombreCiclo + ID_EC from the cycle rows
        nombre_ciclo = ''
        id_ec = ''
        for raw in cycle_rows:
            payload = getattr(raw, '_parsed_json', {})
            nc = self._get_field_value(payload, 'NombreCiclo', ['nombre_ciclo'])
            ie = self._get_field_value(payload, 'ID_EC', ['elemento_combustible'])
            if nc and ie:
                nombre_ciclo = nc
                id_ec = ie
                break

        if not nombre_ciclo or not id_ec:
            return combs

        # Scan all photos matching the broad prefix (covers main loop + final sweep)
        sweep_prefix = f"{nombre_ciclo}-{id_ec}-"
        candidates: List[Path] = []
        for ext in (".png", ".bmp", ".jpg", ".jpeg"):
            for photo_file in self.staging_photo_path.glob(f"{sweep_prefix}*{ext}"):
                if not photo_file.stem.endswith('_comb'):
                    candidates.append(photo_file)
        candidates.sort(key=lambda p: p.name)

        if candidates:
            logger.info(
                f"Pre-fase imagen: procesando {len(candidates)} fotos para "
                f"{nombre_ciclo}-{id_ec} fuera de la transaccion"
            )
        for photo_path in candidates:
            combs[photo_path.name] = self._safe_unify(photo_path)

        return combs

    def _execute_pending_moves(self, pending_moves: List[Tuple[Path, str]], inspection: Inspection):
        """
        Phase 2: Move files from STAGING to PROCESSED after DB commit.
        Runs outside the transaction so filesystem failures cannot
        roll back InspectionPhoto rows.
        """
        inspection_folder_name = inspection.product_code.replace(':', '-').replace('/', '-')
        inspection_folder = self.processed_photo_path / inspection_folder_name
        inspection_folder.mkdir(parents=True, exist_ok=True)

        moved = 0
        already_at_dest = 0
        for src_path, file_type in pending_moves:
            dest = inspection_folder / src_path.name
            try:
                shutil.move(str(src_path), str(dest))
                moved += 1
                logger.debug(f"Movido {file_type}: {src_path.name} -> {dest}")
            except FileNotFoundError:
                if dest.exists():
                    # A previous run already moved the file — not a real error
                    already_at_dest += 1
                    logger.debug(f"Archivo ya existe en destino (movido previamente): {dest}")
                else:
                    logger.error(
                        f"GHOST FILE: {src_path.name} no existe en STAGING ni en PROCESSED. "
                        f"InspectionPhoto DB record may point to a missing file."
                    )
            except shutil.Error as exc:
                logger.error(f"No se pudo mover {src_path} -> {dest}: {exc}")

        total_accounted = moved + already_at_dest
        if total_accounted < len(pending_moves):
            logger.error(
                f"Phase 2 INCOMPLETE for {inspection.product_code}: "
                f"{total_accounted}/{len(pending_moves)} archivos en destino "
                f"({moved} movidos, {already_at_dest} ya existían). "
                f"{len(pending_moves) - total_accounted} archivos PERDIDOS."
            )
        else:
            logger.info(
                f"Movidos {moved}/{len(pending_moves)} archivos a "
                f"PROCESSED/{inspection_folder_name}/ "
                f"({already_at_dest} ya existían en destino)"
            )

    def _extract_prefix_from_photo_filename(self, photo_path: Path) -> Optional[Tuple[str, str, str]]:
        """
        Extract prefix components from photo filename.
        Photo format: {NombreCiclo}-{ID_EC}-{ID_Control}-{Fecha}_{Hora}-{Falla}{PhotoNumber}.bmp
        Returns tuple (nombre_ciclo, id_ec, id_control) if successful, None otherwise.
        """
        if not photo_path:
            return None
        
        filename = photo_path.stem  # Get filename without extension
        
        # Pattern: First 3 fields separated by dashes
        # Example: COMPLETO-UNO-1F-231225_134953-NOK753 -> COMPLETO, UNO, 1F
        parts = filename.split('-')
        
        if len(parts) >= 3:
            nombre_ciclo = parts[0]
            id_ec = parts[1]
            id_control = parts[2]
            return (nombre_ciclo, id_ec, id_control)
        
        return None

    def _recover_orphaned_photos(self) -> Dict[str, int]:
        """
        Scan STAGING and PROCESSED folders for orphaned photos and attempt to
        match them to existing inspections.

        Matches photos where:
        - Photo prefix (NombreCiclo-ID_EC) matches inspection's product_code
          (uses startswith to handle suffixed product_codes like 'Ciclo1-E123').
        - Photo timestamp is between inspection's photo_start_timestamp and
          photo_finish_timestamp.

        Uses DB-first pattern: create InspectionPhoto row, then move file.
        Files ending in '_comb.png' are excluded (generated output).
        PDF generation is disabled (PDFs are created manually via the web UI).
        """
        recovery_stats = {
            "photos_scanned": 0,
            "photos_matched": 0,
            "photos_linked": 0,
            "errors": 0
        }

        # --- Collect orphan candidates from STAGING ---
        all_orphan_photos = []

        if self.staging_photo_path.exists():
            for ext in (".png", ".bmp", ".jpg", ".jpeg"):
                for f in self.staging_photo_path.glob(f"*{ext}"):
                    if not f.stem.endswith('_comb'):
                        all_orphan_photos.append(('staging', f))

        # --- Collect orphan candidates from PROCESSED sub-folders ---
        if self.processed_photo_path.exists():
            for subfolder in self.processed_photo_path.iterdir():
                if not subfolder.is_dir():
                    continue
                for ext in (".png", ".bmp", ".jpg", ".jpeg"):
                    for f in subfolder.glob(f"*{ext}"):
                        if not f.stem.endswith('_comb'):
                            all_orphan_photos.append(('processed', f))

        recovery_stats["photos_scanned"] = len(all_orphan_photos)
        if not all_orphan_photos:
            return recovery_stats

        logger.info(
            f"Recuperación: escaneando {recovery_stats['photos_scanned']} fotos "
            f"(STAGING + PROCESSED)..."
        )

        processed_photo_names = set()
        try:
            photo_records = InspectionPhoto.objects.all().values_list('photo', flat=True)
            for p in photo_records:
                if p:
                    processed_photo_names.add(Path(p).name)
        except Exception as e:
            logger.warning(f"Error cargando fotos procesadas para recuperación: {e}")

        for source_type, photo_path in all_orphan_photos:
            if photo_path.name in processed_photo_names:
                continue
            if photo_path.name in self.processed_photos:
                continue

            try:
                prefix_parts = self._extract_prefix_from_photo_filename(photo_path)
                if not prefix_parts:
                    continue

                nombre_ciclo, id_ec, id_control = prefix_parts

                if "tes" in id_control.lower():
                    continue

                photo_timestamp = self._extract_timestamp_from_photo_filename(photo_path)
                if not photo_timestamp:
                    continue

                product_code_prefix = f"{nombre_ciclo}-{id_ec}"

                matching_inspections = Inspection.objects.filter(
                    product_code__startswith=nombre_ciclo,
                    product_code__endswith=f"-{id_ec}",
                )

                recovery_stats["photos_matched"] += 1

                from datetime import timedelta
                GRACE = timedelta(minutes=15)  # late-arriving photos tolerance

                matched_inspection = None
                # Pass 1: strict range match
                for insp in matching_inspections:
                    if (insp.photo_start_timestamp and
                            insp.photo_finish_timestamp and
                            insp.photo_start_timestamp <= photo_timestamp <= insp.photo_finish_timestamp):
                        matched_inspection = insp
                        break

                # Pass 2: grace-period match (catches photos that arrived after
                # photo_finish_timestamp was recorded — the root cause of the bug)
                if not matched_inspection:
                    for insp in matching_inspections:
                        if (insp.photo_start_timestamp and
                                insp.photo_finish_timestamp and
                                insp.photo_start_timestamp - GRACE <= photo_timestamp
                                <= insp.photo_finish_timestamp + GRACE):
                            matched_inspection = insp
                            logger.info(
                                f"Foto {photo_path.name} recuperada vía gracia de tiempo "
                                f"(±{GRACE}) → inspección {insp.id}"
                            )
                            break

                # Pass 3: fallback — most-recently-completed inspection for this
                # NombreCiclo+ID_EC when no timestamp is available or range still missed
                if not matched_inspection:
                    fallback = (matching_inspections
                                .filter(status='completed')
                                .order_by('-completed_date')
                                .first())
                    if fallback:
                        matched_inspection = fallback
                        logger.info(
                            f"Foto {photo_path.name} recuperada por fallback a inspección "
                            f"más reciente {fallback.id} ({fallback.product_code})"
                        )

                if not matched_inspection:
                    logger.debug(
                        f"Foto {photo_path.name} no coincide con ninguna inspección "
                        f"(prefijo: {product_code_prefix}, timestamp: {photo_timestamp})"
                    )
                    continue

                logger.info(
                    f"Foto huérfana encontrada: {photo_path.name} -> "
                    f"Inspección {matched_inspection.id} ({matched_inspection.product_code})"
                )

                defect_from_photo = self._extract_failure_from_photo_filename(photo_path)
                inspection_folder_name = matched_inspection.product_code.replace(':', '-').replace('/', '-')

                # Combine PNG + SVG if the file is still in STAGING
                comb_path = None
                if source_type == 'staging':
                    try:
                        comb_path = unify_photo_png(photo_path)
                        if comb_path:
                            logger.debug(f"Imagen combinada creada para recuperación: {comb_path}")
                    except Exception as e:
                        logger.warning(f"Error al combinar foto {photo_path} durante recuperación: {e}")

                if comb_path and comb_path.exists():
                    display_filename = comb_path.name
                else:
                    display_filename = photo_path.name

                relative_path = (
                    f"inspection_photos/PROCESSED/"
                    f"{inspection_folder_name}/{display_filename}"
                )

                # DB first: create the record before moving
                InspectionPhoto.objects.create(
                    inspection=matched_inspection,
                    photo=relative_path,
                    caption=f"Recuperado: Ciclo {nombre_ciclo} ID_Control {id_control}",
                    photo_type="plc_cycle",
                    defecto_encontrado=defect_from_photo,
                )

                # Move files only if they are in STAGING
                if source_type == 'staging':
                    inspection_folder = self.processed_photo_path / inspection_folder_name
                    inspection_folder.mkdir(parents=True, exist_ok=True)

                    files_to_move = [(photo_path, 'png')]
                    svg_path = photo_path.with_suffix('.svg')
                    if svg_path.exists():
                        files_to_move.append((svg_path, 'svg'))
                    if comb_path and comb_path.exists():
                        files_to_move.append((comb_path, 'comb_png'))

                    for file_path, file_type in files_to_move:
                        dest = inspection_folder / file_path.name
                        try:
                            shutil.move(str(file_path), str(dest))
                        except FileNotFoundError:
                            logger.warning(f"Archivo desapareció antes de mover: {file_path}")
                        except shutil.Error as exc:
                            logger.warning(f"No se pudo mover {file_path} -> {dest}: {exc}")

                # Update inspection timestamps if needed
                if (not matched_inspection.photo_start_timestamp or
                        photo_timestamp < matched_inspection.photo_start_timestamp):
                    matched_inspection.photo_start_timestamp = photo_timestamp
                if (not matched_inspection.photo_finish_timestamp or
                        photo_timestamp > matched_inspection.photo_finish_timestamp):
                    matched_inspection.photo_finish_timestamp = photo_timestamp
                matched_inspection.save(update_fields=['photo_start_timestamp', 'photo_finish_timestamp'])

                if defect_from_photo:
                    matched_inspection.defecto_encontrado = True
                    matched_inspection.save(update_fields=['defecto_encontrado'])

                self.processed_photos.add(photo_path.name)
                recovery_stats["photos_linked"] += 1

            except Exception as e:
                recovery_stats["errors"] += 1
                logger.error(f"Error procesando foto huérfana {photo_path.name}: {e}")
                import traceback
                logger.error(traceback.format_exc())

        if recovery_stats["photos_linked"] > 0:
            logger.info(
                f"Recuperación completada: {recovery_stats['photos_linked']} fotos vinculadas "
                f"de {recovery_stats['photos_scanned']} escaneadas"
            )

        return recovery_stats

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
    
    def get_unprocessed_raw_data(self, limit: int = 1000) -> List[PlcDataRaw]:
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
    
    def process_pending_cycles(self, batch_size: int = 5000) -> Dict[str, int]:
        """Agrupa raws PLC en ciclos y crea una inspección por ciclo."""
        summary = {"cycles": 0, "inspections": 0, "errors": 0}

        lock_acquired = _mysql_acquire_plc_cycle_lock_nonblocking()
        if not lock_acquired:
            logger.info(
                "Otra instancia tiene el bloqueo PLC MySQL GET_LOCK(%r); "
                "omitiendo procesamiento de ciclos en esta pasada.",
                MYSQL_PLC_CYCLE_LOCK_NAME,
            )
            return summary

        try:
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
        finally:
            _mysql_release_plc_cycle_lock()
    
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
                
                # Run recovery scan periodically (every 10 cycles = ~5 minutes at 30s interval)
                if cycle_count % 10 == 0:
                    logger.info(f"[Ciclo {cycle_count}] Ejecutando escaneo de recuperación de fotos huérfanas...")
                    recovery_stats = self._recover_orphaned_photos()
                    if recovery_stats["photos_linked"] > 0:
                        logger.info(
                            f"[Ciclo {cycle_count}] Recuperación: {recovery_stats['photos_linked']} fotos vinculadas"
                        )

                if self.is_running:
                    time.sleep(interval_seconds)
                
        except KeyboardInterrupt:
            logger.info("Monitor interrumpido por el usuario")
        except Exception as e:
            logger.error("=" * 80)
            logger.error("ERROR FATAL en monitor de ciclos PLC - El monitor se detuvo por un error")
            logger.error(f"Error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            logger.error("=" * 80)
            logger.error("⚠️  MONITOR DE CICLOS PLC DETENIDO - Reinicie el servidor Django para reactivarlo")
            logger.error("=" * 80)
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
            logger.error("=" * 80)
            logger.error("ERROR FATAL en thread de monitor de ciclos PLC")
            logger.error(f"Error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            logger.error("=" * 80)
            logger.error("⚠️  MONITOR DE CICLOS PLC DETENIDO - Reinicie el servidor Django para reactivarlo")
            logger.error("=" * 80)
    
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
