#!/usr/bin/env python
"""
Script to migrate from SQLite to MySQL
"""

import os
import sys
import django
from pathlib import Path

# Add the project directory to Python path
project_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(project_dir))

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.management import execute_from_command_line
from django.conf import settings

def migrate_to_mysql():
    """Migrate the database from SQLite to MySQL"""
    print("�� Starting migration from SQLite to MySQL...")
    
    try:
        # Make migrations
        print("📝 Making migrations...")
        execute_from_command_line(['manage.py', 'makemigrations'])
        
        # Migrate
        print("�� Running migrations...")
        execute_from_command_line(['manage.py', 'migrate'])
        
        # Create superuser if needed
        print("�� Creating superuser...")
        execute_from_command_line(['manage.py', 'createsuperuser', '--noinput'])
        
        print("✅ Migration completed successfully!")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    migrate_to_mysql()
