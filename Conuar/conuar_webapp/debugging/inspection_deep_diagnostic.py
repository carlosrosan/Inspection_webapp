#!/usr/bin/env python3
"""
Deep Diagnostic Script - Sistema Conuar

This script performs deep diagnostics on why a specific inspection (CNA2-E3742)
is not being created, checking:
1. Database record positions and processing order
2. Cycle detection simulation
3. Which cycle would be processed NEXT
4. Why your target cycle might be blocked

Usage:
    python inspection_deep_diagnostic.py <NombreCiclo> <ID_EC>
    
Example:
    python inspection_deep_diagnostic.py CNA2 E3742
"""

import os
import sys
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Django setup - MINIMAL to avoid triggering background monitors
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Disable auto-start of monitors by setting a flag BEFORE django.setup()
os.environ['DISABLE_PLC_MONITORS'] = 'true'

import django
try:
    django.apps.apps.check_apps_ready()
except Exception:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    django.setup()

from django.utils import timezone
from django.db import connection

# Import Django models
try:
    from main.models import PlcDataRaw, Inspection, InspectionPhoto
except ImportError as e:
    print(f"[ERROR] Could not import Django models: {e}")
    sys.exit(1)


def is_boolean_true(value) -> bool:
    """Check if a value represents boolean TRUE (same logic as plc_data_processor)"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes')
    if isinstance(value, (int, float)):
        return value == 1
    return False


def get_field_value(data: dict, field_name: str, fallbacks: list = None) -> str:
    """Safely extract field value from data dict"""
    if fallbacks is None:
        fallbacks = []
    
    for name in [field_name, f' {field_name}'] + fallbacks:
        value = data.get(name)
        if value is None:
            continue
        if isinstance(value, bool):
            return '' if value is False else 'true'
        value_str = str(value).strip()
        if value_str and value_str.lower() not in ('false', 'none', 'null', ''):
            return value_str
    return ''


class DeepDiagnostic:
    """Deep diagnostic for inspection creation issues"""
    
    WAIT_TIME_SECONDS = 300
    
    def __init__(self, nombre_ciclo: str, id_ec: str):
        self.nombre_ciclo = nombre_ciclo
        self.id_ec = id_ec
        self.product_code = f"{nombre_ciclo}-{id_ec}"
    
    def run(self):
        print("=" * 80)
        print("DEEP DIAGNOSTIC REPORT")
        print(f"Target: {self.product_code}")
        print(f"Time: {datetime.now()}")
        print("=" * 80)
        
        self._check_database_overview()
        self._check_processing_queue()
        self._check_target_cycle_position()
        self._simulate_cycle_detection()
        self._check_blocking_cycles()
        self._provide_recommendations()
    
    def _check_database_overview(self):
        """Overview of PlcDataRaw table"""
        print("\n" + "=" * 60)
        print("1. DATABASE OVERVIEW")
        print("=" * 60)
        
        total = PlcDataRaw.objects.count()
        unprocessed = PlcDataRaw.objects.filter(processed=False).count()
        processed = PlcDataRaw.objects.filter(processed=True).count()
        
        print(f"   Total PlcDataRaw records: {total}")
        print(f"   Processed: {processed}")
        print(f"   Unprocessed: {unprocessed}")
        
        if unprocessed == 0:
            print("\n   ⚠️  ALL RECORDS ARE MARKED AS PROCESSED!")
            print("   This means either:")
            print("   - All cycles have been processed (check Inspection table)")
            print("   - Records were marked processed without creating inspections")
    
    def _check_processing_queue(self):
        """Check what's at the front of the processing queue"""
        print("\n" + "=" * 60)
        print("2. PROCESSING QUEUE (First 10 unprocessed records)")
        print("=" * 60)
        
        first_unprocessed = PlcDataRaw.objects.filter(
            processed=False
        ).order_by('timestamp')[:10]
        
        if not first_unprocessed:
            print("   No unprocessed records in queue!")
            return
        
        print(f"\n   {'ID':<8} {'Timestamp':<25} {'CicloActivo':<12} {'NombreCiclo':<15} {'ID_EC':<10} {'ID_Control':<10}")
        print("   " + "-" * 80)
        
        for record in first_unprocessed:
            try:
                data = json.loads(record.json_data)
                ciclo_activo = data.get('CicloActivo', data.get(' CicloActivo', ''))
                nombre = get_field_value(data, 'NombreCiclo')
                id_ec = get_field_value(data, 'ID_EC')
                id_control = get_field_value(data, 'ID_Control')
                
                print(f"   {record.id:<8} {str(record.timestamp)[:25]:<25} {str(ciclo_activo):<12} {nombre:<15} {id_ec:<10} {id_control:<10}")
            except:
                print(f"   {record.id:<8} [Error parsing JSON]")
    
    def _check_target_cycle_position(self):
        """Check where target cycle records are in the queue"""
        print("\n" + "=" * 60)
        print(f"3. TARGET CYCLE POSITION ({self.product_code})")
        print("=" * 60)
        
        # Find all records for target cycle
        all_target_records = []
        target_unprocessed = []
        target_processed = []
        
        for record in PlcDataRaw.objects.all().order_by('timestamp'):
            try:
                data = json.loads(record.json_data)
                nombre = get_field_value(data, 'NombreCiclo')
                id_ec = get_field_value(data, 'ID_EC')
                
                if nombre == self.nombre_ciclo and id_ec == self.id_ec:
                    all_target_records.append(record)
                    if record.processed:
                        target_processed.append(record)
                    else:
                        target_unprocessed.append(record)
            except:
                continue
        
        print(f"\n   Total records for {self.product_code}: {len(all_target_records)}")
        print(f"   - Processed: {len(target_processed)}")
        print(f"   - Unprocessed: {len(target_unprocessed)}")
        
        if all_target_records:
            first_record = all_target_records[0]
            last_record = all_target_records[-1]
            print(f"\n   First record ID: {first_record.id}, Timestamp: {first_record.timestamp}")
            print(f"   Last record ID: {last_record.id}, Timestamp: {last_record.timestamp}")
            
            # Check position in overall queue
            records_before = PlcDataRaw.objects.filter(
                processed=False,
                timestamp__lt=first_record.timestamp
            ).count()
            
            print(f"\n   Unprocessed records BEFORE this cycle: {records_before}")
            
            if records_before > 0:
                print(f"   ⚠️  There are {records_before} unprocessed records that will be processed FIRST!")
        else:
            print(f"\n   ❌ No records found for {self.product_code} in database!")
    
    def _simulate_cycle_detection(self):
        """Simulate the cycle detection logic"""
        print("\n" + "=" * 60)
        print("4. CYCLE DETECTION SIMULATION")
        print("=" * 60)
        
        # Get first 500 unprocessed records (same as processor)
        raw_rows = list(PlcDataRaw.objects.filter(
            processed=False
        ).order_by('timestamp')[:500])
        
        print(f"\n   Fetched {len(raw_rows)} unprocessed records (limit=500)")
        
        if not raw_rows:
            print("   No unprocessed records to simulate!")
            return
        
        # Simulate cycle grouping
        cycles = []
        current_cycle = []
        collecting = False
        prev_ciclo_activo = False
        
        now = timezone.now()
        
        for raw in raw_rows:
            try:
                data = json.loads(raw.json_data)
                raw._parsed_data = data
                
                ciclo_activo = data.get("CicloActivo") or data.get(" CicloActivo")
                is_active = is_boolean_true(ciclo_activo)
                
                # Start collecting when CicloActivo changes to TRUE
                if is_active and not collecting:
                    collecting = True
                    current_cycle = []
                    prev_ciclo_activo = True
                
                if collecting:
                    current_cycle.append(raw)
                    
                    # End cycle when CicloActivo changes to FALSE
                    if not is_active and prev_ciclo_activo:
                        cycle_end_time = raw.timestamp
                        
                        # Handle timezone
                        if cycle_end_time.tzinfo is not None and now.tzinfo is None:
                            cycle_end_time = cycle_end_time.replace(tzinfo=None)
                        elif cycle_end_time.tzinfo is None and now.tzinfo is not None:
                            cycle_end_time = timezone.make_aware(cycle_end_time)
                        
                        time_since_end = (now - cycle_end_time).total_seconds()
                        
                        # Get cycle info
                        first_data = current_cycle[0]._parsed_data
                        nombre = get_field_value(first_data, 'NombreCiclo')
                        id_ec = get_field_value(first_data, 'ID_EC')
                        
                        cycles.append({
                            'nombre_ciclo': nombre,
                            'id_ec': id_ec,
                            'product_code': f"{nombre}-{id_ec}",
                            'rows': len(current_cycle),
                            'first_id': current_cycle[0].id,
                            'last_id': current_cycle[-1].id,
                            'time_since_end': time_since_end,
                            'ready': time_since_end >= self.WAIT_TIME_SECONDS
                        })
                        
                        current_cycle = []
                        collecting = False
                        prev_ciclo_activo = False
                    elif is_active:
                        prev_ciclo_activo = True
            except Exception as e:
                continue
        
        # Still collecting at the end means cycle hasn't ended
        if collecting and current_cycle:
            first_data = current_cycle[0]._parsed_data
            nombre = get_field_value(first_data, 'NombreCiclo')
            id_ec = get_field_value(first_data, 'ID_EC')
            cycles.append({
                'nombre_ciclo': nombre,
                'id_ec': id_ec,
                'product_code': f"{nombre}-{id_ec}",
                'rows': len(current_cycle),
                'first_id': current_cycle[0].id,
                'last_id': current_cycle[-1].id,
                'time_since_end': None,
                'ready': False,
                'incomplete': True
            })
        
        print(f"\n   Cycles detected in batch: {len(cycles)}")
        
        if cycles:
            print(f"\n   {'#':<3} {'Product Code':<20} {'Rows':<6} {'ID Range':<20} {'Status':<30}")
            print("   " + "-" * 80)
            
            target_found = False
            for i, cycle in enumerate(cycles, 1):
                id_range = f"{cycle['first_id']}-{cycle['last_id']}"
                
                if cycle.get('incomplete'):
                    status = "⏳ INCOMPLETE (still active)"
                elif cycle['ready']:
                    status = f"✅ READY ({cycle['time_since_end']:.0f}s ago)"
                else:
                    remaining = self.WAIT_TIME_SECONDS - cycle['time_since_end']
                    status = f"⏳ WAITING ({remaining:.0f}s remaining)"
                
                is_target = cycle['product_code'] == self.product_code
                marker = "→ " if is_target else "  "
                
                print(f"   {marker}{i:<3} {cycle['product_code']:<20} {cycle['rows']:<6} {id_range:<20} {status}")
                
                if is_target:
                    target_found = True
            
            if not target_found:
                print(f"\n   ⚠️  Target cycle {self.product_code} NOT FOUND in first 500 records!")
                print(f"   The cycle might be beyond the current batch limit.")
    
    def _check_blocking_cycles(self):
        """Check if other cycles are blocking the target"""
        print("\n" + "=" * 60)
        print("5. BLOCKING ANALYSIS")
        print("=" * 60)
        
        # Get first unprocessed record for target
        target_first = None
        for record in PlcDataRaw.objects.filter(processed=False).order_by('timestamp'):
            try:
                data = json.loads(record.json_data)
                nombre = get_field_value(data, 'NombreCiclo')
                id_ec = get_field_value(data, 'ID_EC')
                
                if nombre == self.nombre_ciclo and id_ec == self.id_ec:
                    target_first = record
                    break
            except:
                continue
        
        if not target_first:
            print(f"\n   No unprocessed records found for {self.product_code}")
            return
        
        # Find all distinct cycles before target
        blocking_cycles = {}
        for record in PlcDataRaw.objects.filter(
            processed=False,
            timestamp__lt=target_first.timestamp
        ).order_by('timestamp'):
            try:
                data = json.loads(record.json_data)
                nombre = get_field_value(data, 'NombreCiclo')
                id_ec = get_field_value(data, 'ID_EC')
                
                if nombre and id_ec:
                    key = f"{nombre}-{id_ec}"
                    if key not in blocking_cycles:
                        blocking_cycles[key] = 0
                    blocking_cycles[key] += 1
            except:
                continue
        
        if blocking_cycles:
            print(f"\n   Cycles that must be processed BEFORE {self.product_code}:")
            print(f"\n   {'Cycle':<25} {'Unprocessed Records':<20}")
            print("   " + "-" * 45)
            
            for cycle, count in sorted(blocking_cycles.items()):
                print(f"   {cycle:<25} {count:<20}")
            
            print(f"\n   Total blocking cycles: {len(blocking_cycles)}")
            print(f"   Total blocking records: {sum(blocking_cycles.values())}")
        else:
            print(f"\n   ✅ No cycles blocking {self.product_code}")
    
    def _provide_recommendations(self):
        """Provide actionable recommendations"""
        print("\n" + "=" * 60)
        print("6. RECOMMENDATIONS")
        print("=" * 60)
        
        # Check various conditions
        unprocessed = PlcDataRaw.objects.filter(processed=False).count()
        
        # Find target records
        target_unprocessed = 0
        for record in PlcDataRaw.objects.filter(processed=False):
            try:
                data = json.loads(record.json_data)
                nombre = get_field_value(data, 'NombreCiclo')
                id_ec = get_field_value(data, 'ID_EC')
                if nombre == self.nombre_ciclo and id_ec == self.id_ec:
                    target_unprocessed += 1
            except:
                continue
        
        print("\n   Based on the analysis:")
        
        if unprocessed == 0:
            print("\n   1. ❌ All records are processed - check if inspection was created")
            print("      → Run: Inspection.objects.filter(product_code='CNA2-E3742')")
        
        if target_unprocessed == 0 and unprocessed > 0:
            print(f"\n   1. ❌ No unprocessed records for {self.product_code}")
            print("      → Records may already be processed or not imported")
        
        if target_unprocessed > 0:
            # Find first target record position
            first_target = None
            position = 0
            for record in PlcDataRaw.objects.filter(processed=False).order_by('timestamp'):
                position += 1
                try:
                    data = json.loads(record.json_data)
                    nombre = get_field_value(data, 'NombreCiclo')
                    id_ec = get_field_value(data, 'ID_EC')
                    if nombre == self.nombre_ciclo and id_ec == self.id_ec:
                        first_target = position
                        break
                except:
                    continue
            
            if first_target and first_target > 500:
                print(f"\n   1. ⚠️  Target cycle starts at position {first_target}")
                print(f"      → Batch limit is 500, so it won't be reached in one run")
                print(f"      → Option A: Run processor multiple times to clear earlier cycles")
                print(f"      → Option B: Increase batch_size in process_pending_cycles()")
                print(f"      → Option C: Mark earlier records as processed manually")
            elif first_target and first_target <= 500:
                print(f"\n   1. ✅ Target cycle is at position {first_target} (within batch)")
                print("      → Check if blocking cycles are failing to process")
                print("      → The processor might be stuck on an earlier cycle")
        
        print("\n   2. 🔍 Quick SQL check for your cycle:")
        print(f"      SELECT id, processed, timestamp FROM main_plcdataraw")
        print(f"      WHERE json_data LIKE '%{self.nombre_ciclo}%' AND json_data LIKE '%{self.id_ec}%'")
        print(f"      ORDER BY timestamp LIMIT 10;")
        
        print("\n   3. 🔧 To force processing of this specific cycle:")
        print("      → Mark all earlier unprocessed records as processed")
        print("      → Or modify plc_data_processor.py to filter by product_code")


def main():
    if len(sys.argv) != 3:
        print("Usage: python inspection_deep_diagnostic.py <NombreCiclo> <ID_EC>")
        print("Example: python inspection_deep_diagnostic.py CNA2 E3742")
        sys.exit(1)
    
    nombre_ciclo = sys.argv[1]
    id_ec = sys.argv[2]
    
    diagnostic = DeepDiagnostic(nombre_ciclo, id_ec)
    diagnostic.run()


if __name__ == "__main__":
    main()
