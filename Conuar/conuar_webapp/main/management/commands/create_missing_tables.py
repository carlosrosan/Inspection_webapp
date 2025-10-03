#!/usr/bin/env python
"""
Django management command to create missing database tables.
This command can be used to create tables that might be missing from the database.
"""

from django.core.management.base import BaseCommand
from django.db import connection
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Create missing database tables'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force creation even if tables exist',
        )

    def handle(self, *args, **options):
        self.stdout.write('Creating missing database tables...')
        
        try:
            # First, try to run migrations to ensure all tables are created
            self.stdout.write('Running Django migrations...')
            call_command('migrate', verbosity=0)
            self.stdout.write(self.style.SUCCESS('✅ Migrations completed successfully'))
            
            # Check if main_inspection table exists
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM information_schema.tables 
                    WHERE table_schema = DATABASE() 
                    AND table_name = 'main_inspection'
                """)
                table_exists = cursor.fetchone()[0] > 0
                
                if table_exists:
                    self.stdout.write(self.style.SUCCESS('✅ main_inspection table already exists'))
                else:
                    self.stdout.write(self.style.WARNING('⚠️ main_inspection table does not exist'))
                    
                    # Create the table manually
                    self.stdout.write('Creating main_inspection table...')
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
                    self.stdout.write(self.style.SUCCESS('✅ main_inspection table created successfully'))
                    
                    # Add foreign key constraint if main_user table exists
                    cursor.execute("""
                        SELECT COUNT(*) 
                        FROM information_schema.tables 
                        WHERE table_schema = DATABASE() 
                        AND table_name = 'main_user'
                    """)
                    user_table_exists = cursor.fetchone()[0] > 0
                    
                    if user_table_exists:
                        try:
                            cursor.execute("""
                                ALTER TABLE main_inspection 
                                ADD CONSTRAINT main_inspection_inspector_id_7c8b8f1f_fk_main_user_id 
                                FOREIGN KEY (inspector_id) REFERENCES main_user (id)
                            """)
                            self.stdout.write(self.style.SUCCESS('✅ Foreign key constraint added'))
                        except Exception as e:
                            self.stdout.write(self.style.WARNING(f'⚠️ Could not add foreign key constraint: {e}'))
                    
                    # Insert default inspection data
                    cursor.execute("""
                        INSERT IGNORE INTO main_inspection 
                        (id, title, description, tipo_combustible, status, product_name, product_code, batch_number, location, inspection_date, created_at, updated_at, inspector_id)
                        VALUES 
                        (1, 'Inspección de Combustible ArByte', 'Inspección de calidad de combustible utilizando el sistema ArByte-3000', 'uranio', 'completed', 'Combustible Industrial', 'COMB-001', 'LOTE-2024-001', 'Planta de Inspección ArByte', NOW(), NOW(), NOW(), 1)
                    """)
                    self.stdout.write(self.style.SUCCESS('✅ Default inspection data inserted'))
            
            # List all main_ tables to verify
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = DATABASE() 
                    AND table_name LIKE 'main_%'
                    ORDER BY table_name
                """)
                tables = cursor.fetchall()
                
                self.stdout.write('\n📋 Main application tables:')
                for table in tables:
                    self.stdout.write(f'  - {table[0]}')
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error: {e}'))
            raise
