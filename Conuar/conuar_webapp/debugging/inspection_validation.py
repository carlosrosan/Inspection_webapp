#!/usr/bin/env python3
"""
Inspection Validation Script - Sistema Conuar

This script validates why an inspection might not be created by checking:
1. CSV data presence and format
2. Database PlcDataRaw records
3. Cycle detection (CicloActivo transitions)
4. Photo matching in STAGING folder
5. Existing inspections in database
6. Wait time requirements
7. "tes" exclusion patterns

Usage:
    python inspection_validation.py <NombreCiclo> <ID_EC>
    
Example:
    python inspection_validation.py CNA2 E3742
"""

import os
import sys
import csv
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Django setup (same as plc_data_processor.py)
try:
    import django
    django.apps.apps.check_apps_ready()
except Exception:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()

from django.utils import timezone

# Import Django models
try:
    from main.models import PlcDataRaw, Inspection, InspectionPhoto, InspectionMachine, User
except ImportError as e:
    print(f"[ERROR] Could not import Django models: {e}")
    print("Make sure you're running this from the correct Django project directory")
    sys.exit(1)

# Path configuration (same as plc_data_processor.py)
try:
    from config.paths_config import (
        INSPECTION_PHOTOS_DIR,
        INSPECTION_PHOTOS_STAGING_DIR,
        INSPECTION_PHOTOS_PROCESSED_DIR,
    )
    STAGING_PATH = Path(INSPECTION_PHOTOS_STAGING_DIR)
    PROCESSED_PATH = Path(INSPECTION_PHOTOS_PROCESSED_DIR)
    BASE_PHOTO_PATH = Path(INSPECTION_PHOTOS_DIR)
except ImportError:
    BASE_PHOTO_PATH = Path(r"C:\Users\USER\Documents\GitHub\Inspection_webapp\Conuar\conuar_webapp\media\inspection_photos")
    STAGING_PATH = BASE_PHOTO_PATH / "STAGING"
    PROCESSED_PATH = BASE_PHOTO_PATH / "PROCESSED"

# CSV file path (same directory as this script)
#CSV_PATH = Path(__file__).parent / "plc_reads_nodered.csv"
CSV_PATH =  Path(r"C:\Users\USER\Documents\GitHub\Inspection_webapp\Conuar\conuar_webapp\etl\NodeRed\plc_reads\plc_reads_nodered.csv")


class ValidationResult:
    """Stores validation check results"""
    def __init__(self, check_name: str, passed: bool, message: str, details: dict = None):
        self.check_name = check_name
        self.passed = passed
        self.message = message
        self.details = details or {}
    
    def __str__(self):
        status = "✅ PASS" if self.passed else "❌ FAIL"
        return f"{status} | {self.check_name}: {self.message}"


class InspectionValidator:
    """Validates why inspections might not be created"""
    
    WAIT_TIME_SECONDS = 300  # Same as plc_data_processor.py
    
    def __init__(self, nombre_ciclo: str, id_ec: str):
        self.nombre_ciclo = nombre_ciclo
        self.id_ec = id_ec
        self.product_code = f"{nombre_ciclo}-{id_ec}"
        self.results: List[ValidationResult] = []
        
        # Data collected during validation
        self.csv_rows: List[dict] = []
        self.db_raw_records: List[PlcDataRaw] = []
        self.staging_photos: List[Path] = []
        self.processed_photos: List[Path] = []
        self.existing_inspections: List[Inspection] = []
        self.existing_inspection_photos: List[InspectionPhoto] = []
    
    def add_result(self, check_name: str, passed: bool, message: str, details: dict = None):
        result = ValidationResult(check_name, passed, message, details)
        self.results.append(result)
        return result
    
    def run_all_validations(self):
        """Run all validation checks"""
        print("=" * 80)
        print(f"INSPECTION VALIDATION REPORT")
        print(f"NombreCiclo: {self.nombre_ciclo}")
        print(f"ID_EC: {self.id_ec}")
        print(f"Product Code: {self.product_code}")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        print()
        
        # Run all checks
        self._check_csv_data()
        self._check_database_raw_records()
        self._check_cycle_detection()
        self._check_wait_time()
        self._check_staging_photos()
        self._check_processed_photos()
        self._check_existing_inspections()
        self._check_existing_inspection_photos()
        self._check_photo_filename_matching()
        self._check_tes_exclusion()
        self._check_required_fields()
        
        # Print summary
        self._print_summary()
    
    def _check_csv_data(self):
        """Check 1: Verify data exists in CSV file"""
        print("\n" + "-" * 40)
        print("CHECK 1: CSV Data Presence")
        print("-" * 40)
        
        if not CSV_PATH.exists():
            self.add_result(
                "CSV File Exists",
                False,
                f"CSV file not found at: {CSV_PATH}"
            )
            return
        
        self.add_result("CSV File Exists", True, f"Found at: {CSV_PATH}")
        
        # Read and parse CSV
        matching_rows = []
        total_rows = 0
        
        try:
            with open(CSV_PATH, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    total_rows += 1
                    # Check if row matches our NombreCiclo and ID_EC
                    row_nombre = row.get('NombreCiclo', '').strip()
                    row_id_ec = row.get('ID_EC', '').strip()
                    
                    if row_nombre == self.nombre_ciclo and row_id_ec == self.id_ec:
                        matching_rows.append(row)
        except Exception as e:
            self.add_result("CSV Parse", False, f"Error parsing CSV: {e}")
            return
        
        self.csv_rows = matching_rows
        
        if matching_rows:
            self.add_result(
                "CSV Data Match",
                True,
                f"Found {len(matching_rows)} rows matching {self.product_code} (out of {total_rows} total)",
                {"row_count": len(matching_rows), "total_rows": total_rows}
            )
            
            # Show sample of ID_Control values
            id_controls = set()
            for row in matching_rows:
                id_control = row.get('ID_Control', '').strip()
                if id_control:
                    id_controls.add(id_control)
            
            print(f"   ID_Control values found: {len(id_controls)}")
            if len(id_controls) <= 20:
                print(f"   Sample: {sorted(id_controls)[:20]}")
            else:
                print(f"   Sample (first 20): {sorted(id_controls)[:20]}...")
        else:
            self.add_result(
                "CSV Data Match",
                False,
                f"No rows found matching NombreCiclo={self.nombre_ciclo}, ID_EC={self.id_ec}",
                {"searched_rows": total_rows}
            )
    
    def _check_database_raw_records(self):
        """Check 2: Verify data exists in PlcDataRaw database table"""
        print("\n" + "-" * 40)
        print("CHECK 2: Database PlcDataRaw Records")
        print("-" * 40)
        
        try:
            # Query all PlcDataRaw records
            all_records = PlcDataRaw.objects.all().order_by('timestamp')
            total_count = all_records.count()
            
            self.add_result(
                "Database Connection",
                True,
                f"Connected successfully. Total PlcDataRaw records: {total_count}"
            )
            
            if total_count == 0:
                self.add_result(
                    "Database Has Data",
                    False,
                    "PlcDataRaw table is EMPTY! CSV data needs to be imported."
                )
                return
            
            # Search for matching records
            matching_records = []
            unprocessed_count = 0
            processed_count = 0
            
            for record in all_records:
                try:
                    data = json.loads(record.json_data)
                    row_nombre = data.get('NombreCiclo', data.get(' NombreCiclo', '')).strip() if isinstance(data.get('NombreCiclo', data.get(' NombreCiclo', '')), str) else ''
                    row_id_ec = data.get('ID_EC', data.get(' ID_EC', '')).strip() if isinstance(data.get('ID_EC', data.get(' ID_EC', '')), str) else ''
                    
                    if row_nombre == self.nombre_ciclo and row_id_ec == self.id_ec:
                        matching_records.append(record)
                        record._parsed_json = data  # Cache for later use
                        if record.processed:
                            processed_count += 1
                        else:
                            unprocessed_count += 1
                except (json.JSONDecodeError, AttributeError):
                    continue
            
            self.db_raw_records = matching_records
            
            if matching_records:
                self.add_result(
                    "Database Records Match",
                    True,
                    f"Found {len(matching_records)} records matching {self.product_code}",
                    {
                        "total": len(matching_records),
                        "processed": processed_count,
                        "unprocessed": unprocessed_count
                    }
                )
                print(f"   Processed: {processed_count}, Unprocessed: {unprocessed_count}")
                
                if unprocessed_count == 0 and processed_count > 0:
                    print(f"   ⚠️  All records already processed - inspection may already exist")
            else:
                self.add_result(
                    "Database Records Match",
                    False,
                    f"No records found in PlcDataRaw matching {self.product_code}. "
                    f"CSV data needs to be imported into the database!",
                    {"total_in_db": total_count}
                )
                
        except Exception as e:
            self.add_result(
                "Database Query",
                False,
                f"Error querying database: {e}"
            )
    
    def _check_cycle_detection(self):
        """Check 3: Verify cycle detection (CicloActivo transitions)"""
        print("\n" + "-" * 40)
        print("CHECK 3: Cycle Detection (CicloActivo)")
        print("-" * 40)
        
        # Check in CSV data
        if self.csv_rows:
            ciclo_activo_values = []
            for row in self.csv_rows:
                ciclo_val = row.get('CicloActivo', '').strip().lower()
                ciclo_activo_values.append(ciclo_val)
            
            true_count = sum(1 for v in ciclo_activo_values if v == 'true')
            false_count = sum(1 for v in ciclo_activo_values if v == 'false')
            
            # Check for cycle completion (TRUE -> FALSE transition)
            has_cycle_start = 'true' in ciclo_activo_values
            has_cycle_end = 'false' in ciclo_activo_values
            
            # Find the transition point
            cycle_ended = False
            for i in range(1, len(ciclo_activo_values)):
                if ciclo_activo_values[i-1] == 'true' and ciclo_activo_values[i] == 'false':
                    cycle_ended = True
                    break
            
            if cycle_ended:
                self.add_result(
                    "Cycle Completion (CSV)",
                    True,
                    f"Cycle completed (CicloActivo: TRUE → FALSE transition found)",
                    {"true_count": true_count, "false_count": false_count}
                )
            elif has_cycle_start and not has_cycle_end:
                self.add_result(
                    "Cycle Completion (CSV)",
                    False,
                    f"Cycle NOT completed - CicloActivo never became FALSE. "
                    f"(TRUE: {true_count}, FALSE: {false_count})"
                )
            elif not has_cycle_start:
                self.add_result(
                    "Cycle Completion (CSV)",
                    False,
                    f"Cycle never started - CicloActivo never became TRUE"
                )
            else:
                self.add_result(
                    "Cycle Completion (CSV)",
                    False,
                    f"Unexpected cycle state. TRUE: {true_count}, FALSE: {false_count}"
                )
            
            print(f"   CicloActivo=true: {true_count}, CicloActivo=false: {false_count}")
        
        # Check in database records
        if self.db_raw_records:
            db_cycle_values = []
            for record in self.db_raw_records:
                data = record._parsed_json
                ciclo_val = data.get('CicloActivo', data.get(' CicloActivo', False))
                if isinstance(ciclo_val, bool):
                    db_cycle_values.append(ciclo_val)
                elif isinstance(ciclo_val, str):
                    db_cycle_values.append(ciclo_val.lower() == 'true')
            
            db_true = sum(db_cycle_values)
            db_false = len(db_cycle_values) - db_true
            
            db_cycle_ended = False
            for i in range(1, len(db_cycle_values)):
                if db_cycle_values[i-1] == True and db_cycle_values[i] == False:
                    db_cycle_ended = True
                    break
            
            if db_cycle_ended:
                self.add_result(
                    "Cycle Completion (DB)",
                    True,
                    f"Database shows cycle completed",
                    {"true": db_true, "false": db_false}
                )
            else:
                self.add_result(
                    "Cycle Completion (DB)",
                    False,
                    f"Database shows cycle NOT completed or not imported"
                )
    
    def _check_wait_time(self):
        """Check 4: Verify wait time requirement (300 seconds after cycle end)"""
        print("\n" + "-" * 40)
        print("CHECK 4: Wait Time Requirement")
        print("-" * 40)
        
        print(f"   Required wait time: {self.WAIT_TIME_SECONDS} seconds (5 minutes)")
        
        # Find cycle end time from CSV
        cycle_end_time = None
        if self.csv_rows:
            for i in range(len(self.csv_rows) - 1, 0, -1):
                curr_ciclo = self.csv_rows[i].get('CicloActivo', '').strip().lower()
                prev_ciclo = self.csv_rows[i-1].get('CicloActivo', '').strip().lower()
                
                if prev_ciclo == 'true' and curr_ciclo == 'false':
                    # Found transition, get timestamp
                    dt_str = self.csv_rows[i].get('datetime', '')
                    try:
                        cycle_end_time = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                        break
                    except:
                        pass
        
        if cycle_end_time:
            now = timezone.now()
            # Handle timezone
            if cycle_end_time.tzinfo is None:
                cycle_end_time = timezone.make_aware(cycle_end_time)
            
            time_since_end = (now - cycle_end_time).total_seconds()
            
            if time_since_end >= self.WAIT_TIME_SECONDS:
                self.add_result(
                    "Wait Time Elapsed",
                    True,
                    f"Cycle ended {time_since_end:.0f} seconds ago (>{self.WAIT_TIME_SECONDS}s required)",
                    {"seconds_since_end": time_since_end, "cycle_end_time": str(cycle_end_time)}
                )
            else:
                remaining = self.WAIT_TIME_SECONDS - time_since_end
                self.add_result(
                    "Wait Time Elapsed",
                    False,
                    f"Cycle ended only {time_since_end:.0f} seconds ago. "
                    f"Need to wait {remaining:.0f} more seconds.",
                    {"seconds_since_end": time_since_end, "remaining": remaining}
                )
            
            print(f"   Cycle end time: {cycle_end_time}")
            print(f"   Current time: {now}")
            print(f"   Time elapsed: {time_since_end:.0f} seconds")
        else:
            self.add_result(
                "Wait Time Elapsed",
                False,
                "Could not determine cycle end time (cycle may not have ended)"
            )
    
    def _check_staging_photos(self):
        """Check 5: Verify photos exist in STAGING folder"""
        print("\n" + "-" * 40)
        print("CHECK 5: STAGING Photos")
        print("-" * 40)
        
        print(f"   STAGING path: {STAGING_PATH}")
        
        if not STAGING_PATH.exists():
            self.add_result(
                "STAGING Directory Exists",
                False,
                f"STAGING directory does not exist: {STAGING_PATH}"
            )
            return
        
        self.add_result(
            "STAGING Directory Exists",
            True,
            f"Directory exists: {STAGING_PATH}"
        )
        
        # Find all photos in STAGING
        all_photos = []
        matching_photos = []
        
        for ext in ('.bmp', '.jpg', '.jpeg', '.png'):
            all_photos.extend(list(STAGING_PATH.glob(f'*{ext}')))
        
        print(f"   Total photos in STAGING: {len(all_photos)}")
        
        # Find photos matching our NombreCiclo-ID_EC prefix
        prefix = f"{self.nombre_ciclo}-{self.id_ec}-"
        for photo in all_photos:
            if photo.name.startswith(prefix):
                matching_photos.append(photo)
        
        self.staging_photos = matching_photos
        
        if matching_photos:
            self.add_result(
                "Matching STAGING Photos",
                True,
                f"Found {len(matching_photos)} photos matching prefix '{prefix}'",
                {"photos": [p.name for p in matching_photos]}
            )
            print(f"   Matching photos:")
            for p in matching_photos[:10]:  # Show first 10
                print(f"      - {p.name}")
            if len(matching_photos) > 10:
                print(f"      ... and {len(matching_photos) - 10} more")
        else:
            self.add_result(
                "Matching STAGING Photos",
                False,
                f"No photos found matching prefix '{prefix}' in STAGING folder"
            )
            
            # Show what photos ARE in staging
            if all_photos:
                print(f"   Photos in STAGING (first 10):")
                for p in all_photos[:10]:
                    print(f"      - {p.name}")
    
    def _check_processed_photos(self):
        """Check 6: Check if photos were already processed"""
        print("\n" + "-" * 40)
        print("CHECK 6: PROCESSED Photos")
        print("-" * 40)
        
        print(f"   PROCESSED path: {PROCESSED_PATH}")
        
        if not PROCESSED_PATH.exists():
            self.add_result(
                "PROCESSED Directory Exists",
                True,
                f"PROCESSED directory does not exist yet (no photos processed)"
            )
            return
        
        # Look for inspection folder
        inspection_folder = PROCESSED_PATH / self.product_code
        
        if inspection_folder.exists():
            processed_photos = list(inspection_folder.glob('*'))
            self.processed_photos = [p for p in processed_photos if p.is_file()]
            
            self.add_result(
                "Photos Already Processed",
                True,
                f"Found {len(self.processed_photos)} files in PROCESSED/{self.product_code}/",
                {"folder": str(inspection_folder)}
            )
            print(f"   Inspection folder: {inspection_folder}")
            print(f"   Files in folder:")
            for p in self.processed_photos[:10]:
                print(f"      - {p.name}")
        else:
            self.add_result(
                "Photos Already Processed",
                True,
                f"No processed folder found for {self.product_code} (photos not yet processed)"
            )
    
    def _check_existing_inspections(self):
        """Check 7: Check if inspection already exists in database"""
        print("\n" + "-" * 40)
        print("CHECK 7: Existing Inspections in Database")
        print("-" * 40)
        
        try:
            # Look for inspection with matching product_code
            inspections = Inspection.objects.filter(product_code=self.product_code)
            self.existing_inspections = list(inspections)
            
            if self.existing_inspections:
                self.add_result(
                    "Inspection Already Exists",
                    True,
                    f"Found {len(self.existing_inspections)} inspection(s) with product_code={self.product_code}",
                    {"inspection_ids": [i.id for i in self.existing_inspections]}
                )
                
                for insp in self.existing_inspections:
                    print(f"   Inspection ID: {insp.id}")
                    print(f"      Title: {insp.title}")
                    print(f"      Status: {insp.status}")
                    print(f"      Created: {insp.created_at if hasattr(insp, 'created_at') else 'N/A'}")
                    print(f"      Defecto: {insp.defecto_encontrado}")
                    
                    # Count photos for this inspection
                    photo_count = InspectionPhoto.objects.filter(inspection=insp).count()
                    print(f"      Photos linked: {photo_count}")
            else:
                self.add_result(
                    "Inspection Does Not Exists",
                    False,
                    f"No inspection found with product_code={self.product_code}"
                )
                
            # Also search by batch_number and serial_number
            alt_inspections = Inspection.objects.filter(
                batch_number=self.nombre_ciclo,
                serial_number=self.id_ec
            ).exclude(product_code=self.product_code)
            
            if alt_inspections.exists():
                print(f"\n   ⚠️  Found {alt_inspections.count()} inspection(s) with different product_code but matching batch/serial:")
                for insp in alt_inspections:
                    print(f"      - ID: {insp.id}, product_code: {insp.product_code}")
                    
        except Exception as e:
            self.add_result(
                "Database Inspection Query",
                False,
                f"Error querying inspections: {e}"
            )
    
    def _check_existing_inspection_photos(self):
        """Check 8: Check existing InspectionPhoto records"""
        print("\n" + "-" * 40)
        print("CHECK 8: Existing InspectionPhoto Records")
        print("-" * 40)
        
        try:
            # Search for photos with matching prefix in path
            prefix = f"{self.nombre_ciclo}-{self.id_ec}-"
            matching_photos = []
            
            all_photos = InspectionPhoto.objects.all()
            for photo in all_photos:
                if photo.photo and prefix in str(photo.photo):
                    matching_photos.append(photo)
            
            self.existing_inspection_photos = matching_photos
            
            if matching_photos:
                self.add_result(
                    "InspectionPhoto Records",
                    True,
                    f"Found {len(matching_photos)} InspectionPhoto records matching prefix"
                )
                print(f"   Matching records:")
                for p in matching_photos[:10]:
                    print(f"      - {p.photo} (Inspection ID: {p.inspection_id})")
            else:
                self.add_result(
                    "InspectionPhoto Records",
                    True,
                    "No InspectionPhoto records found matching this prefix (photos not yet linked)"
                )
                
        except Exception as e:
            self.add_result(
                "InspectionPhoto Query",
                False,
                f"Error querying InspectionPhoto: {e}"
            )
    
    def _check_photo_filename_matching(self):
        """Check 9: Validate photo filename format and matching logic"""
        print("\n" + "-" * 40)
        print("CHECK 9: Photo Filename Matching")
        print("-" * 40)
        
        # Get unique ID_Control values from CSV
        id_controls = set()
        if self.csv_rows:
            for row in self.csv_rows:
                id_control = row.get('ID_Control', '').strip()
                if id_control:
                    id_controls.add(id_control)
        
        print(f"   Expected photo prefixes (from CSV ID_Control values):")
        
        # Build expected prefixes
        expected_prefixes = []
        for id_control in sorted(id_controls)[:20]:
            prefix = f"{self.nombre_ciclo}-{self.id_ec}-{id_control}"
            expected_prefixes.append(prefix)
            print(f"      {prefix}-*.bmp")
        
        if len(id_controls) > 20:
            print(f"      ... and {len(id_controls) - 20} more")
        
        # Check if any staging photos match these prefixes
        if self.staging_photos:
            matched_prefixes = set()
            for photo in self.staging_photos:
                for prefix in expected_prefixes:
                    if photo.name.startswith(prefix + "-"):
                        matched_prefixes.add(prefix)
            
            if matched_prefixes:
                self.add_result(
                    "Photo Prefix Matching",
                    True,
                    f"Found photos matching {len(matched_prefixes)} expected prefixes"
                )
            else:
                self.add_result(
                    "Photo Prefix Matching",
                    False,
                    "No staging photos match expected prefixes from CSV"
                )
        else:
            self.add_result(
                "Photo Prefix Matching",
                False,
                "No staging photos to check"
            )
    
    def _check_tes_exclusion(self):
        """Check 10: Check for 'tes' exclusion pattern in ID_Control"""
        print("\n" + "-" * 40)
        print("CHECK 10: 'tes' Exclusion Pattern")
        print("-" * 40)
        
        print("   Note: Rows with 'tes' in ID_Control are SKIPPED by the processor")
        
        tes_rows = []
        non_tes_rows = []
        
        if self.csv_rows:
            for row in self.csv_rows:
                id_control = row.get('ID_Control', '').strip()
                if 'tes' in id_control.lower():
                    tes_rows.append(row)
                elif id_control:  # Only count non-empty ID_Control
                    non_tes_rows.append(row)
        
        if tes_rows:
            self.add_result(
                "'tes' Exclusion",
                True,
                f"Found {len(tes_rows)} rows with 'tes' in ID_Control (will be skipped)",
                {"tes_count": len(tes_rows), "valid_count": len(non_tes_rows)}
            )
            tes_controls = set(r.get('ID_Control', '') for r in tes_rows)
            print(f"   'tes' ID_Controls: {sorted(tes_controls)}")
        
        if non_tes_rows:
            print(f"   Valid rows (without 'tes'): {len(non_tes_rows)}")
        else:
            self.add_result(
                "'tes' Exclusion",
                False,
                "All rows have 'tes' in ID_Control or empty ID_Control - no photos will be matched!"
            )
    
    def _check_required_fields(self):
        """Check 11: Verify required fields are present"""
        print("\n" + "-" * 40)
        print("CHECK 11: Required Fields")
        print("-" * 40)
        
        if not self.csv_rows:
            self.add_result(
                "Required Fields",
                False,
                "No CSV rows to check"
            )
            return
        
        # Check required fields in first row
        sample_row = self.csv_rows[0]
        required_fields = ['NombreCiclo', 'ID_EC', 'ID_Control', 'CicloActivo']
        
        missing_fields = []
        empty_fields = []
        
        for field in required_fields:
            if field not in sample_row:
                missing_fields.append(field)
            elif not sample_row.get(field, '').strip():
                empty_fields.append(field)
        
        if missing_fields:
            self.add_result(
                "Required Fields Present",
                False,
                f"Missing fields in CSV: {missing_fields}, row: {sample_row}"
            )
        elif empty_fields:
            self.add_result(
                "Required Fields Present",
                False,
                f"Empty required fields found: {empty_fields}, row: {sample_row}"
            )
        else:
            self.add_result(
                "Required Fields Present",
                True,
                "All required fields are present"
            )
        
        # Count rows with complete data
        complete_rows = 0
        for row in self.csv_rows:
            nombre = row.get('NombreCiclo', '').strip()
            id_ec = row.get('ID_EC', '').strip()
            id_control = row.get('ID_Control', '').strip()
            
            if nombre and id_ec and id_control:
                complete_rows += 1
        
        print(f"   Rows with complete data: {complete_rows} / {len(self.csv_rows)}")
    
    def _print_summary(self):
        """Print validation summary"""
        print("\n" + "=" * 80)
        print("VALIDATION SUMMARY")
        print("=" * 80)
        
        passed = [r for r in self.results if r.passed]
        failed = [r for r in self.results if not r.passed]
        
        print(f"\nTotal checks: {len(self.results)}")
        print(f"Passed: {len(passed)}")
        print(f"Failed: {len(failed)}")
        
        if failed:
            print("\n❌ FAILED CHECKS:")
            for r in failed:
                print(f"   - {r.check_name}: {r.message}")
        
        # Provide diagnosis
        print("\n" + "-" * 40)
        print("DIAGNOSIS")
        print("-" * 40)
        
        if not self.csv_rows:
            print("🔴 CRITICAL: No matching data found in CSV file")
            print("   → Check that NombreCiclo and ID_EC values are correct")
        
        if not self.db_raw_records:
            print("🔴 CRITICAL: No matching data in database")
            print("   → CSV data needs to be imported into PlcDataRaw table")
        
        if not self.staging_photos:
            print("🔴 CRITICAL: No photos found in STAGING folder")
            print(f"   → Place photos matching '{self.nombre_ciclo}-{self.id_ec}-*' in: {STAGING_PATH}")
        
        if self.existing_inspections:
            print("🟡 INFO: Inspection already exists in database")
            print("   → Check if photos need to be re-linked or if this is expected")
        
        all_critical_passed = (
            bool(self.csv_rows) and 
            bool(self.db_raw_records) and 
            bool(self.staging_photos)
        )
        
        if all_critical_passed and not self.existing_inspections:
            print("🟢 All critical checks passed!")
            print("   → Run the plc_data_processor.py to create the inspection")
            print("   → Make sure wait time (300s) has elapsed since cycle ended")


def main():
    """Main entry point"""
    if len(sys.argv) != 3:
        print("Usage: python inspection_validation.py <NombreCiclo> <ID_EC>")
        print("Example: python inspection_validation.py CNA2 E3742")
        sys.exit(1)
    
    nombre_ciclo = sys.argv[1]
    id_ec = sys.argv[2]
    
    validator = InspectionValidator(nombre_ciclo, id_ec)
    validator.run_all_validations()


if __name__ == "__main__":
    main()
