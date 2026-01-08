#!/usr/bin/env python3
"""
PLC Data Processor - Sistema Conuar

Este script agrupa lecturas PLC en ciclos, busca fotos en el directorio
STAGING que cumplan el patrón
    {NombreCiclo}-{ID_EC}-{ID_Control}-{Fecha formato DDMMYY}_{Hora formato HHMMss}-{Falla}.bmp
    Ejemplo: Ciclo2-E123-3F-041225_154941-NOK.bmp
Las fotos se matchean SOLO por los primeros 3 campos: {NombreCiclo}-{ID_EC}-{ID_Control}
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
    from etl.photo_unificator import unify_photo
except ImportError:
    # If running as standalone script, use relative import
    from photo_unificator import unify_photo

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
            self.base_photo_path = Path(r"C:\Users\USER\Documents\GitHub\Inspection_webapp\Conuar\conuar_webapp\media\inspection_photos")
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
        Full format: {NombreCiclo}-{ID_EC}-{ID_Control}-{Fecha formato DDMMYY}_{Hora formato HHMMss}-{Falla}{PhotoNumber}.bmp
        Example: Ciclo2-E123-3F-041225_154941-NOK753.bmp or COMPLETO-UNO-1F-231225_134953-NOK754.bmp
        
        Args:
            row: Dictionary with PLC data fields
            exclude_photo_names: Set of photo filenames to exclude (already processed)
        
        Returns:
            List of Path objects for all matching photos
        """
        if exclude_photo_names is None:
            exclude_photo_names = set()
        
        try:
            # Build match prefix (first 3 fields only)
            match_prefix = self._build_photo_match_prefix(row)
        except KeyError as exc:
            logger.warning(
                f"Falta campo requerido {exc} en datos PLC para construir prefijo de foto"
            )
            return []

        # Search for photos that start with the match prefix
        # Match pattern: {NombreCiclo}-{ID_EC}-{ID_Control}-...
        if not self.staging_photo_path.exists():
            return []
        
        matching_photos = []
        
        # Try different extensions - collect ALL matching photos
        for ext in (".bmp", ".jpg", ".jpeg", ".png"):
            # Look for files starting with the match prefix
            for photo_file in self.staging_photo_path.glob(f"{match_prefix}-*{ext}"):
                # Verify it matches the pattern (starts with our prefix)
                if photo_file.name.startswith(match_prefix + "-"):
                    # Skip if already processed
                    if photo_file.name not in exclude_photo_names:
                        matching_photos.append(photo_file)
        
        # Also try exact match if no date/time/falla pattern found
        for ext in (".bmp", ".jpg", ".jpeg", ".png"):
            candidate = self.staging_photo_path / f"{match_prefix}{ext}"
            if candidate.exists() and candidate.name not in exclude_photo_names:
                matching_photos.append(candidate)
        
        # Sort by filename for consistent ordering
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
        
        # Build natural key for inspection - group by nombre_ciclo and id_ec only
        # This ensures all cycles for the same cycle name and fuel element are grouped together
        natural_key = f"{nombre_ciclo}-{id_ec}"
        
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
        
        # Note: PDF generation now happens in _link_cycle_photos() after the last photo is processed
        # This ensures the PDF is generated immediately when all photos are linked
        # No need to generate here again to avoid duplicate generation
        
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
        # Track photo timestamps to determine inspection start and finish times
        photo_timestamps = []
        
        # Create inspection folder from inspection's product_code (consistent identifier)
        # Use a sanitized version of product_code as folder name
        inspection_folder_name = inspection.product_code.replace(':', '-').replace('/', '-')
        inspection_folder = self.processed_photo_path / inspection_folder_name
        inspection_folder.mkdir(parents=True, exist_ok=True)
        logger.info(f"Usando carpeta de inspección: {inspection_folder}")
        
        for raw in cycle_rows:
            payload = raw._parsed_json
            
            # Skip rows with missing required fields for photo matching
            nombre_ciclo = self._get_field_value(payload, 'NombreCiclo', ['nombre_ciclo'])
            id_ec = self._get_field_value(payload, 'ID_EC', ['elemento_combustible'])
            id_value = self._get_field_value(payload, 'ID_Control', ['ID', 'id_puntero', 'PunteroControl'])
            
            if not nombre_ciclo or not id_ec or not id_value:
                # Skip this row - missing required fields for photo matching
                logger.warning(
                    f"Omitiendo fila del ciclo - campos faltantes: "
                    f"NombreCiclo={nombre_ciclo!r}, ID_EC={id_ec!r}, ID_Control={id_value!r}"
                )
                continue
            
            # Find ALL matching photos for this prefix (not just the first one)
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
            
            # Process all matching photos
            for photo_path in matching_photos:
                # Skip if we've already linked this photo (should not happen, but safety check)
                if photo_path.name in linked_photo_names:
                    logger.debug(f"Foto {photo_path.name} ya vinculada, omitiendo duplicado")
                    continue
                
                linked_photo_names.add(photo_path.name)
                
                # Extract timestamp from photo filename BEFORE moving
                photo_timestamp = self._extract_timestamp_from_photo_filename(photo_path)
                if photo_timestamp:
                    photo_timestamps.append(photo_timestamp)
                    logger.debug(f"Timestamp extraído de {photo_path.name}: {photo_timestamp}")
                
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

                # Unify photo: overlay SVG on BMP and create PNG
                # This must be done BEFORE moving files, so all files are in STAGING
                png_path = None
                try:
                    logger.info(f"Unificando foto: {photo_path}")
                    png_path = unify_photo(photo_path)
                    if png_path:
                        logger.info(f"Imagen unificada creada: {png_path}")
                    else:
                        logger.warning(f"No se pudo crear imagen unificada para {photo_path}")
                except Exception as e:
                    logger.error(f"Error al unificar foto {photo_path}: {e}")
                    # Continue processing even if unification fails
                
                # Find corresponding SVG file (same name, different extension)
                svg_path = photo_path.with_suffix('.svg')
                if not svg_path.exists():
                    svg_path = None
                
                # Prepare list of files to move: BMP, SVG (if exists), and PNG (if created)
                files_to_move = []
                if photo_path.exists():
                    files_to_move.append((photo_path, 'bmp'))
                if svg_path and svg_path.exists():
                    files_to_move.append((svg_path, 'svg'))
                if png_path and png_path.exists():
                    files_to_move.append((png_path, 'png'))
                
                # Move all related files to inspection-specific folder
                moved_bmp = False
                for file_path, file_type in files_to_move:
                    destination = inspection_folder / file_path.name
                    try:
                        shutil.move(str(file_path), str(destination))
                        logger.debug(f"Movido {file_type.upper()}: {file_path.name} -> {destination}")
                        if file_type == 'bmp':
                            moved_bmp = True
                    except FileNotFoundError:
                        logger.warning(f"El archivo {file_path} desapareció antes de moverlo a PROCESSED")
                    except shutil.Error as exc:
                        logger.warning(f"No se pudo mover {file_path} a {destination}: {exc}")
                
                # Only create InspectionPhoto record if BMP was successfully moved
                if not moved_bmp:
                    logger.warning(f"BMP no fue movido, omitiendo registro de inspección para {photo_path.name}")
                    continue

                # Update relative path to include the inspection folder (use BMP for the record)
                bmp_destination = inspection_folder / photo_path.name
                relative_path = f"inspection_photos/PROCESSED/{inspection_folder.name}/{bmp_destination.name}"
                
                InspectionPhoto.objects.create(
                    inspection=inspection,
                    photo=relative_path,
                    caption=f"Ciclo {nombre_ciclo} ID_Control {id_value}",
                    photo_type="plc_cycle",
                    defecto_encontrado=defecto_encontrado,
                )

                self.processed_photos.add(bmp_destination.name)
                linked += 1
        
        # Update inspection defect status based on photos found
        if defects_found_in_photos:
            inspection.defecto_encontrado = any(defects_found_in_photos)
            inspection.save(update_fields=['defecto_encontrado'])
            logger.info(
                f"Inspección {inspection.product_code}: "
                f"defectos encontrados en {sum(defects_found_in_photos)} de {len(defects_found_in_photos)} fotos"
            )
        
        # Update inspection photo timestamps (start and finish) based on photo filenames
        if photo_timestamps:
            photo_start = min(photo_timestamps)
            photo_finish = max(photo_timestamps)
            inspection.photo_start_timestamp = photo_start
            inspection.photo_finish_timestamp = photo_finish
            inspection.save(update_fields=['photo_start_timestamp', 'photo_finish_timestamp'])
            logger.info(
                f"Inspección {inspection.product_code}: "
                f"timestamps de fotos actualizados - Inicio: {photo_start}, Fin: {photo_finish}"
            )

        # Generate PDF automatically when the last photo is processed
        # This ensures PDF is created immediately after all photos are linked
        if linked > 0:
            try:
                from main.views import generate_inspection_pdf_to_file
                logger.info(
                    f"Última foto procesada para inspección {inspection.id} ({inspection.product_code}). "
                    f"Generando PDF automáticamente..."
                )
                pdf_bytes, pdf_path = generate_inspection_pdf_to_file(inspection.id, save_to_disk=True)
                if pdf_path:
                    logger.info(f"PDF generado y guardado automáticamente: {pdf_path}")
                    logger.info(f"PDF existe en disco: {os.path.exists(pdf_path)}")
                    logger.info(f"Tamaño del PDF: {len(pdf_bytes) if pdf_bytes else 0} bytes")
                else:
                    logger.warning(
                        f"PDF no se pudo guardar para inspección {inspection.id}. "
                        f"Bytes generados: {len(pdf_bytes) if pdf_bytes else 0}"
                    )
            except ImportError as e:
                logger.error(f"Error al importar función de generación de PDF: {e}")
                import traceback
                logger.error(traceback.format_exc())
            except Exception as e:
                logger.error(f"Error generando PDF automáticamente para inspección {inspection.id}: {e}")
                import traceback
                logger.error(traceback.format_exc())

        return linked

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
        Scan STAGING folder for orphaned photos and attempt to match them to existing inspections.
        Only matches photos to inspections where:
        - Photo prefix (NombreCiclo-ID_EC-ID_Control) matches inspection's product_code pattern
        - Photo timestamp is between inspection's photo_start_timestamp and photo_finish_timestamp
        
        Returns:
            Dictionary with recovery statistics
        """
        recovery_stats = {
            "photos_scanned": 0,
            "photos_matched": 0,
            "photos_linked": 0,
            "errors": 0
        }
        
        if not self.staging_photo_path.exists():
            logger.debug("Directorio STAGING no existe, saltando recuperación de fotos huérfanas")
            return recovery_stats
        
        logger.info("Iniciando escaneo de recuperación de fotos huérfanas en STAGING...")
        
        # Get all photos in STAGING that haven't been processed
        all_staging_photos = []
        for ext in (".bmp", ".jpg", ".jpeg", ".png"):
            all_staging_photos.extend(list(self.staging_photo_path.glob(f"*{ext}")))
        
        recovery_stats["photos_scanned"] = len(all_staging_photos)
        logger.info(f"Encontradas {recovery_stats['photos_scanned']} fotos en STAGING para escanear")
        
        # Get all processed photo filenames to exclude
        processed_photo_names = set()
        try:
            photo_records = InspectionPhoto.objects.all().values_list('photo', flat=True)
            for photo_path in photo_records:
                if photo_path:
                    filename = Path(photo_path).name
                    processed_photo_names.add(filename)
        except Exception as e:
            logger.warning(f"Error cargando fotos procesadas para recuperación: {e}")
        
        # Process each photo
        for photo_path in all_staging_photos:
            # Skip if already processed
            if photo_path.name in processed_photo_names:
                continue
            
            # Skip if in our processed_photos set
            if photo_path.name in self.processed_photos:
                continue
            
            try:
                # Extract prefix from photo filename
                prefix_parts = self._extract_prefix_from_photo_filename(photo_path)
                if not prefix_parts:
                    logger.debug(f"No se pudo extraer prefijo de {photo_path.name}, omitiendo")
                    continue
                
                nombre_ciclo, id_ec, id_control = prefix_parts
                
                # Extract timestamp from photo filename
                photo_timestamp = self._extract_timestamp_from_photo_filename(photo_path)
                if not photo_timestamp:
                    logger.debug(f"No se pudo extraer timestamp de {photo_path.name}, omitiendo")
                    continue
                
                # Build product_code pattern (first 2 fields: NombreCiclo-ID_EC)
                # This matches how inspections are created in _create_or_fetch_cycle_inspection
                product_code_pattern = f"{nombre_ciclo}-{id_ec}"
                
                # Find matching inspections by product_code
                matching_inspections = Inspection.objects.filter(
                    product_code=product_code_pattern
                )
                
                recovery_stats["photos_matched"] += 1
                
                # Try to match to an inspection where timestamp is within range
                matched_inspection = None
                for inspection in matching_inspections:
                    # Check if photo timestamp is between inspection's photo timestamps
                    # Both timestamps must exist for strict matching
                    if (inspection.photo_start_timestamp and 
                        inspection.photo_finish_timestamp and
                        inspection.photo_start_timestamp <= photo_timestamp <= inspection.photo_finish_timestamp):
                        matched_inspection = inspection
                        break
                
                if not matched_inspection:
                    logger.debug(
                        f"Foto {photo_path.name} no coincide con ninguna inspección existente "
                        f"(prefijo: {product_code_pattern}, timestamp: {photo_timestamp})"
                    )
                    continue
                
                logger.info(
                    f"Foto huérfana encontrada y vinculada: {photo_path.name} -> "
                    f"Inspección {matched_inspection.id} ({matched_inspection.product_code})"
                )
                
                # Link photo to inspection (similar to _link_cycle_photos logic)
                inspection_folder_name = matched_inspection.product_code.replace(':', '-').replace('/', '-')
                inspection_folder = self.processed_photo_path / inspection_folder_name
                inspection_folder.mkdir(parents=True, exist_ok=True)
                
                # Extract defect status from photo filename
                defect_from_photo = self._extract_failure_from_photo_filename(photo_path)
                
                # Unify photo if needed
                png_path = None
                try:
                    png_path = unify_photo(photo_path)
                    if png_path:
                        logger.debug(f"Imagen unificada creada para recuperación: {png_path}")
                except Exception as e:
                    logger.warning(f"Error al unificar foto {photo_path} durante recuperación: {e}")
                
                # Find corresponding SVG file
                svg_path = photo_path.with_suffix('.svg')
                if not svg_path.exists():
                    svg_path = None
                
                # Move files to inspection folder
                files_to_move = []
                if photo_path.exists():
                    files_to_move.append((photo_path, 'bmp'))
                if svg_path and svg_path.exists():
                    files_to_move.append((svg_path, 'svg'))
                if png_path and png_path.exists():
                    files_to_move.append((png_path, 'png'))
                
                moved_bmp = False
                for file_path, file_type in files_to_move:
                    destination = inspection_folder / file_path.name
                    try:
                        shutil.move(str(file_path), str(destination))
                        if file_type == 'bmp':
                            moved_bmp = True
                    except FileNotFoundError:
                        logger.warning(f"El archivo {file_path} desapareció antes de moverlo durante recuperación")
                    except shutil.Error as exc:
                        logger.warning(f"No se pudo mover {file_path} a {destination} durante recuperación: {exc}")
                
                if not moved_bmp:
                    logger.warning(f"BMP no fue movido durante recuperación, omitiendo registro para {photo_path.name}")
                    continue
                
                # Create InspectionPhoto record
                bmp_destination = inspection_folder / photo_path.name
                relative_path = f"inspection_photos/PROCESSED/{inspection_folder.name}/{bmp_destination.name}"
                
                InspectionPhoto.objects.create(
                    inspection=matched_inspection,
                    photo=relative_path,
                    caption=f"Recuperado: Ciclo {nombre_ciclo} ID_Control {id_control}",
                    photo_type="plc_cycle",
                    defecto_encontrado=defect_from_photo,
                )
                
                # Update inspection timestamps if needed
                if (not matched_inspection.photo_start_timestamp or 
                    photo_timestamp < matched_inspection.photo_start_timestamp):
                    matched_inspection.photo_start_timestamp = photo_timestamp
                
                if (not matched_inspection.photo_finish_timestamp or 
                    photo_timestamp > matched_inspection.photo_finish_timestamp):
                    matched_inspection.photo_finish_timestamp = photo_timestamp
                
                matched_inspection.save(update_fields=['photo_start_timestamp', 'photo_finish_timestamp'])
                
                # Update inspection defect status if photo shows defect
                if defect_from_photo:
                    matched_inspection.defecto_encontrado = True
                    matched_inspection.save(update_fields=['defecto_encontrado'])
                
                # Generate PDF automatically after recovering orphaned photo
                # This ensures PDF is updated when new photos are linked to existing inspections
                try:
                    from main.views import generate_inspection_pdf_to_file
                    logger.info(
                        f"Foto huérfana vinculada a inspección {matched_inspection.id}. "
                        f"Regenerando PDF automáticamente..."
                    )
                    pdf_bytes, pdf_path = generate_inspection_pdf_to_file(matched_inspection.id, save_to_disk=True)
                    if pdf_path:
                        logger.info(f"PDF regenerado y guardado: {pdf_path}")
                    else:
                        logger.warning(f"PDF no se pudo regenerar para inspección {matched_inspection.id}")
                except Exception as e:
                    logger.warning(f"Error regenerando PDF después de recuperar foto huérfana: {e}")
                    # Don't fail recovery if PDF generation fails
                
                self.processed_photos.add(bmp_destination.name)
                recovery_stats["photos_linked"] += 1
                
            except Exception as e:
                recovery_stats["errors"] += 1
                logger.error(f"Error procesando foto huérfana {photo_path.name}: {e}")
                import traceback
                logger.error(traceback.format_exc())
        
        if recovery_stats["photos_linked"] > 0:
            logger.info(
                f"Recuperación completada: {recovery_stats['photos_linked']} fotos vinculadas de "
                f"{recovery_stats['photos_scanned']} escaneadas"
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
