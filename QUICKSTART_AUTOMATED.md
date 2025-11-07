# Quick Start - Automated Conuar System

## ✅ What's New

Your system now runs **100% automatically**! Everything starts when Django starts.

## 🚀 Start Everything

```bash
cd C:\Users\Admin\Documents\Inspection_webapp\Conuar\conuar_webapp
python manage.py runserver
```

**That's it!** The system will:
1. ✅ Load initial CSV data
2. ✅ Start CSV monitor (checks every 30s)
3. ✅ Start photo monitor (checks every 30s)
4. ✅ Create inspections automatically

## 📊 What Happens Automatically

### Every 30 Seconds

**CSV Monitor:**
- Checks: `plc_reads_nodered.csv`
- Action: Inserts new rows into `plc_data_raw` table
- Logs: `"✓ X nuevos registros guardados"`

**Photo Monitor:**
- Checks: `media/inspection_photos/OK/` and `NOK/`
- Action: Creates inspections for new photos
- Logs: `"✓ X nuevas inspecciones creadas"`

## 📁 Folders to Watch

**Add CSV data here:**
```
etl/Conuar test NodeRed/plc_reads/plc_reads_nodered.csv
```

**Add photos here:**
```
media/inspection_photos/OK/     ← Approved inspections
media/inspection_photos/NOK/    ← Rejected inspections
```

## 🧪 Quick Test

### Test 1: Add Photo
```bash
# Copy a photo
copy test.bmp media\inspection_photos\OK\99.bmp

# Wait 30 seconds

# Check result
python manage.py dbshell
SELECT * FROM main_inspection WHERE product_code='COMB-99';
```

### Test 2: Add CSV Data
```bash
# Add line to plc_reads_nodered.csv
echo {"datetime":"2025-11-04T10:00:00.000Z","InSight_3800-AcquisitionID":"100"} >> plc_reads_nodered.csv

# Wait 30 seconds

# Check result
python manage.py dbshell
SELECT * FROM plc_data_raw WHERE json_data LIKE '%100%';
```

## 📋 Monitor Status

**Check if monitors are running:**
```python
# In Django shell
import threading
[t.name for t in threading.enumerate()]
# Should show: PLCDataReaderMonitor, PLCPhotoProcessorMonitor
```

**Check logs:**
```bash
type logs\plc_data_reader.log
type logs\plc_data_processor.log
```

## ⚙️ Configuration

**Change monitoring interval:**

Edit `main/apps.py`:
```python
# Line 68 & 80
csv_thread = start_csv_monitor(interval_seconds=60)    # Change from 30 to 60
photo_thread = start_photo_monitor(interval_seconds=60)  # Change from 30 to 60
```

## 🛑 Stop Everything

Just stop Django:
```bash
Ctrl + C
```

The monitors will stop automatically (daemon threads).

## 📖 Full Documentation

See `AUTOMATED_SYSTEM_README.md` for complete details.

## ✨ That's It!

Your system is now fully automated. Just start Django and let it run!


