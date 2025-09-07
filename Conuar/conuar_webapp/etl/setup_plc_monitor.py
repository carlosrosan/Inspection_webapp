#!/usr/bin/env python3
"""
Setup script for PLC Inspection Monitor

This script helps configure the PLC monitoring system and test connections.
"""

import os
import sys
import django

# Add Django project to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from main.models import SystemConfiguration, Inspection, InspectionMachine
from pyModbusTCP.client import ModbusClient

def test_plc_connection():
    """Test connection to PLC"""
    config = SystemConfiguration.get_config()
    
    print(f"Testing PLC connection to {config.plc_ip}:{config.plc_port}")
    
    try:
        client = ModbusClient(
            host=config.plc_ip,
            port=config.plc_port,
            auto_open=True,
            auto_close=True
        )
        
        if client.open():
            print("✅ PLC connection successful!")
            
            # Test reading a register
            result = client.read_holding_registers(1, 1)
            if result:
                print(f"✅ Successfully read register 1: {result[0]}")
            else:
                print("⚠️  Could not read register 1")
            
            client.close()
            return True
        else:
            print("❌ Failed to connect to PLC")
            return False
            
    except Exception as e:
        print(f"❌ Error connecting to PLC: {e}")
        return False

def setup_database():
    """Setup database tables and initial data"""
    print("Setting up database...")
    
    try:
        # Get or create the single inspection
        inspection = Inspection.get_inspection()
        print(f"✅ Inspection setup: ID {inspection.id} - {inspection.title}")
        
        # Get or create the machine
        machine = InspectionMachine.get_machine()
        print(f"✅ Machine setup: {machine.name} - Status: {machine.status}")
        
        # Get or create system configuration
        config = SystemConfiguration.get_config()
        print(f"✅ System configuration: PLC {config.plc_ip}:{config.plc_port}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error setting up database: {e}")
        return False

def show_configuration():
    """Show current configuration"""
    config = SystemConfiguration.get_config()
    
    print("\nCurrent Configuration:")
    print("=====================")
    print(f"PLC IP: {config.plc_ip}")
    print(f"PLC Port: {config.plc_port}")
    print(f"Media Storage Path: {config.media_storage_path}")
    print(f"Camera 1 IP: {config.camera_1_ip}")
    print(f"Camera 2 IP: {config.camera_2_ip}")
    print(f"Camera 3 IP: {config.camera_3_ip}")

def main():
    """Main setup function"""
    print("PLC Inspection Monitor Setup")
    print("============================")
    
    # Show current configuration
    show_configuration()
    
    # Test database setup
    print("\n1. Testing database setup...")
    if not setup_database():
        print("❌ Database setup failed. Please check your Django configuration.")
        return
    
    # Test PLC connection
    print("\n2. Testing PLC connection...")
    if not test_plc_connection():
        print("❌ PLC connection failed. Please check:")
        print("   - PLC IP address and port in configuration")
        print("   - Network connectivity")
        print("   - PLC is running and accessible")
        return
    
    print("\n✅ Setup completed successfully!")
    print("\nTo run the PLC monitor:")
    print("python plc_inspection_monitor.py")
    
    print("\nTo install required dependencies:")
    print("pip install -r requirements.txt")

if __name__ == "__main__":
    main()
