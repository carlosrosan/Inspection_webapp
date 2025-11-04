# Automatic PLC Data Loading on Django Startup

## Overview
The Django application has been configured to automatically load PLC data from the CSV file into the MySQL `plc_data_raw` table every time Django starts via `manage.py`.

## What Was Changed

### 1. Modified `plc_data_reader.py`
**File:** `Conuar/conuar_webapp/etl/plc_data_reader.py`

**Changes:**
- Added a new function `load_csv_data_to_db()` that can be called from Django's startup process
- Made Django setup conditional to avoid conflicts when imported by an already-running Django app
- The function reads the CSV file from: `C:\Users\Admin\Documents\Inspection_webapp\Conuar\conuar_webapp\etl\Conuar test NodeRed\plc_reads\plc_reads_nodered.csv`
- Inserts all JSON rows into the `plc_data_raw` MySQL table

**New Function:**
```python
def load_csv_data_to_db(csv_file_path: str = None) -> dict:
    """
    Load CSV data into database - can be called from Django startup
    Returns a dictionary with results
    """
```

### 2. Modified `apps.py`
**File:** `Conuar/conuar_webapp/main/apps.py`

**Changes:**
- Added a `ready()` method to the `MainConfig` class
- This method is automatically called by Django when the application starts
- It imports and executes the `load_csv_data_to_db()` function
- Includes protection against running in Django's auto-reloader process
- Has comprehensive error handling to prevent Django startup failures

**Key Features:**
- Only runs in the main process (not in reloader)
- Logs all operations for debugging
- Won't prevent Django from starting even if data loading fails
- Provides clear success/failure messages

## How It Works

1. When you run `python manage.py runserver` (or any Django command)
2. Django loads all installed apps
3. The `MainConfig.ready()` method is called
4. The CSV data is automatically loaded into the database
5. You see log messages indicating success or failure
6. Django continues normal startup

## Log Output
When Django starts, you'll see output like this:

```
============================================================
Django Startup: Loading PLC data from CSV...
============================================================
INFO - Archivo CSV encontrado: C:\Users\Admin\Documents\Inspection_webapp\...\plc_reads_nodered.csv
INFO - Iniciando procesamiento de archivo CSV: ...
INFO - Datos guardados - Timestamp: 2025-11-04 00:47:18.786000, Tamaño: XXX bytes
INFO - Progreso: 10 registros guardados...
INFO - Resumen de procesamiento:
INFO - Total de líneas procesadas: 17
INFO - Guardados exitosamente: 17
INFO - Errores: 0
INFO - Tiempo transcurrido: X.X segundos
INFO - ✓ PLC data loaded successfully on Django startup
============================================================
```

## CSV File Format
The CSV file should contain one JSON object per line:
```json
{"datetime":"2025-11-04T00:47:18.786Z","tank_level":"false","InSight_3800-TriggerEnable":"false",...}
```

Each line is stored as-is in the `plc_data_raw.json_data` field.

## Database Table
**Table:** `plc_data_raw`

**Fields:**
- `id` (auto-increment primary key)
- `timestamp` (datetime from JSON)
- `json_data` (TEXT - raw JSON string)
- `processed` (boolean - default False)
- `created_at` (datetime - when inserted)

## Testing

### Test 1: Normal Django Startup
```bash
cd C:\Users\Admin\Documents\Inspection_webapp\Conuar\conuar_webapp
python manage.py runserver
```

You should see the data loading messages in the console.

### Test 2: Verify Data in Database
```python
python manage.py shell

>>> from main.models import PlcDataRaw
>>> PlcDataRaw.objects.count()
17  # or however many rows are in your CSV

>>> PlcDataRaw.objects.first().json_data
'{"datetime":"2025-11-04T00:47:18.786Z",...}'
```

### Test 3: Standalone Script (Still Works)
```bash
cd C:\Users\Admin\Documents\Inspection_webapp\Conuar\conuar_webapp\etl
python plc_data_reader.py
```

The standalone script still works as before!

## Important Notes

1. **Data Duplication:** ⚠️ **IMPORTANT** - The script will insert data every time Django starts. This means:
   - Each Django restart adds 17 new records to the database
   - This is by design for continuous data collection
   - If you want to avoid duplicates, consider adding one of these solutions:
     - Clear the table before each run: `PlcDataRaw.objects.all().delete()`
     - Add duplicate checking logic based on timestamp and JSON hash
     - Only load data if the table is empty: `if PlcDataRaw.objects.count() == 0:`
     - Add a unique constraint on timestamp and a JSON hash field

2. **CSV File Location:** The CSV file path is hardcoded. If you move the file, update the path in `plc_data_reader.py`:
   ```python
   csv_file_path = r"C:\Users\Admin\Documents\Inspection_webapp\Conuar\conuar_webapp\etl\Conuar test NodeRed\plc_reads\plc_reads_nodered.csv"
   ```

3. **Error Handling:** If the CSV file is missing or there's a database error, Django will still start normally. Check the logs for error messages.

4. **Performance:** Loading happens synchronously during startup. For large CSV files, this might slow down Django's startup time.

## Troubleshooting

### Data Not Loading?
1. Check if the CSV file exists at the specified path
2. Check Django logs for error messages
3. Verify database connection settings
4. Check that the `plc_data_raw` table exists

### Import Errors?
1. Ensure the `etl` directory is at the correct location
2. Check that `plc_data_reader.py` has no syntax errors
3. Verify Django settings are correct

### Data Loaded Multiple Times?
This is expected behavior - data loads on every Django restart. Consider adding logic to check if data already exists.

## Future Enhancements

Consider these improvements:
1. Add duplicate detection before inserting
2. Clear old data before loading new data
3. Make the CSV path configurable via Django settings
4. Add a flag to enable/disable auto-loading
5. Support incremental loading (only new records)
6. Add validation for JSON data before insertion

## Files Modified
1. `Conuar/conuar_webapp/etl/plc_data_reader.py`
2. `Conuar/conuar_webapp/main/apps.py`

## Backup
If you need to revert changes, the key modification is in `apps.py` - simply remove or comment out the `ready()` method.

