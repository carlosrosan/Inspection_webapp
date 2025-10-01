#!/usr/bin/env python3
"""
PLC Data Reader Test - Sistema Conuar
Simple script to read Modbus PLC data and log to CSV file
"""

import time
import csv
import os
from datetime import datetime
from typing import Dict, Optional

# Import Modbus library
try:
    from pyModbusTCP.client import ModbusClient
except ImportError:
    print("Error: pyModbusTCP not installed. Run: pip install pyModbusTCP")
    exit(1)

class PlcDataReaderTest:
    """Simple class to read PLC data and write to CSV"""
    
    def __init__(self, plc_ip: str = '127.0.0.1', plc_port: int = 502):
        self.plc_ip = plc_ip
        self.plc_port = plc_port
        self.plc_client = None
        self.is_running = False
        
        # PLC Register mapping - 5 numeric registers
        self.register_map = {
            'register_1': 0,
            'register_2': 1,
            'register_3': 2,
            'register_4': 3,
            'register_5': 4,
        }
        
        # CSV file setup - Fixed filename
        self.csv_filename = "plc_data_reader_test.csv"
        self.csv_file = None
        self.csv_writer = None
    
    def connect_to_plc(self) -> bool:
        """Connect to PLC"""
        try:
            print(f"Attempting to connect to PLC at {self.plc_ip}:{self.plc_port}...")
            self.plc_client = ModbusClient(
                host=self.plc_ip,
                port=self.plc_port,
                auto_open=True,
                auto_close=False,
                timeout=5.0
            )
            
            if self.plc_client.open():
                print(f"✓ Successfully connected to PLC at {self.plc_ip}:{self.plc_port}")
                return True
            else:
                print(f"✗ Failed to connect to PLC at {self.plc_ip}:{self.plc_port}")
                return False
                
        except Exception as e:
            print(f"✗ Error connecting to PLC: {e}")
            return False
    
    def disconnect_from_plc(self):
        """Disconnect from PLC"""
        if self.plc_client:
            self.plc_client.close()
            print("Disconnected from PLC")
    
    def read_plc_data(self) -> Optional[Dict]:
        """Read all registers from PLC and return as dictionary"""
        try:
            if not self.plc_client or not self.plc_client.is_open:
                print("PLC client not connected")
                return None
            
            data = {}
            data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            
            # Read all 5 numeric registers
            for field, register in self.register_map.items():
                result = self.plc_client.read_holding_registers(register, 1)
                if result:
                    data[field] = result[0]
                else:
                    print(f"Warning: Failed to read register {register} for field {field}")
                    data[field] = 0
            
            return data
            
        except Exception as e:
            print(f"Error reading PLC data: {e}")
            return None
    
    def initialize_csv(self):
        """Initialize CSV file - append mode, write headers only if new file"""
        try:
            # Get script directory
            script_dir = os.path.dirname(os.path.abspath(__file__))
            csv_path = os.path.join(script_dir, self.csv_filename)
            
            # Check if file already exists
            file_exists = os.path.isfile(csv_path)
            
            # Open in append mode
            self.csv_file = open(csv_path, 'a', newline='', encoding='utf-8')
            
            # Create header row with all fields
            headers = ['timestamp'] + list(self.register_map.keys())
            
            self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=headers)
            
            # Only write header if file is new
            if not file_exists:
                self.csv_writer.writeheader()
                self.csv_file.flush()
                print(f"✓ CSV file created: {csv_path}")
            else:
                print(f"✓ Appending to existing CSV file: {csv_path}")
            
        except Exception as e:
            print(f"Error initializing CSV file: {e}")
            raise
    
    def write_to_csv(self, data: Dict):
        """Write data row to CSV file"""
        try:
            if self.csv_writer:
                self.csv_writer.writerow(data)
                self.csv_file.flush()  # Ensure data is written immediately
                
        except Exception as e:
            print(f"Error writing to CSV: {e}")
    
    def close_csv(self):
        """Close CSV file"""
        if self.csv_file:
            self.csv_file.close()
            print("CSV file closed")
    
    def run_reading_loop(self, duration_minutes: int = 60, interval_seconds: int = 5):
        """Execute main reading loop"""
        print(f"\n{'='*60}")
        print(f"PLC Data Reader Test - Starting")
        print(f"{'='*60}")
        print(f"Duration: {duration_minutes} minutes")
        print(f"Read interval: {interval_seconds} seconds")
        print(f"CSV file: {self.csv_filename}")
        print(f"{'='*60}\n")
        
        if not self.connect_to_plc():
            print("Error: Could not connect to PLC. Exiting.")
            return
        
        self.initialize_csv()
        
        self.is_running = True
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)
        read_count = 0
        
        try:
            while self.is_running and time.time() < end_time:
                # Read data from PLC
                plc_data = self.read_plc_data()
                
                if plc_data:
                    # Write to CSV
                    self.write_to_csv(plc_data)
                    read_count += 1
                    
                    # Display summary
                    print(f"[{read_count}] {plc_data['timestamp']} - "
                          f"R1: {plc_data.get('register_1', 0)}, "
                          f"R2: {plc_data.get('register_2', 0)}, "
                          f"R3: {plc_data.get('register_3', 0)}, "
                          f"R4: {plc_data.get('register_4', 0)}, "
                          f"R5: {plc_data.get('register_5', 0)}")
                else:
                    print("Warning: No data received from PLC")
                
                # Wait before next reading
                time.sleep(interval_seconds)
                
        except KeyboardInterrupt:
            print("\n\nReading interrupted by user (Ctrl+C)")
        except Exception as e:
            print(f"\nError in reading loop: {e}")
        finally:
            self.is_running = False
            self.disconnect_from_plc()
            self.close_csv()
            
            elapsed_time = time.time() - start_time
            print(f"\n{'='*60}")
            print(f"PLC Data Reader Test - Summary")
            print(f"{'='*60}")
            print(f"Total readings: {read_count}")
            print(f"Elapsed time: {elapsed_time:.1f} seconds ({elapsed_time/60:.1f} minutes)")
            print(f"CSV file: {self.csv_filename}")
            print(f"{'='*60}\n")
    
    def stop_reading(self):
        """Stop the reading loop"""
        self.is_running = False
        print("Stopping PLC reading...")

def main():
    """Main function"""
    print("\n" + "="*60)
    print("PLC Data Reader Test - Sistema Conuar")
    print("="*60)
    
    # Configuration
    PLC_IP = '127.0.0.1'
    PLC_PORT = 502
    DURATION_MINUTES = 60  # Run for 60 minutes
    READ_INTERVAL_SECONDS = 5  # Read every 5 seconds
    
    print(f"PLC IP: {PLC_IP}")
    print(f"PLC Port: {PLC_PORT}")
    
    # Create reader instance
    reader = PlcDataReaderTest(plc_ip=PLC_IP, plc_port=PLC_PORT)
    
    try:
        # Run reading loop
        reader.run_reading_loop(
            duration_minutes=DURATION_MINUTES,
            interval_seconds=READ_INTERVAL_SECONDS
        )
    except Exception as e:
        print(f"Fatal error: {e}")
    finally:
        reader.stop_reading()

if __name__ == "__main__":
    main()
