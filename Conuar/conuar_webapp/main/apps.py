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
        if os.environ.get('RUN_MAIN') != 'true' and 'runserver' in sys.argv:
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
            
            # ============================================================
            # STEP 1: Load initial CSV data
            # ============================================================
            try:
                from etl.plc_data_reader import load_csv_data_to_db, start_background_monitor as start_csv_monitor
            except ImportError as ie:
                logger.error(f"Failed to import plc_data_reader: {ie}")
                return
            
            logger.info("=" * 60)
            logger.info("Django Startup: Loading initial PLC data...")
            logger.info("=" * 60)
            
            # Load initial data
            result = load_csv_data_to_db()
            
            if result.get('success'):
                new_records = result.get('new_records', 0)
                if new_records > 0:
                    logger.info(f"[SUCCESS] {new_records} nuevos registros PLC cargados")
                else:
                    logger.info("[INFO] No hay nuevos registros PLC para cargar")
            else:
                logger.warning(f"[WARNING] Error cargando datos PLC: {result.get('message')}")
            
            # ============================================================
            # STEP 2: Start CSV monitor (background thread)
            # ============================================================
            try:
                logger.info("Iniciando monitor de CSV en background...")
                csv_thread = start_csv_monitor(interval_seconds=30)
                logger.info("[SUCCESS] Monitor de CSV iniciado - verificará nuevos datos cada 30 segundos")
            except Exception as e:
                logger.error(f"Error iniciando monitor de CSV: {e}")
            
            # ============================================================
            # STEP 3: Start photo processor (background thread)
            # ============================================================
            try:
                from etl.plc_data_processor import start_background_monitor as start_photo_monitor
                
                logger.info("Iniciando monitor de fotos en background...")
                photo_thread = start_photo_monitor(interval_seconds=30)
                logger.info("[SUCCESS] Monitor de fotos iniciado - creará inspecciones cada 30 segundos")
            except ImportError as ie:
                logger.error(f"Failed to import plc_data_processor: {ie}")
            except Exception as e:
                logger.error(f"Error iniciando monitor de fotos: {e}")
            
            logger.info("=" * 60)
            logger.info("Sistema Conuar iniciado completamente")
            logger.info("  - Monitor CSV: Activo (cada 30s)")
            logger.info("  - Monitor Fotos: Activo (cada 30s)")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Error during startup: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Don't prevent Django from starting even if this fails
            pass
