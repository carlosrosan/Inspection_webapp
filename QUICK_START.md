# Quick Start Guide - Auto PLC Data Loading

## ✅ Implementation Complete!

Your Django project now automatically loads PLC data from CSV into MySQL on every startup.

## How to Use

### Start Django (Data loads automatically)
```bash
cd C:\Users\Admin\Documents\Inspection_webapp\Conuar\conuar_webapp
python manage.py runserver
```

You'll see:
```
============================================================
Django Startup: Loading PLC data from CSV...
============================================================
INFO - Guardados exitosamente: 17
[SUCCESS] PLC data loaded successfully on Django startup
```

### Check Data in Database
```bash
python manage.py dbshell
```
```sql
SELECT COUNT(*) FROM plc_data_raw;
SELECT * FROM plc_data_raw ORDER BY created_at DESC LIMIT 5;
```

## What Files Were Changed

1. **`main/apps.py`** - Added automatic loading on Django startup
2. **`etl/plc_data_reader.py`** - Made compatible with both Django startup and standalone use

## Important Notes

⚠️ **Data loads EVERY TIME Django starts** - This means you'll get 17 new records each time.

To prevent duplicates, add this to `apps.py` line 46 (before `result = load_csv_data_to_db()`):

```python
from main.models import PlcDataRaw
PlcDataRaw.objects.all().delete()  # Clear before loading
```

## CSV File Location

```
C:\Users\Admin\Documents\Inspection_webapp\Conuar\conuar_webapp\etl\Conuar test NodeRed\plc_reads\plc_reads_nodered.csv
```

Contains 17 JSON objects (one per line)

## Database Table: `plc_data_raw`

| Column     | Type     | Description              |
|------------|----------|--------------------------|
| id         | INT      | Primary key              |
| timestamp  | DATETIME | From JSON data           |
| json_data  | TEXT     | Full JSON (3500+ bytes)  |
| processed  | BOOLEAN  | Processing flag          |
| created_at | DATETIME | When inserted            |

## Full Documentation

📖 See detailed documentation:
- `IMPLEMENTATION_SUMMARY.md` - Complete overview
- `STARTUP_DATA_LOADER_README.md` - Technical details

## That's It! 🎉

Your Django project is ready to use. Start it and watch the data load automatically!

