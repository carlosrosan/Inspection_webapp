import json
import pandas as pd
import os
import argparse
import pymysql
from sqlalchemy import create_engine, text
import warnings
warnings.filterwarnings('ignore')

def load_db_config():
    """Load database configuration from JSON file"""
    try:
        with open("C:/Inspection_webapp/Conuar/conuar_webapp/etl/db_config.json", "r") as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        print("❌ db_config.json not found. Using default MySQL values.")
        return {
            "ENGINE": "mysql",
            "NAME": "conuar_webapp",
            "USER": "root",
            "PASSWORD": "",
            "HOST": "localhost",
            "PORT": "3306"
        }

def create_mysql_connection(config):
    """Create MySQL connection"""
    try:
        connection = pymysql.connect(
            host=config.get("HOST", "localhost"),
            user=config.get("USER", "root"),
            password=config.get("PASSWORD", ""),
            database=config.get("NAME", "conuar_webapp"),
            port=int(config.get("PORT", 3306)),
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        return connection
    except Exception as e:
        print(f"❌ Error connecting to MySQL: {e}")
        return None

def get_table_schema(cursor, table_name):
    """Get column information for a specific table"""
    try:
        cursor.execute(f"DESCRIBE {table_name}")
        columns = cursor.fetchall()
        return columns
    except Exception as e:
        print(f"❌ Error getting schema for table {table_name}: {e}")
        return []

def query_specific_table(cursor, table_name, limit=1000):
    """Query a specific table and return results"""
    try:
        # First get the table schema to understand the structure
        schema = get_table_schema(cursor, table_name)
        if not schema:
            return None, None
        
        # Get column names from schema
        column_names = [col['Field'] for col in schema]
        
        # Query the table with a limit to avoid memory issues
        cursor.execute(f"SELECT * FROM {table_name} LIMIT {limit}")
        rows = cursor.fetchall()
        
        # Convert dict rows to list format for pandas
        list_rows = []
        for row in rows:
            list_rows.append([row[col] for col in column_names])
        
        return list_rows, column_names
    except Exception as e:
        print(f"❌ Error querying table {table_name}: {e}")
        return None, None

def save_table_data_to_csv(data, columns, table_name, output_dir):
    """Save table data to CSV file"""
    try:
        if data and columns:
            df = pd.DataFrame(data, columns=columns)
            filename = f"{table_name}_data.csv"
            filepath = os.path.join(output_dir, filename)
            df.to_csv(filepath, index=False)
            print(f"✅ Table data saved to {filename}")
            return filepath
        else:
            print(f"❌ No data to save for table {table_name}")
            return None
    except Exception as e:
        print(f"❌ Error saving table data: {e}")
        return None

def get_mysql_tables(cursor):
    """Get list of tables from MySQL database"""
    try:
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        # Extract table names from the result
        table_names = [list(table.values())[0] for table in tables]
        return table_names
    except Exception as e:
        print(f"❌ Error getting tables: {e}")
        return []

def main():
    """Main function to execute database checks and queries"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='MySQL Database inspection and query tool')
    parser.add_argument('--table', type=str, help='Specific table to query')
    parser.add_argument('--limit', type=int, default=1000, help='Limit number of rows to query (default: 1000)')
    parser.add_argument('--output-dir', type=str, default='C:/Inspection_webapp/Conuar/conuar_webapp/etl', 
                       help='Output directory for CSV files')
    
    args = parser.parse_args()
    
    # Load DB config
    config = load_db_config()
    
    print(f" Database Engine: {config.get('ENGINE', 'mysql')}")
    print(f"📊 Database Name: {config.get('NAME', 'conuar_webapp')}")
    print(f"🌐 Host: {config.get('HOST', 'localhost')}:{config.get('PORT', '3306')}")
    print(f"👤 User: {config.get('USER', 'root')}")
    
    # Create MySQL connection
    connection = create_mysql_connection(config)
    if not connection:
        print("❌ Failed to connect to MySQL database")
        return
    
    cursor = connection.cursor()
    
    try:
        # Get all tables
        tables = get_mysql_tables(cursor)
        
        if not tables:
            print("❌ No tables found in database")
            return
        
        # Create enhanced tables dataframe with column information
        enhanced_tables_data = []
        
        for table_name in tables:
            columns_info = get_table_schema(cursor, table_name)
            
            if columns_info:
                for col_info in columns_info:
                    enhanced_tables_data.append({
                        'table_name': table_name,
                        'column_name': col_info['Field'],
                        'column_type': col_info['Type'],
                        'null_allowed': col_info['Null'],
                        'key_type': col_info['Key'],
                        'default_value': col_info['Default'],
                        'extra': col_info['Extra']
                    })
        
        # Create dataframes
        enhanced_tables_df = pd.DataFrame(enhanced_tables_data)
        
        # Save enhanced results to CSV
        enhanced_tables_df.to_csv(os.path.join(args.output_dir, "tables_with_columns.csv"), index=False)
        
        print("✅ Enhanced tables schema saved to tables_with_columns.csv")
        
        # If a specific table is requested, query it
        if args.table:
            print(f"\n🔍 Querying specific table: {args.table}")
            
            # Check if table exists
            if args.table not in tables:
                print(f"❌ Table '{args.table}' not found in database")
                print("Available tables:")
                for table in tables:
                    print(f"  - {table}")
                return
            
            # Query the specific table
            data, columns = query_specific_table(cursor, args.table, args.limit)
            
            if data is not None:
                # Save table data to CSV
                output_file = save_table_data_to_csv(data, columns, args.table, args.output_dir)
                if output_file:
                    print(f"✅ Table '{args.table}' data saved with {len(data)} rows")
                    
                    # Show sample data
                    df = pd.DataFrame(data, columns=columns)
                    print(f"\n Sample data from {args.table}:")
                    print(df.head())
                    print(f"\n📊 Table shape: {df.shape}")
            else:
                print(f"❌ Failed to query table '{args.table}'")
        
        # Print summary of all tables
        print(f"\n📊 Database Summary:")
        print(f"Total tables: {len(tables)}")
        print(f"Total columns across all tables: {len(enhanced_tables_data)}")
        
        # Show table names
        print("\n📋 Available tables:")
        for table_name in tables:
            col_count = len([row for row in enhanced_tables_data if row['table_name'] == table_name])
            print(f"  - {table_name} ({col_count} columns)")
    
    except Exception as e:
        print(f"❌ Error during database operations: {e}")
    
    finally:
        # Close connection
        cursor.close()
        connection.close()
        print("\n🔒 Database connection closed")

if __name__ == "__main__":
    main()
