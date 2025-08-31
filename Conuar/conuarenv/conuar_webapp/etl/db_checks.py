import json
import sqlite3
import pandas as pd
import os

# Load DB config
with open("db_config.json", "r") as f:
    config = json.load(f)

db_name = config.get("NAME", "db.sqlite3")
db_path = config.get("PATH", "db.sqlite3")

print(db_path)

# Ensure DB exists
if not os.path.exists(os.path.join(db_path, db_name)):
    raise FileNotFoundError(f"Database file '{db_name}' not found!")

# Connect to SQLite
conn = sqlite3.connect(db_name)
cursor = conn.cursor()

# Query 1: List all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()

# Query 2: List all databases attached to the engine
cursor.execute("PRAGMA database_list;")
databases = cursor.fetchall()

# Save results into CSVs
tables_df = pd.DataFrame(tables, columns=["table_name"])
databases_df = pd.DataFrame(databases, columns=["seq", "name", "file"])

tables_df.to_csv("tables_list.csv", index=False)
databases_df.to_csv("databases_list.csv", index=False)

# Print summary
print("✅ Tables saved to tables_list.csv")
print("✅ Databases saved to databases_list.csv")

# Close connection
conn.close()
