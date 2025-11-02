import os

# Delete the problematic migration file
migration_file = "main/migrations/0006_inspection_inspection_id.py"
if os.path.exists(migration_file):
    os.remove(migration_file)
    print(f"Deleted {migration_file}")
else:
    print(f"File {migration_file} not found")

print("Migration file deleted successfully!")
