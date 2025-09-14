#!/usr/bin/env python3
"""
Script to generate realistic PLC data for inspection 1
"""

import os
import sys
import django
from datetime import datetime, timedelta
import random

# Agregar proyecto Django al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from main.models import PlcReading, Inspection, InspectionPhoto, InspectionMachine

def generate_plc_data_for_inspection_1():
    """Generate realistic PLC data that would result in inspection 1"""
    
    # Get the existing inspection to understand the timeline
    inspection = Inspection.objects.get(id=1)
    photos = InspectionPhoto.objects.filter(inspection_id=1).order_by('uploaded_at')
    
    print(f"Generating PLC data for inspection: {inspection.title}")
    print(f"Created: {inspection.created_at}")
    print(f"Photos count: {photos.count()}")
    
    # Calculate timeline
    inspection_start = inspection.created_at
    inspection_duration = timedelta(minutes=15)  # Assume 15 minutes for inspection
    inspection_end = inspection_start + inspection_duration
    
    # Generate multiple PLC readings throughout the inspection process
    plc_readings = []
    
    # Reading 1: Inspection start
    reading_time = inspection_start
    plc_readings.append({
        'timestamp_plc': reading_time,
        'id_inspection': 1,
        'execution_id': 1001,
        'control_point_id': 1,
        'execution_type': 1,  # automatic
        'control_point_label': 1001,
        'x_control_point': 0.0,
        'y_control_point': 0.0,
        'z_control_point': 0.0,
        'plate_angle': 0.0,
        'control_point_creator': 1,
        'program_creator': 1,
        'program_version': 2103,
        'camera_id': 1,
        'filming_type': 2,  # photo
        'last_photo_request_timestamp': int(reading_time.timestamp()),
        'new_photos_available': True,
        'photo_count': 3,
        'processed': False
    })
    
    # Reading 2: First control point (OCR)
    reading_time = inspection_start + timedelta(minutes=2)
    plc_readings.append({
        'timestamp_plc': reading_time,
        'id_inspection': 1,
        'execution_id': 1001,
        'control_point_id': 2,
        'execution_type': 1,  # automatic
        'control_point_label': 1002,
        'x_control_point': 10.5,
        'y_control_point': 15.2,
        'z_control_point': 5.0,
        'plate_angle': 0.0,
        'control_point_creator': 1,
        'program_creator': 1,
        'program_version': 2103,
        'camera_id': 1,
        'filming_type': 2,  # photo
        'last_photo_request_timestamp': int(reading_time.timestamp()),
        'new_photos_available': True,
        'photo_count': 1,  # OCR photo
        'processed': False
    })
    
    # Reading 3: Second control point (Deformacion)
    reading_time = inspection_start + timedelta(minutes=4)
    plc_readings.append({
        'timestamp_plc': reading_time,
        'id_inspection': 1,
        'execution_id': 1001,
        'control_point_id': 3,
        'execution_type': 1,  # automatic
        'control_point_label': 1003,
        'x_control_point': 25.3,
        'y_control_point': 8.7,
        'z_control_point': 3.5,
        'plate_angle': 15.0,
        'control_point_creator': 1,
        'program_creator': 1,
        'program_version': 2103,
        'camera_id': 2,
        'filming_type': 2,  # photo
        'last_photo_request_timestamp': int(reading_time.timestamp()),
        'new_photos_available': True,
        'photo_count': 2,  # Deformacion photos
        'processed': False
    })
    
    # Reading 4: Third control point (More deformacion)
    reading_time = inspection_start + timedelta(minutes=6)
    plc_readings.append({
        'timestamp_plc': reading_time,
        'id_inspection': 1,
        'execution_id': 1001,
        'control_point_id': 4,
        'execution_type': 1,  # automatic
        'control_point_label': 1004,
        'x_control_point': 35.8,
        'y_control_point': 12.1,
        'z_control_point': 4.2,
        'plate_angle': 30.0,
        'control_point_creator': 1,
        'program_creator': 1,
        'program_version': 2103,
        'camera_id': 2,
        'filming_type': 2,  # photo
        'last_photo_request_timestamp': int(reading_time.timestamp()),
        'new_photos_available': True,
        'photo_count': 2,  # More deformacion photos
        'processed': False
    })
    
    # Reading 5: Fourth control point (Additional photos)
    reading_time = inspection_start + timedelta(minutes=8)
    plc_readings.append({
        'timestamp_plc': reading_time,
        'id_inspection': 1,
        'execution_id': 1001,
        'control_point_id': 5,
        'execution_type': 1,  # automatic
        'control_point_label': 1005,
        'x_control_point': 45.2,
        'y_control_point': 18.9,
        'z_control_point': 6.1,
        'plate_angle': 45.0,
        'control_point_creator': 1,
        'program_creator': 1,
        'program_version': 2103,
        'camera_id': 3,
        'filming_type': 2,  # photo
        'last_photo_request_timestamp': int(reading_time.timestamp()),
        'new_photos_available': True,
        'photo_count': 3,  # Additional photos
        'processed': False
    })
    
    # Reading 6: Fifth control point (More photos)
    reading_time = inspection_start + timedelta(minutes=10)
    plc_readings.append({
        'timestamp_plc': reading_time,
        'id_inspection': 1,
        'execution_id': 1001,
        'control_point_id': 6,
        'execution_type': 1,  # automatic
        'control_point_label': 1006,
        'x_control_point': 55.7,
        'y_control_point': 22.3,
        'z_control_point': 7.8,
        'plate_angle': 60.0,
        'control_point_creator': 1,
        'program_creator': 1,
        'program_version': 2103,
        'camera_id': 1,
        'filming_type': 2,  # photo
        'last_photo_request_timestamp': int(reading_time.timestamp()),
        'new_photos_available': True,
        'photo_count': 2,  # More photos
        'processed': False
    })
    
    # Reading 7: Final control point (Completion)
    reading_time = inspection_start + timedelta(minutes=12)
    plc_readings.append({
        'timestamp_plc': reading_time,
        'id_inspection': 1,
        'execution_id': 1001,
        'control_point_id': 7,
        'execution_type': 1,  # automatic
        'control_point_label': 1007,
        'x_control_point': 65.1,
        'y_control_point': 25.6,
        'z_control_point': 8.5,
        'plate_angle': 90.0,
        'control_point_creator': 1,
        'program_creator': 1,
        'program_version': 2103,
        'camera_id': 2,
        'filming_type': 2,  # photo
        'last_photo_request_timestamp': int(reading_time.timestamp()),
        'new_photos_available': True,
        'photo_count': 3,  # Final photos
        'processed': False
    })
    
    # Reading 8: Inspection completion
    reading_time = inspection_end
    plc_readings.append({
        'timestamp_plc': reading_time,
        'id_inspection': 1,
        'execution_id': 1001,
        'control_point_id': 8,
        'execution_type': 1,  # automatic
        'control_point_label': 1008,
        'x_control_point': 75.0,
        'y_control_point': 30.0,
        'z_control_point': 10.0,
        'plate_angle': 0.0,
        'control_point_creator': 1,
        'program_creator': 1,
        'program_version': 2103,
        'camera_id': 3,
        'filming_type': 2,  # photo
        'last_photo_request_timestamp': int(reading_time.timestamp()),
        'new_photos_available': False,
        'photo_count': 0,
        'processed': False
    })
    
    # Create PLC reading records
    created_readings = []
    for reading_data in plc_readings:
        try:
            reading = PlcReading.objects.create(**reading_data)
            created_readings.append(reading)
            print(f"Created PLC reading {reading.id} at {reading.timestamp_plc}")
        except Exception as e:
            print(f"Error creating PLC reading: {e}")
    
    print(f"\nSuccessfully created {len(created_readings)} PLC readings")
    return created_readings

def main():
    """Generate PLC data for inspection 1"""
    print("Generating PLC Data for Inspection 1")
    print("====================================")
    
    try:
        readings = generate_plc_data_for_inspection_1()
        print(f"\nGenerated {len(readings)} PLC readings")
        print("These readings can now be processed by plc_data_processor.py")
        
        # Show summary
        print("\nSummary of generated data:")
        for reading in readings:
            print(f"  Reading {reading.id}: Control Point {reading.control_point_id}, "
                  f"Photos: {reading.photo_count}, Time: {reading.timestamp_plc}")
                  
    except Exception as e:
        print(f"Error generating PLC data: {e}")

if __name__ == "__main__":
    main()
