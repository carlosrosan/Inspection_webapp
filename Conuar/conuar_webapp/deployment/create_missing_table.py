#!/usr/bin/env python
"""
Simple script to create the missing main_inspection table.
This script can be run independently to fix the missing table issue.
"""

import os
import sys
import pymysql
from pymysql import Error
import getpass

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_unicode_ci',
    'connect_timeout': 60,
    'read_timeout': 60,
    'write_timeout': 60
}

DATABASE_NAME = 'conuar_webapp'

def get_password():
    """Get MySQL password securely"""
    return getpass.getpass("Enter MySQL password: ")

def create_database_connection(password, database=None):
    """Create database connection"""
    try:
        config = DB_CONFIG.copy()
        config['password'] = password
        config['charset'] = 'utf8mb4'
        config['autocommit'] = True
        if database:
            config['database'] = database
        
        connection = pymysql.connect(**config)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error connecting to MySQL: {e}")
        return None

def check_table_exists(cursor, table_name):
    """Check if a table exists in the database"""
    try:
        cursor.execute(f"""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = DATABASE() 
            AND table_name = '{table_name}'
        """)
        return cursor.fetchone()[0] > 0
    except Error:
        return False

def create_missing_inspection_table(connection):
    """Create the main_inspection table if it doesn't exist"""
    cursor = connection.cursor()
    
    try:
        # Check if main_inspection table exists
        if not check_table_exists(cursor, 'main_inspection'):
            print("🔧 Creating missing main_inspection table...")
            cursor.execute("""
                CREATE TABLE main_inspection (
                    id bigint AUTO_INCREMENT NOT NULL PRIMARY KEY,
                    title varchar(200) NOT NULL DEFAULT 'Inspección de Combustible ArByte',
                    description longtext NOT NULL,
                    tipo_combustible varchar(20) NOT NULL DEFAULT 'uranio',
                    status varchar(20) NOT NULL DEFAULT 'completed',
                    product_name varchar(200),
                    product_code varchar(100) NOT NULL DEFAULT '',
                    batch_number varchar(100) NOT NULL DEFAULT '',
                    serial_number varchar(100) NOT NULL DEFAULT '',
                    location varchar(200) NOT NULL DEFAULT '',
                    inspection_date datetime(6) NOT NULL,
                    completed_date datetime(6),
                    result longtext NOT NULL,
                    notes longtext NOT NULL,
                    recommendations longtext NOT NULL,
                    defecto_encontrado bool NOT NULL DEFAULT 0,
                    created_at datetime(6) NOT NULL,
                    updated_at datetime(6) NOT NULL,
                    inspector_id bigint NOT NULL,
                    KEY main_inspection_inspector_id_7c8b8f1f (inspector_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            print("✅ main_inspection table created successfully")
            
            # Add foreign key constraint if main_user table exists
            if check_table_exists(cursor, 'main_user'):
                try:
                    cursor.execute("""
                        ALTER TABLE main_inspection 
                        ADD CONSTRAINT main_inspection_inspector_id_7c8b8f1f_fk_main_user_id 
                        FOREIGN KEY (inspector_id) REFERENCES main_user (id)
                    """)
                    print("✅ Foreign key constraint added to main_inspection")
                except Error as e:
                    print(f"⚠️  Warning: Could not add foreign key constraint: {e}")
            
            # Insert default inspection data
            cursor.execute("""
                INSERT IGNORE INTO main_inspection 
                (id, title, description, tipo_combustible, status, product_name, product_code, batch_number, location, inspection_date, created_at, updated_at, inspector_id)
                VALUES 
                (1, 'Inspección de Combustible ArByte', 'Inspección de calidad de combustible utilizando el sistema ArByte-3000', 'uranio', 'completed', 'Combustible Industrial', 'COMB-001', 'LOTE-2024-001', 'Planta de Inspección ArByte', NOW(), NOW(), NOW(), 1)
            """)
            print("✅ Default inspection data inserted")
            
        else:
            print("✅ main_inspection table already exists")
            
    except Error as e:
        print(f"❌ Error creating main_inspection table: {e}")
        return False
    finally:
        cursor.close()
    
    return True

def main():
    """Main function to create missing table"""
    print("🚀 Creating Missing main_inspection Table")
    print("=" * 50)
    
    # Get password
    password = get_password()
    
    # Create connection to database
    connection = create_database_connection(password, DATABASE_NAME)
    if not connection:
        print("❌ Failed to connect to MySQL database")
        return False
    
    try:
        # Create missing inspection table
        success = create_missing_inspection_table(connection)
        
        if success:
            print("\n✅ Table creation completed successfully!")
            print("The main_inspection table has been created and is ready to use.")
        else:
            print("\n❌ Table creation failed!")
            
        return success
        
    except Error as e:
        print(f"❌ Database operation failed: {e}")
        return False
    finally:
        if connection and connection.open:
            connection.close()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
