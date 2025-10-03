#!/usr/bin/env python
"""
Script to create MySQL database and all tables for the Conuar Inspection Webapp
This script bypasses Django's manage.py and creates the database directly using SQL.
"""

import os
import sys
import mysql.connector
from mysql.connector import Error
from pathlib import Path
import getpass

# Database configuration - you can modify these values
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',  # Change this to your MySQL username
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_unicode_ci'
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
        if database:
            config['database'] = database
        
        connection = mysql.connector.connect(**config)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

def create_database(cursor, db_name):
    """Create the database if it doesn't exist"""
    try:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        print(f"✅ Database '{db_name}' created successfully or already exists")
        return True
    except Error as e:
        print(f"❌ Error creating database: {e}")
        return False

def get_sql_create_statements():
    """Return SQL statements to create all tables"""
    return [
        # Create database
        f"USE {DATABASE_NAME};",
        
        # Django auth tables
        """
        CREATE TABLE IF NOT EXISTS auth_group (
            id bigint AUTO_INCREMENT NOT NULL PRIMARY KEY,
            name varchar(150) NOT NULL UNIQUE
        );
        """,
        
        """
        CREATE TABLE IF NOT EXISTS auth_group_permissions (
            id bigint AUTO_INCREMENT NOT NULL PRIMARY KEY,
            group_id bigint NOT NULL,
            permission_id bigint NOT NULL,
            UNIQUE KEY auth_group_permissions_group_id_permission_id_0cd325b0_uniq (group_id, permission_id),
            KEY auth_group_permissions_group_id_b120cbf9 (group_id),
            KEY auth_group_permissions_permission_id_84c5c92e (permission_id)
        );
        """,
        
        """
        CREATE TABLE IF NOT EXISTS auth_permission (
            id bigint AUTO_INCREMENT NOT NULL PRIMARY KEY,
            name varchar(255) NOT NULL,
            content_type_id bigint NOT NULL,
            codename varchar(100) NOT NULL,
            UNIQUE KEY auth_permission_content_type_id_codename_01ab375a_uniq (content_type_id, codename),
            KEY auth_permission_content_type_id_2f476e4b (content_type_id)
        );
        """,
        
        """
        CREATE TABLE IF NOT EXISTS django_content_type (
            id bigint AUTO_INCREMENT NOT NULL PRIMARY KEY,
            app_label varchar(100) NOT NULL,
            model varchar(100) NOT NULL,
            UNIQUE KEY django_content_type_app_label_model_76bd3d3b_uniq (app_label, model)
        );
        """,
        
        """
        CREATE TABLE IF NOT EXISTS django_migrations (
            id bigint AUTO_INCREMENT NOT NULL PRIMARY KEY,
            app varchar(255) NOT NULL,
            name varchar(255) NOT NULL,
            applied datetime(6) NOT NULL
        );
        """,
        
        """
        CREATE TABLE IF NOT EXISTS django_session (
            session_key varchar(40) NOT NULL PRIMARY KEY,
            session_data longtext NOT NULL,
            expire_date datetime(6) NOT NULL,
            KEY django_session_expire_date_a5c62663 (expire_date)
        );
        """,
        
        # Main User table (extends Django's AbstractUser)
        """
        CREATE TABLE IF NOT EXISTS main_user (
            id bigint AUTO_INCREMENT NOT NULL PRIMARY KEY,
            password varchar(128) NOT NULL,
            last_login datetime(6),
            is_superuser bool NOT NULL,
            username varchar(150) NOT NULL UNIQUE,
            first_name varchar(150) NOT NULL,
            last_name varchar(150) NOT NULL,
            email varchar(254) NOT NULL,
            is_staff bool NOT NULL,
            is_active bool NOT NULL,
            date_joined datetime(6) NOT NULL,
            created_at datetime(6) NOT NULL,
            updated_at datetime(6) NOT NULL,
            password_reset_enabled bool NOT NULL DEFAULT 0,
            password_reset_token varchar(100),
            password_expiry_date datetime(6),
            password_expired bool NOT NULL DEFAULT 0
        );
        """,
        
        """
        CREATE TABLE IF NOT EXISTS main_user_groups (
            id bigint AUTO_INCREMENT NOT NULL PRIMARY KEY,
            user_id bigint NOT NULL,
            group_id bigint NOT NULL,
            UNIQUE KEY main_user_groups_user_id_group_id_59c0b32f_uniq (user_id, group_id),
            KEY main_user_groups_user_id_52afd551 (user_id),
            KEY main_user_groups_group_id_97559544 (group_id)
        );
        """,
        
        """
        CREATE TABLE IF NOT EXISTS main_user_user_permissions (
            id bigint AUTO_INCREMENT NOT NULL PRIMARY KEY,
            user_id bigint NOT NULL,
            permission_id bigint NOT NULL,
            UNIQUE KEY main_user_user_permissions_user_id_permission_id_14a6b632_uniq (user_id, permission_id),
            KEY main_user_user_permissions_user_id_a95ead1b (user_id),
            KEY main_user_user_permissions_permission_id_1fbb5f2c (permission_id)
        );
        """,
        
        # Inspection table
        """
        CREATE TABLE IF NOT EXISTS main_inspection (
            id bigint AUTO_INCREMENT NOT NULL PRIMARY KEY,
            title varchar(200) NOT NULL DEFAULT 'Inspección de Combustible ArByte',
            description longtext NOT NULL DEFAULT 'Inspección de calidad de combustible utilizando el sistema ArByte-3000',
            tipo_combustible varchar(20) NOT NULL DEFAULT 'uranio',
            status varchar(20) NOT NULL DEFAULT 'completed',
            product_name varchar(200),
            product_code varchar(100) NOT NULL DEFAULT '',
            batch_number varchar(100) NOT NULL DEFAULT '',
            serial_number varchar(100) NOT NULL DEFAULT '',
            location varchar(200) NOT NULL DEFAULT '',
            inspection_date datetime(6) NOT NULL,
            completed_date datetime(6),
            result longtext NOT NULL DEFAULT '',
            notes longtext NOT NULL DEFAULT '',
            recommendations longtext NOT NULL DEFAULT '',
            defecto_encontrado bool NOT NULL DEFAULT 0,
            created_at datetime(6) NOT NULL,
            updated_at datetime(6) NOT NULL,
            inspector_id bigint NOT NULL,
            KEY main_inspection_inspector_id_7c8b8f1f (inspector_id)
        );
        """,
        
        # Inspection Photo table
        """
        CREATE TABLE IF NOT EXISTS main_inspectionphoto (
            id bigint AUTO_INCREMENT NOT NULL PRIMARY KEY,
            photo varchar(100) NOT NULL,
            caption varchar(200) NOT NULL DEFAULT '',
            photo_type varchar(50) NOT NULL DEFAULT '',
            uploaded_at datetime(6) NOT NULL,
            defecto_encontrado bool NOT NULL DEFAULT 0,
            inspection_id bigint NOT NULL,
            KEY main_inspectionphoto_inspection_id_8b2c8f1f (inspection_id)
        );
        """,
        
        # Inspection Machine table
        """
        CREATE TABLE IF NOT EXISTS main_inspectionmachine (
            id bigint AUTO_INCREMENT NOT NULL PRIMARY KEY,
            machine_id varchar(50) NOT NULL UNIQUE DEFAULT 'MAQ-001',
            name varchar(100) NOT NULL DEFAULT 'Analizador de Combustible ArByte-3000',
            model varchar(50) NOT NULL DEFAULT 'AB-3000',
            version varchar(20) NOT NULL DEFAULT 'v2.1.3',
            status varchar(20) NOT NULL DEFAULT 'offline',
            current_stage varchar(30),
            total_inspections int unsigned NOT NULL DEFAULT 0,
            inspections_today int unsigned NOT NULL DEFAULT 0,
            uptime_hours double NOT NULL DEFAULT 0,
            last_inspection datetime(6),
            last_maintenance datetime(6),
            success_rate double NOT NULL DEFAULT 100,
            average_inspection_time double NOT NULL DEFAULT 0,
            total_defects_found int unsigned NOT NULL DEFAULT 0,
            last_status_change datetime(6) NOT NULL,
            created_at datetime(6) NOT NULL,
            updated_at datetime(6) NOT NULL,
            current_inspection_id bigint UNIQUE,
            KEY main_inspectionmachine_current_inspection_id_8b2c8f1f (current_inspection_id)
        );
        """,
        
        # Machine Log table
        """
        CREATE TABLE IF NOT EXISTS main_machinelog (
            id bigint AUTO_INCREMENT NOT NULL PRIMARY KEY,
            log_type varchar(20) NOT NULL,
            message longtext NOT NULL,
            timestamp datetime(6) NOT NULL,
            machine_id bigint NOT NULL,
            KEY main_machinelog_machine_id_7c8b8f1f (machine_id)
        );
        """,
        
        # System Configuration table
        """
        CREATE TABLE IF NOT EXISTS main_systemconfiguration (
            id bigint AUTO_INCREMENT NOT NULL PRIMARY KEY,
            media_storage_path varchar(500) NOT NULL DEFAULT 'media/inspection_photos/Inspection_1/',
            camera_1_ip char(39) NOT NULL DEFAULT '192.168.1.100',
            camera_2_ip char(39) NOT NULL DEFAULT '192.168.1.101',
            camera_3_ip char(39) NOT NULL DEFAULT '192.168.1.102',
            plc_ip char(39) NOT NULL DEFAULT '192.168.1.50',
            plc_port int unsigned NOT NULL DEFAULT 502,
            created_at datetime(6) NOT NULL,
            updated_at datetime(6) NOT NULL,
            updated_by_id bigint,
            KEY main_systemconfiguration_updated_by_id_7c8b8f1f (updated_by_id)
        );
        """,
        
        # Inspection PLC Event table
        """
        CREATE TABLE IF NOT EXISTS main_inspectionplcevent (
            id bigint AUTO_INCREMENT NOT NULL PRIMARY KEY,
            timestamp_plc datetime(6) NOT NULL,
            execution_id varchar(100) NOT NULL,
            control_point_id varchar(100) NOT NULL,
            execution_type varchar(20) NOT NULL,
            control_point_label varchar(200) NOT NULL DEFAULT '',
            x_control_point double NOT NULL,
            y_control_point double NOT NULL,
            z_control_point double NOT NULL,
            plate_angle double NOT NULL,
            control_point_creator varchar(100) NOT NULL,
            program_creator varchar(100) NOT NULL,
            program_version varchar(50) NOT NULL,
            camera_id varchar(50) NOT NULL,
            filming_type varchar(20) NOT NULL,
            last_photo_request_timestamp datetime(6),
            message_type varchar(30) NOT NULL DEFAULT 'machine_routine_step',
            message_body longtext NOT NULL DEFAULT '',
            fuel_rig_id varchar(50) NOT NULL DEFAULT '',
            created_at datetime(6) NOT NULL,
            updated_at datetime(6) NOT NULL,
            id_inspection_id bigint NOT NULL,
            KEY main_inspectionplcevent_id_inspection_id_7c8b8f1f (id_inspection_id)
        );
        """,
        
        # PLC Reading table
        """
        CREATE TABLE IF NOT EXISTS main_plcreading (
            id bigint AUTO_INCREMENT NOT NULL PRIMARY KEY,
            timestamp_plc datetime(6) NOT NULL,
            id_inspection bigint NOT NULL,
            execution_id bigint NOT NULL,
            control_point_id bigint NOT NULL,
            execution_type bigint NOT NULL,
            control_point_label bigint NOT NULL,
            tipo_combustible bigint NOT NULL,
            x_control_point double NOT NULL,
            y_control_point double NOT NULL,
            z_control_point double NOT NULL,
            plate_angle double NOT NULL,
            control_point_creator bigint NOT NULL,
            program_creator bigint NOT NULL,
            program_version bigint NOT NULL,
            camera_id bigint NOT NULL,
            filming_type bigint NOT NULL,
            last_photo_request_timestamp bigint NOT NULL,
            new_photos_available bool NOT NULL DEFAULT 0,
            photo_count bigint NOT NULL DEFAULT 0,
            message_type varchar(30) NOT NULL DEFAULT 'machine_routine_step',
            message_body longtext NOT NULL DEFAULT '',
            fuel_rig_id varchar(50) NOT NULL DEFAULT '',
            processed bool NOT NULL DEFAULT 0,
            processing_error longtext NOT NULL DEFAULT '',
            created_at datetime(6) NOT NULL,
            updated_at datetime(6) NOT NULL,
            KEY main_plcreading_processed_timestamp_plc_7c8b8f1f (processed, timestamp_plc),
            KEY main_plcreading_id_inspection_7c8b8f1f (id_inspection)
        );
        """,
        
        # Foreign Key Constraints
        """
        ALTER TABLE auth_group_permissions 
        ADD CONSTRAINT auth_group_permissions_group_id_b120cbf9_fk_auth_group_id 
        FOREIGN KEY (group_id) REFERENCES auth_group (id);
        """,
        
        """
        ALTER TABLE auth_group_permissions 
        ADD CONSTRAINT auth_group_permissions_permission_id_84c5c92e_fk_auth_permission_id 
        FOREIGN KEY (permission_id) REFERENCES auth_permission (id);
        """,
        
        """
        ALTER TABLE auth_permission 
        ADD CONSTRAINT auth_permission_content_type_id_2f476e4b_fk_django_content_type_id 
        FOREIGN KEY (content_type_id) REFERENCES django_content_type (id);
        """,
        
        """
        ALTER TABLE main_user_groups 
        ADD CONSTRAINT main_user_groups_user_id_52afd551_fk_main_user_id 
        FOREIGN KEY (user_id) REFERENCES main_user (id);
        """,
        
        """
        ALTER TABLE main_user_groups 
        ADD CONSTRAINT main_user_groups_group_id_97559544_fk_auth_group_id 
        FOREIGN KEY (group_id) REFERENCES auth_group (id);
        """,
        
        """
        ALTER TABLE main_user_user_permissions 
        ADD CONSTRAINT main_user_user_permissions_user_id_a95ead1b_fk_main_user_id 
        FOREIGN KEY (user_id) REFERENCES main_user (id);
        """,
        
        """
        ALTER TABLE main_user_user_permissions 
        ADD CONSTRAINT main_user_user_permissions_permission_id_1fbb5f2c_fk_auth_permission_id 
        FOREIGN KEY (permission_id) REFERENCES auth_permission (id);
        """,
        
        """
        ALTER TABLE main_inspection 
        ADD CONSTRAINT main_inspection_inspector_id_7c8b8f1f_fk_main_user_id 
        FOREIGN KEY (inspector_id) REFERENCES main_user (id);
        """,
        
        """
        ALTER TABLE main_inspectionphoto 
        ADD CONSTRAINT main_inspectionphoto_inspection_id_8b2c8f1f_fk_main_inspection_id 
        FOREIGN KEY (inspection_id) REFERENCES main_inspection (id);
        """,
        
        """
        ALTER TABLE main_inspectionmachine 
        ADD CONSTRAINT main_inspectionmachine_current_inspection_id_8b2c8f1f_fk_main_inspection_id 
        FOREIGN KEY (current_inspection_id) REFERENCES main_inspection (id);
        """,
        
        """
        ALTER TABLE main_machinelog 
        ADD CONSTRAINT main_machinelog_machine_id_7c8b8f1f_fk_main_inspectionmachine_id 
        FOREIGN KEY (machine_id) REFERENCES main_inspectionmachine (id);
        """,
        
        """
        ALTER TABLE main_systemconfiguration 
        ADD CONSTRAINT main_systemconfiguration_updated_by_id_7c8b8f1f_fk_main_user_id 
        FOREIGN KEY (updated_by_id) REFERENCES main_user (id);
        """,
        
        """
        ALTER TABLE main_inspectionplcevent 
        ADD CONSTRAINT main_inspectionplcevent_id_inspection_id_7c8b8f1f_fk_main_inspection_id 
        FOREIGN KEY (id_inspection_id) REFERENCES main_inspection (id);
        """,
    ]

def execute_sql_statements(connection, statements):
    """Execute SQL statements"""
    cursor = connection.cursor()
    
    for i, statement in enumerate(statements):
        try:
            if statement.strip():
                cursor.execute(statement)
                print(f"✅ Executed statement {i+1}/{len(statements)}")
        except Error as e:
            print(f"⚠️  Warning executing statement {i+1}: {e}")
            # Continue with other statements
    
    connection.commit()
    cursor.close()

def insert_initial_data(connection):
    """Insert initial data into the database"""
    cursor = connection.cursor()
    
    try:
        # Insert default user
        cursor.execute("""
            INSERT IGNORE INTO main_user 
            (id, password, is_superuser, username, first_name, last_name, email, is_staff, is_active, date_joined, created_at, updated_at, password_reset_enabled, password_expired)
            VALUES 
            (1, 'pbkdf2_sha256$600000$dummy$dummy', 1, 'admin', 'System', 'Administrator', 'admin@conuar.com', 1, 1, NOW(), NOW(), NOW(), 0, 0)
        """)
        
        # Insert system inspector user
        cursor.execute("""
            INSERT IGNORE INTO main_user 
            (id, password, is_superuser, username, first_name, last_name, email, is_staff, is_active, date_joined, created_at, updated_at, password_reset_enabled, password_expired)
            VALUES 
            (2, 'pbkdf2_sha256$600000$dummy$dummy', 0, 'system_inspector', 'Sistema', 'Inspector', 'system@arbyte.com', 1, 1, NOW(), NOW(), NOW(), 0, 0)
        """)
        
        # Insert default inspection
        cursor.execute("""
            INSERT IGNORE INTO main_inspection 
            (id, title, description, tipo_combustible, status, product_name, product_code, batch_number, location, inspection_date, created_at, updated_at, inspector_id)
            VALUES 
            (1, 'Inspección de Combustible ArByte', 'Inspección de calidad de combustible utilizando el sistema ArByte-3000', 'uranio', 'completed', 'Combustible Industrial', 'COMB-001', 'LOTE-2024-001', 'Planta de Inspección ArByte', NOW(), NOW(), NOW(), 2)
        """)
        
        # Insert default machine
        cursor.execute("""
            INSERT IGNORE INTO main_inspectionmachine 
            (id, machine_id, name, model, version, status, total_inspections, inspections_today, success_rate, created_at, updated_at, last_status_change, current_inspection_id)
            VALUES 
            (1, 'MAQ-001', 'Analizador de Combustible ArByte-3000', 'AB-3000', 'v2.1.3', 'idle', 1, 1, 100.0, NOW(), NOW(), NOW(), 1)
        """)
        
        # Insert default system configuration
        cursor.execute("""
            INSERT IGNORE INTO main_systemconfiguration 
            (id, media_storage_path, camera_1_ip, camera_2_ip, camera_3_ip, plc_ip, plc_port, created_at, updated_at)
            VALUES 
            (1, 'media/inspection_photos/Inspection_1/', '192.168.1.100', '192.168.1.101', '192.168.1.102', '192.168.1.50', 502, NOW(), NOW())
        """)
        
        connection.commit()
        print("✅ Initial data inserted successfully")
        
    except Error as e:
        print(f"❌ Error inserting initial data: {e}")
        connection.rollback()
    finally:
        cursor.close()

def main():
    """Main function to create database and tables"""
    print("🚀 Starting Conuar Inspection Webapp Database Setup")
    print("=" * 60)
    
    # Get password
    password = get_password()
    
    # Create initial connection (without database)
    connection = create_database_connection(password)
    if not connection:
        print("❌ Failed to connect to MySQL server")
        return False
    
    try:
        cursor = connection.cursor()
        
        # Create database
        if not create_database(cursor, DATABASE_NAME):
            return False
        
        cursor.close()
        connection.close()
        
        # Reconnect with database
        connection = create_database_connection(password, DATABASE_NAME)
        if not connection:
            print("❌ Failed to connect to database")
            return False
        
        # Execute SQL statements
        print("\n📝 Creating tables...")
        statements = get_sql_create_statements()
        execute_sql_statements(connection, statements)
        
        # Insert initial data
        print("\n📊 Inserting initial data...")
        insert_initial_data(connection)
        
        print("\n✅ Database setup completed successfully!")
        print(f"Database: {DATABASE_NAME}")
        print("Tables created:")
        print("- main_user (custom user authentication)")
        print("- main_inspection (inspection records)")
        print("- main_inspectionphoto (inspection photos)")
        print("- main_inspectionmachine (machine status)")
        print("- main_machinelog (machine logs)")
        print("- main_systemconfiguration (system settings)")
        print("- main_inspectionplcevent (PLC events)")
        print("- main_plcreading (PLC readings)")
        print("- Django system tables (auth, sessions, etc.)")
        
        print("\n🔑 Default users created:")
        print("- Username: admin (superuser)")
        print("- Username: system_inspector (staff user)")
        print("Note: You'll need to set passwords for these users through Django admin")
        
        return True
        
    except Error as e:
        print(f"❌ Database setup failed: {e}")
        return False
    finally:
        if connection and connection.is_connected():
            connection.close()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
