#!/usr/bin/env python3
"""
PLC Data Reader Test - Sistema Conuar
Simple script to read CSV file with JSON data and save to MySQL database
"""

import time
import csv
import json
import os
import pymysql
from datetime import datetime
from typing import Dict, Optional
from pathlib import Path

class PlcDataReaderTest:
    """Simple class to read CSV with JSON data and save to MySQL"""
    
    def __init__(self, csv_input_file: str, db_config_file: str = 'db_config.json'):
        self.csv_input_file = csv_input_file
        self.db_config_file = db_config_file
        self.db_connection = None
        self.is_running = False
        self.db_config = None
    
    def load_db_config(self) -> bool:
        """Load database configuration from JSON file"""
        try:
            script_dir = Path(__file__).parent
            config_path = script_dir / self.db_config_file
            
            with open(config_path, 'r') as f:
                self.db_config = json.load(f)
            
            print(f"✓ Database configuration loaded from {config_path}")
            return True
        except Exception as e:
            print(f"✗ Error loading database configuration: {e}")
            return False
    
    def connect_to_database(self) -> bool:
        """Connect to MySQL database"""
        try:
            if not self.db_config:
                if not self.load_db_config():
                    return False
            
            print(f"Attempting to connect to MySQL database...")
            self.db_connection = pymysql.connect(
                host=self.db_config.get('HOST', 'localhost'),
                port=int(self.db_config.get('PORT', 3306)),
                user=self.db_config['USER'],
                password=self.db_config['PASSWORD'],
                database=self.db_config['NAME'],
                charset='utf8mb4',
                autocommit=True
            )
            
            print(f"✓ Successfully connected to MySQL database: {self.db_config['NAME']}")
            return True
                
        except Exception as e:
            print(f"✗ Error connecting to MySQL: {e}")
            return False
    
    def disconnect_from_database(self):
        """Disconnect from MySQL database"""
        if self.db_connection:
            self.db_connection.close()
            print("Disconnected from MySQL database")
    
    def save_to_database(self, timestamp: str, json_data: str) -> bool:
        """Save timestamp and JSON data to plc_data_raw table"""
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("""
                INSERT INTO plc_data_raw (timestamp, json_data, created_at)
                VALUES (%s, %s, NOW())
            """, (timestamp, json_data))
            cursor.close()
            return True
        except Exception as e:
            print(f"Error saving to database: {e}")
            return False
    
    def process_csv_file(self):
        """Read CSV file and save each JSON row to database"""
        print(f"\n{'='*60}")
        print(f"CSV to MySQL Processor - Starting")
        print(f"{'='*60}")
        print(f"Input CSV file: {self.csv_input_file}")
        print(f"{'='*60}\n")
        
        # Check if CSV file exists
        if not os.path.exists(self.csv_input_file):
            print(f"Error: CSV file not found: {self.csv_input_file}")
            return
        
        if not self.connect_to_database():
            print("Error: Could not connect to database. Exiting.")
            return
        
        self.is_running = True
        row_count = 0
        success_count = 0
        error_count = 0
        
        try:
            with open(self.csv_input_file, 'r', encoding='utf-8') as csvfile:
                for line_num, line in enumerate(csvfile, 1):
                    line = line.strip()
                    
                    if not line:
                        continue
                    
                    try:
                        # Parse JSON from line
                        json_obj = json.loads(line)
                        
                        # Extract timestamp (try different field names)
                        timestamp = json_obj.get('datetime') or json_obj.get('timestamp') or datetime.now().isoformat()
                        
                        # Convert timestamp to MySQL datetime format if needed
                        if 'T' in timestamp and 'Z' in timestamp:
                            # ISO format like "2025-11-02T16:33:20.607Z"
                            timestamp = timestamp.replace('T', ' ').replace('Z', '')
                        
                        # Save to database
                        if self.save_to_database(timestamp, line):
                            success_count += 1
                            print(f"[{line_num}] ✓ Saved: {timestamp[:19]} - {len(line)} bytes")
                        else:
                            error_count += 1
                            print(f"[{line_num}] ✗ Failed to save row")
                        
                        row_count += 1
                        
                    except json.JSONDecodeError as e:
                        error_count += 1
                        print(f"[{line_num}] ✗ JSON parse error: {e}")
                    except Exception as e:
                        error_count += 1
                        print(f"[{line_num}] ✗ Error processing row: {e}")
                
        except KeyboardInterrupt:
            print("\n\nProcessing interrupted by user (Ctrl+C)")
        except Exception as e:
            print(f"\nError reading CSV file: {e}")
        finally:
            self.is_running = False
            self.disconnect_from_database()
            
            print(f"\n{'='*60}")
            print(f"CSV to MySQL Processor - Summary")
            print(f"{'='*60}")
            print(f"Total rows processed: {row_count}")
            print(f"Successful inserts: {success_count}")
            print(f"Errors: {error_count}")
            print(f"{'='*60}\n")
    
    def stop_processing(self):
        """Stop the processing"""
        self.is_running = False
        print("Stopping CSV processing...")

def main():
    """Main function"""
    print("\n" + "="*60)
    print("CSV to MySQL Processor - Sistema Conuar")
    print("="*60)
    
    # Configuration - Using absolute path
    CSV_INPUT_FILE = r"C:\Users\Admin\Documents\Inspection_webapp\Conuar\conuar_webapp\etl\Conuar test NodeRed\plc_reads\plc_reads_nodered.csv"
    script_dir = Path(__file__).parent
    DB_CONFIG_FILE = script_dir / "db_config.json"
    
    print(f"CSV Input File: {CSV_INPUT_FILE}")
    print(f"Database Config: {DB_CONFIG_FILE}")
    
    # Create reader instance
    reader = PlcDataReaderTest(
        csv_input_file=CSV_INPUT_FILE,
        db_config_file=str(DB_CONFIG_FILE)
    )
    
    try:
        # Process CSV file
        reader.process_csv_file()
    except Exception as e:
        print(f"Fatal error: {e}")
    finally:
        reader.stop_processing()

if __name__ == "__main__":
    main()
