from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class MainConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'main'
    
    def ready(self):
        """
        Called when Django starts:
        1. Loads initial PLC data from CSV
        2. Starts background CSV monitor (reads new data every 30s)
        3. Starts background photo processor (creates inspections for new photos every 30s)
        """
        # Import here to avoid AppRegistryNotReady error
        import os
        import sys
        
        # Only run in the main process, not in reloader processes
        # Check for both RUN_MAIN and if we're using runserver
        is_runserver = 'runserver' in sys.argv
        is_main_process = os.environ.get('RUN_MAIN') == 'true'
        
        # Skip if using runserver but not in main process (reloader)
        if is_runserver and not is_main_process:
            logger.debug("Skipping startup in reloader process")
            return
        
        # Also skip if not using runserver (e.g., migrations, shell, etc.)
        # But allow it for other commands that might need it
        if not is_runserver and 'migrate' in sys.argv:
            logger.debug("Skipping startup during migrations")
            return
        
        try:
            # Import the modules from etl
            from pathlib import Path
            
            # Get the path to the ETL directory (parent of main app)
            base_dir = Path(__file__).resolve().parent.parent
            etl_module_path = base_dir / 'etl'
            
            # Add ETL directory to sys.path if not already there
            if str(etl_module_path.parent) not in sys.path:
                sys.path.insert(0, str(etl_module_path.parent))
            
            logger.info("=" * 60)
            logger.info("Django Startup: Initializing Conuar ETL System...")
            logger.info("=" * 60)
            
            # ============================================================
            # STEP 1: Load initial CSV data
            # ============================================================
            try:
                from etl.plc_data_reader import load_csv_data_to_db, start_background_monitor as start_csv_monitor
                logger.info("✓ Successfully imported plc_data_reader")
            except ImportError as ie:
                logger.error(f"✗ Failed to import plc_data_reader: {ie}")
                import traceback
                logger.error(traceback.format_exc())
                return
            except Exception as e:
                logger.error(f"✗ Error importing plc_data_reader: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return
            
            logger.info("Loading initial PLC data from CSV...")
            
            # Load initial data
            try:
                result = load_csv_data_to_db()
                
                if result.get('success'):
                    new_records = result.get('new_records', 0)
                    if new_records > 0:
                        logger.info(f"✓ {new_records} nuevos registros PLC cargados")
                    else:
                        logger.info("✓ No hay nuevos registros PLC para cargar (ya están en la base de datos)")
                else:
                    logger.warning(f"⚠ Error cargando datos PLC: {result.get('message')}")
            except Exception as e:
                logger.error(f"✗ Error durante carga inicial de datos: {e}")
                import traceback
                logger.error(traceback.format_exc())
            
            # ============================================================
            # STEP 2: Start CSV monitor (background thread)
            # ============================================================
            csv_thread = None
            try:
                logger.info("Iniciando monitor de CSV en background...")
                csv_thread = start_csv_monitor(interval_seconds=30)
                if csv_thread and csv_thread.is_alive():
                    logger.info("✓ Monitor de CSV iniciado - verificará nuevos datos cada 30 segundos")
                else:
                    logger.error("✗ Monitor de CSV no se inició correctamente")
            except Exception as e:
                logger.error(f"✗ Error iniciando monitor de CSV: {e}")
                import traceback
                logger.error(traceback.format_exc())
            
            # ============================================================
            # STEP 3: Start photo processor (background thread)
            # ============================================================
            photo_thread = None
            try:
                from etl.plc_data_processor import start_background_monitor as start_photo_monitor
                logger.info("✓ Successfully imported plc_data_processor")
                
                logger.info("Iniciando monitor de fotos en background...")
                photo_thread = start_photo_monitor(interval_seconds=30)
                if photo_thread and photo_thread.is_alive():
                    logger.info("✓ Monitor de fotos iniciado - creará inspecciones cada 30 segundos")
                else:
                    logger.error("✗ Monitor de fotos no se inició correctamente")
            except ImportError as ie:
                logger.error(f"✗ Failed to import plc_data_processor: {ie}")
                import traceback
                logger.error(traceback.format_exc())
            except Exception as e:
                logger.error(f"✗ Error iniciando monitor de fotos: {e}")
                import traceback
                logger.error(traceback.format_exc())
            
            logger.info("=" * 60)
            logger.info("Sistema Conuar iniciado completamente")
            logger.info(f"  - Monitor CSV: {'✓ Activo' if csv_thread and csv_thread.is_alive() else '✗ Inactivo'} (cada 30s)")
            logger.info(f"  - Monitor Fotos: {'✓ Activo' if photo_thread and photo_thread.is_alive() else '✗ Inactivo'} (cada 30s)")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"✗ Error crítico durante startup: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Don't prevent Django from starting even if this fails
            pass
