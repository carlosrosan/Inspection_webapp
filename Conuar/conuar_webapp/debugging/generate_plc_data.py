#!/usr/bin/env python3
"""
Generate PLC Data from Photos - Sistema Conuar

This script generates PLC records in CSV format based on photos in the STAGING folder.
It matches photos by Inspection date, Ciclo_Inspeccion (NombreCiclo), and EC_ID (ID_EC).

Photo format: {NombreCiclo}-{ID_EC}-{ID_Control}-{Fecha formato DDMMYY}_{Hora formato HHMMss}-{Falla}{PhotoNumber}.bmp
Example: COMPLETO-UNO-1F-231225_134953-NOK753.bmp

The script generates PLC records following the same format as plc_reads_nodered.csv:
datetime,CicloActivo,ReiniciarCiclo,AbortarCiclo,FinCiclo,ID_Control,Nombre_Control,ID_EC,NombreCiclo
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple, Optional
import re
import csv

# Try to import paths config, fallback to default if not available
try:
    from config.paths_config import INSPECTION_PHOTOS_STAGING_DIR
    STAGING_DIR = Path(INSPECTION_PHOTOS_STAGING_DIR)
except ImportError:
    # Fallback path
    current_dir = Path(__file__).resolve().parent
    project_root = current_dir.parent
    STAGING_DIR = project_root / "media" / "inspection_photos" / "STAGING"


def parse_photo_filename(filename: str) -> Optional[Tuple[str, str, str, Optional[datetime]]]:
    """
    Parse photo filename to extract components.
    
    Format: {NombreCiclo}-{ID_EC}-{ID_Control}-{Fecha formato DDMMYY}_{Hora formato HHMMss}-{Falla}{PhotoNumber}.ext
    Example: COMPLETO-UNO-1F-231225_134953-NOK753.bmp
    
    Returns:
        Tuple of (nombre_ciclo, id_ec, id_control, timestamp) or None if parsing fails
        timestamp is datetime object if found, None otherwise
    """
    # Remove extension
    stem = Path(filename).stem
    
    # Split by dashes
    parts = stem.split('-')
    
    if len(parts) < 3:
        return None
    
    nombre_ciclo = parts[0]
    id_ec = parts[1]
    id_control = parts[2]
    
    # Try to extract timestamp (format: DDMMYY_HHMMSS)
    timestamp = None
    if len(parts) >= 4:
        # Look for pattern DDMMYY_HHMMSS in the filename
        timestamp_pattern = r'-(\d{6})_(\d{6})-'
        match = re.search(timestamp_pattern, stem)
        if match:
            fecha_str = match.group(1)  # DDMMYY
            hora_str = match.group(2)   # HHMMSS
            
            try:
                day = int(fecha_str[0:2])
                month = int(fecha_str[2:4])
                year = 2000 + int(fecha_str[4:6])  # Assume 20XX
                
                hour = int(hora_str[0:2])
                minute = int(hora_str[2:4])
                second = int(hora_str[4:6])
                
                timestamp = datetime(year, month, day, hour, minute, second)
            except (ValueError, IndexError):
                pass
    
    return (nombre_ciclo, id_ec, id_control, timestamp)


def find_matching_photos(inspection_date: datetime, ciclo_inspeccion: str, ec_id: str) -> List[Tuple[Path, str, Optional[datetime]]]:
    """
    Find photos in STAGING folder that match the given criteria.
    
    Args:
        inspection_date: Date to match (YYYY-MM-DD format, will match photos on this date)
        ciclo_inspeccion: NombreCiclo value to match
        ec_id: ID_EC value to match
    
    Returns:
        List of tuples: (photo_path, id_control, timestamp)
    """
    matching_photos = []
    
    if not STAGING_DIR.exists():
        print(f"STAGING directory does not exist: {STAGING_DIR}")
        return matching_photos
    
    # Build match prefix: {Ciclo_Inspeccion}-{EC_ID}-
    match_prefix = f"{ciclo_inspeccion}-{ec_id}-"
    
    # Convert inspection_date to DDMMYY format for comparison
    date_str_ddmmyy = inspection_date.strftime("%d%m%y")
    
    # Search for matching photos
    for ext in (".bmp", ".jpg", ".jpeg", ".png"):
        for photo_file in STAGING_DIR.glob(f"{match_prefix}*{ext}"):
            # Parse the filename
            parsed = parse_photo_filename(photo_file.name)
            if parsed:
                nombre_ciclo, id_ec, id_control, timestamp = parsed
                
                # Verify it matches our criteria
                if nombre_ciclo == ciclo_inspeccion and id_ec == ec_id:
                    # Check if date matches (if timestamp is available)
                    if timestamp:
                        photo_date_str = timestamp.strftime("%d%m%y")
                        if photo_date_str == date_str_ddmmyy:
                            matching_photos.append((photo_file, id_control, timestamp))
                    else:
                        # If no timestamp in filename, include it anyway
                        matching_photos.append((photo_file, id_control, None))
    
    # Sort by filename (which should give chronological order if timestamps are in filename)
    matching_photos.sort(key=lambda x: x[0].name)
    
    return matching_photos


def generate_plc_records(inspection_date: datetime, ciclo_inspeccion: str, ec_id: str) -> List[dict]:
    """
    Generate PLC records from matching photos.
    
    Args:
        inspection_date: Inspection date (datetime object)
        ciclo_inspeccion: NombreCiclo value
        ec_id: ID_EC value
    
    Returns:
        List of dictionaries representing PLC records
    """
    # Find matching photos
    photos = find_matching_photos(inspection_date, ciclo_inspeccion, ec_id)
    
    if not photos:
        print(f"No matching photos found for Ciclo={ciclo_inspeccion}, EC_ID={ec_id}, Date={inspection_date.strftime('%Y-%m-%d')}")
        return []
    
    print(f"Found {len(photos)} matching photos")
    
    records = []
    
    # Start of cycle: CicloActivo=true, others false, no ID_Control
    # Use first photo's timestamp or inspection_date
    start_time = photos[0][2] if photos[0][2] else inspection_date
    records.append({
        'datetime': start_time.isoformat() + 'Z',
        'CicloActivo': 'true',
        'ReiniciarCiclo': 'false',
        'AbortarCiclo': 'false',
        'FinCiclo': 'false',
        'ID_Control': '',
        'Nombre_Control': '',
        'ID_EC': ec_id,
        'NombreCiclo': ciclo_inspeccion
    })
    
    # Add a record for each photo with ID_Control
    # Increment time by a few seconds for each photo
    current_time = start_time
    for i, (photo_path, id_control, timestamp) in enumerate(photos):
        # Use timestamp from photo if available, otherwise increment from previous
        if timestamp:
            current_time = timestamp
        else:
            # Increment by 5 seconds for each photo if no timestamp
            current_time = start_time + timedelta(seconds=5 * (i + 1))
        
        records.append({
            'datetime': current_time.isoformat() + 'Z',
            'CicloActivo': 'true',
            'ReiniciarCiclo': 'false',
            'AbortarCiclo': 'false',
            'FinCiclo': 'false',
            'ID_Control': id_control,
            'Nombre_Control': '',
            'ID_EC': ec_id,
            'NombreCiclo': ciclo_inspeccion
        })
    
    # End of cycle: CicloActivo=false, FinCiclo=true
    # Use last photo's timestamp + a few seconds
    end_time = photos[-1][2] if photos[-1][2] else (current_time + timedelta(seconds=5))
    if not photos[-1][2]:
        end_time = current_time + timedelta(seconds=5)
    
    records.append({
        'datetime': end_time.isoformat() + 'Z',
        'CicloActivo': 'false',
        'ReiniciarCiclo': 'false',
        'AbortarCiclo': 'false',
        'FinCiclo': 'true',
        'ID_Control': '',
        'Nombre_Control': '',
        'ID_EC': ec_id,
        'NombreCiclo': ciclo_inspeccion
    })
    
    return records


def write_csv_records(records: List[dict], output_file: Path):
    """
    Write PLC records to CSV file in the same format as plc_reads_nodered.csv.
    
    Args:
        records: List of dictionary records
        output_file: Path to output CSV file
    """
    fieldnames = ['datetime', 'CicloActivo', 'ReiniciarCiclo', 'AbortarCiclo', 'FinCiclo', 
                  'ID_Control', 'Nombre_Control', 'ID_EC', 'NombreCiclo']
    
    # Check if file exists - if it does, append to it, otherwise create new
    file_exists = output_file.exists()
    
    with open(output_file, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        # Write header only if file is new
        if not file_exists:
            writer.writeheader()
        
        # Write each record, with empty line after each (matching the format)
        for record in records:
            writer.writerow(record)
            csvfile.write('\n')  # Empty line after each record
    
    print(f"Written {len(records)} records to {output_file}")


def main():
    """Main function to generate PLC data from photos."""
    print("=" * 80)
    print("Generate PLC Data from Photos - Sistema Conuar")
    print("=" * 80)
    print()
    
    # Get inputs from user
    try:
        # Inspection date
        date_str = input("Enter Inspection Date (YYYY-MM-DD): ").strip()
        inspection_date = datetime.strptime(date_str, "%Y-%m-%d")
        
        # Ciclo Inspeccion (NombreCiclo)
        ciclo_inspeccion = input("Enter Ciclo_Inspeccion (NombreCiclo): ").strip()
        if not ciclo_inspeccion:
            print("Error: Ciclo_Inspeccion cannot be empty")
            return
        
        # EC_ID (ID_EC)
        ec_id = input("Enter EC_ID (ID_EC): ").strip()
        if not ec_id:
            print("Error: EC_ID cannot be empty")
            return
        
    except ValueError as e:
        print(f"Error parsing input: {e}")
        return
    
    # Generate PLC records
    print()
    print(f"Generating PLC records for:")
    print(f"  Date: {inspection_date.strftime('%Y-%m-%d')}")
    print(f"  Ciclo: {ciclo_inspeccion}")
    print(f"  EC_ID: {ec_id}")
    print()
    
    records = generate_plc_records(inspection_date, ciclo_inspeccion, ec_id)
    
    if not records:
        print("No records generated. Exiting.")
        return
    
    # Ask for output file
    default_output = Path(__file__).parent / "NodeRed" / "plc_reads" / "plc_reads_nodered.csv"
    output_str = input(f"Enter output CSV file path (default: {default_output}): ").strip()
    
    if output_str:
        output_file = Path(output_str)
    else:
        output_file = default_output
    
    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Write records to CSV
    write_csv_records(records, output_file)
    
    print()
    print("=" * 80)
    print("Done!")
    print("=" * 80)


if __name__ == "__main__":
    main()

