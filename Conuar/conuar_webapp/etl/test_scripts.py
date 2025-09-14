#!/usr/bin/env python3
"""
Test script to verify both PLC scripts work correctly
"""

import os
import sys
import django

# Agregar proyecto Django al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

def test_plc_reader():
    """Test PLC data reader script"""
    print("Testing PLC Data Reader...")
    try:
        from plc_data_reader import PlcDataReader
        reader = PlcDataReader()
        print("✓ PLC Data Reader imported successfully")
        print(f"  - Register map has {len(reader.register_map)} fields")
        print(f"  - PLC IP: {reader.config.plc_ip}")
        print(f"  - PLC Port: {reader.config.plc_port}")
        return True
    except Exception as e:
        print(f"✗ Error importing PLC Data Reader: {e}")
        return False

def test_plc_processor():
    """Test PLC data processor script"""
    print("\nTesting PLC Data Processor...")
    try:
        from plc_data_processor import PlcDataProcessor
        processor = PlcDataProcessor()
        print("✓ PLC Data Processor imported successfully")
        print(f"  - Execution type map: {processor.execution_type_map}")
        print(f"  - Filming type map: {processor.filming_type_map}")
        return True
    except Exception as e:
        print(f"✗ Error importing PLC Data Processor: {e}")
        return False

def test_models():
    """Test that all required models are available"""
    print("\nTesting Models...")
    try:
        from main.models import PlcReading, Inspection, InspectionMachine, InspectionPhoto, InspectionPlcEvent
        print("✓ All required models imported successfully")
        
        # Test PlcReading model
        print(f"  - PlcReading fields: {[f.name for f in PlcReading._meta.fields]}")
        return True
    except Exception as e:
        print(f"✗ Error importing models: {e}")
        return False

def main():
    """Run all tests"""
    print("PLC Scripts Test - Sistema Conuar")
    print("=================================")
    
    tests = [
        test_models,
        test_plc_reader,
        test_plc_processor,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print(f"\nTest Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ All tests passed! Scripts are ready to use.")
    else:
        print("✗ Some tests failed. Please check the errors above.")

if __name__ == "__main__":
    main()
