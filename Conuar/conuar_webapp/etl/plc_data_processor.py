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
        self.staging_photo_path = self.base_photo_path / "STAGING"
        self.processed_photo_path = self.base_photo_path / "PROCESSED"
        if not self.staging_photo_path.exists():
            logger.warning(f"Directorio STAGING no existe: {self.staging_photo_path}")
        self.processed_photo_path.mkdir(parents=True, exist_ok=True)

        # Track processed photos to avoid reprocessing
        self.processed_photos: set = set()
        
        # Load existing processed photos from database
        self._load_processed_photos()

    def _build_photo_match_prefix(self, row: dict) -> str:
        """
        Build the matching prefix for photos (first 3 fields only):
        {NombreCiclo}-{ID_EC}-{ID}
        This is used to match photos regardless of date/time/falla values.
        """
        try:
            # Handle field names with/without leading spaces
            nombre_ciclo = row.get('NombreCiclo') or row.get(' NombreCiclo', '').strip()
            id_ec = row.get('ID_EC') or row.get(' ID_EC', '').strip()
            # ID is PunteroControl
            id_value = str(row.get('PunteroControl') or row.get(' PunteroControl', '')).strip()
            
            if not nombre_ciclo or not id_ec or not id_value:
                raise KeyError("Missing required fields for photo matching")
            
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

    def _create_or_fetch_cycle_inspection(self, cycle_rows: List[PlcDataRaw]) -> Tuple[Inspection, bool]:
        first = cycle_rows[0]._parsed_json
        inspector = self.get_default_inspector()
        
        # Get values using new field names, with fallback to old names for compatibility
        # Handle field names with/without leading spaces
        nombre_ciclo = (first.get('NombreCiclo') or first.get(' NombreCiclo', '') or 
                       first.get('nombre_ciclo', '')).strip()
        id_ec = (first.get('ID_EC') or first.get(' ID_EC', '') or 
                first.get('elemento_combustible', '')).strip()
        
        # Build datetime from FechaFoto and HoraFoto, or use timestamp from database
        # Handle field names with/without leading spaces
        fecha_foto = (first.get('FechaFoto') or first.get(' FechaFoto', '')).strip()
        hora_foto = (first.get('HoraFoto') or first.get(' HoraFoto', '')).strip()
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
        # Check for defects: Falla="1" or "true" means NOK, otherwise OK
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
        for raw in cycle_rows:
            payload = raw._parsed_json
            photo_path = self._find_staged_photo(payload)
            if not photo_path:
                nombre_ciclo = (payload.get('NombreCiclo') or payload.get(' NombreCiclo', '') or 
                               payload.get('nombre_ciclo', '')).strip()
                puntero = (payload.get('PunteroControl') or payload.get(' PunteroControl', '') or 
                          payload.get('id_puntero', '')).strip()
                logger.warning(
                    f"No se encontró foto en STAGING para ciclo {nombre_ciclo} "
                    f"ID {puntero}"
                )
                continue

            destination = self.processed_photo_path / photo_path.name
            try:
                shutil.move(str(photo_path), str(destination))
            except FileNotFoundError:
                logger.warning(f"La foto {photo_path} desapareció antes de moverla a PROCESSED")
                continue
            except shutil.Error as exc:
                logger.warning(f"No se pudo mover {photo_path} a {destination}: {exc}")
                continue

            relative_path = f"inspection_photos/PROCESSED/{destination.name}"
            nombre_ciclo = (payload.get('NombreCiclo') or payload.get(' NombreCiclo', '') or 
                           payload.get('nombre_ciclo', '')).strip()
            puntero = (payload.get('PunteroControl') or payload.get(' PunteroControl', '') or 
                      payload.get('id_puntero', '')).strip()
            # Check for defect: Falla="1" or "true" means NOK
            falla = payload.get('Falla') or payload.get(' Falla', '0')
            defecto_encontrado = self._is_boolean_true(falla) or (payload.get("defecto") == "NOK")
            
            InspectionPhoto.objects.create(
                inspection=inspection,
                photo=relative_path,
                caption=f"Ciclo {nombre_ciclo} puntero {puntero}",
                photo_type="plc_cycle",
                defecto_encontrado=defecto_encontrado,
            )

            self.processed_photos.add(destination.name)
            linked += 1

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
