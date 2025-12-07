#!/usr/bin/env python3
"""
PLC Data Processor - Sistema Conuar

Este script agrupa lecturas PLC en ciclos, busca fotos en el directorio
STAGING que cumplan el patrón
    {nombre_ciclo}_{elemento_combustible}_{id_puntero}_{photo_date}_{photo_time}_{defecto}{photo_code}.bmp
    Ejemplo: Ciclo2_E123_3.1_041225_154941_NOK{105}.bmp
y crea una única inspección por ciclo. Cada foto utilizada se mueve a
PROCESSED y se vincula a la inspección resultante.

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

    def _build_staging_filename(self, row: dict) -> str:
        """
        Build filename in new format:
        {nombre_ciclo}_{elemento_combustible}_{id_puntero}_{photo_date}_{photo_time}_{defecto}{photo_code}.bmp
        Example: Ciclo2_E123_3.1_041225_154941_NOK{105}.bmp
        """
        try:
            nombre_ciclo = row.get('nombre_ciclo', '')
            elemento_combustible = row.get('elemento_combustible', '')
            id_puntero = str(row.get('id_puntero', ''))  # Ensure it's a string
            photo_date = row.get('photo_date', '')
            photo_time = row.get('photo_time', '')
            defecto = row.get('defecto', 'OK')
            photo_code = row.get('photo_code', '')
            
            # Build filename with photo_code in curly braces
            if photo_code:
                return f"{nombre_ciclo}_{elemento_combustible}_{id_puntero}_{photo_date}_{photo_time}_{defecto}{{{photo_code}}}"
            else:
                return f"{nombre_ciclo}_{elemento_combustible}_{id_puntero}_{photo_date}_{photo_time}_{defecto}"
        except KeyError as exc:
            logger.warning(
                f"Falta campo requerido {exc} en datos PLC para construir nombre de foto"
            )
            raise

    def _find_staged_photo(self, row: dict) -> Optional[Path]:
        """
        Find photo in STAGING folder matching the new naming pattern.
        Format: {nombre_ciclo}_{elemento_combustible}_{id_puntero}_{photo_date}_{photo_time}_{defecto}{photo_code}.bmp
        """
        try:
            base_name = self._build_staging_filename(row)
        except KeyError as exc:
            logger.warning(
                f"Falta campo requerido {exc} en datos PLC para construir nombre de foto"
            )
            return None

        # Try .bmp first (as per new format), then other extensions for backward compatibility
        for ext in (".bmp", ".jpg", ".jpeg", ".png"):
            candidate = self.staging_photo_path / f"{base_name}{ext}"
            if candidate.exists():
                return candidate
        return None

    def _group_raw_rows_by_cycle(self, raw_rows: List[PlcDataRaw]) -> List[List[PlcDataRaw]]:
        cycles, current = [], []
        collecting = False
        for raw in raw_rows:
            data = json.loads(raw.json_data)
            bit = data.get("bit_inicio_ciclo")
            if bit == "1" and not collecting:
                collecting = True
                current = []
            if collecting:
                raw._parsed_json = data  # cache for later
                current.append(raw)
                if bit == "0":
                    cycles.append(current)
                    current, collecting = [], False
        if collecting and current:
            cycles.append(current)
        return cycles

    def _create_or_fetch_cycle_inspection(self, cycle_rows: List[PlcDataRaw]) -> Tuple[Inspection, bool]:
        first = cycle_rows[0]._parsed_json
        inspector = self.get_default_inspector()
        natural_key = f"{first['nombre_ciclo']}-{first['elemento_combustible']}-{first['datetime']}"
        inspection, created = Inspection.objects.get_or_create(
            product_code=natural_key,
            defaults={
                "title": f"Inspección {first['nombre_ciclo']}",
                "description": f"Inspección {first['nombre_ciclo']} del elemento combustible {first['elemento_combustible']}",
                "tipo_combustible": "uranio",
                "status": "in_progress",
                "defecto_encontrado": any(r._parsed_json.get('defecto') == 'NOK' for r in cycle_rows),
                "product_name": first.get('nombre_ubicacion') or "Línea Conuar",
                "serial_number": first["elemento_combustible"],
                "batch_number": first["nombre_ciclo"],
                "location": first.get("pos_camara", ""),
                "inspection_date": datetime.fromisoformat(first["datetime"].replace('Z','').replace('T',' ')),
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
        inspection.defecto_encontrado = any(r._parsed_json.get('defecto') == 'NOK' for r in cycle_rows)
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
                logger.warning(
                    f"No se encontró foto en STAGING para ciclo {payload.get('nombre_ciclo')} "
                    f"puntero {payload.get('id_puntero')}"
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
            InspectionPhoto.objects.create(
                inspection=inspection,
                photo=relative_path,
                caption=f"Ciclo {payload['nombre_ciclo']} puntero {payload['id_puntero']}",
                photo_type="plc_cycle",
                defecto_encontrado=payload.get("defecto") == "NOK",
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
