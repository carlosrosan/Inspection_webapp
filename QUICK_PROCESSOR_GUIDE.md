# Quick Guide - PLC Data Processor

## ✅ What Was Done

Modified `plc_data_processor.py` to automatically create inspections based on photos.

## How It Works

1. **Reads** JSON data from `plc_data_raw` table
2. **Extracts** `InSight_3800-AcquisitionID` (e.g., "1", "2", "3")
3. **Finds** matching photo in OK or NOK folder
4. **Creates** inspection with status based on photo location:
   - **OK folder** → Status: `approved` (Pasa ✅)
   - **NOK folder** → Status: `rejected` (No pasa ❌)
5. **Links** photo to inspection
6. **Updates** machine statistics

## Quick Start

```bash
cd C:\Users\Admin\Documents\Inspection_webapp\Conuar\conuar_webapp\etl
python plc_data_processor.py
```

Select option:
- **1** = Process once and exit
- **2** = Process continuously every 30 seconds

## Test Results ✅

Last run (Nov 3, 2025):
- ✅ Processed: 36 records
- ✅ Created: 28 inspections
- ✅ Time: < 1 second

## Examples

### Acquisition ID "1" → Photo NOK/1.bmp
```
→ Creates Inspection #1
→ Status: rejected (No pasa)
→ Defect: True
→ Photo linked: inspection_photos/NOK/1.bmp
```

### Acquisition ID "2" → Photo OK/2.bmp
```
→ Creates Inspection #2
→ Status: approved (Pasa)
→ Defect: False
→ Photo linked: inspection_photos/OK/2.bmp
```

## Photo Locations

```
OK photos:  C:\...\media\inspection_photos\OK\
NOK photos: C:\...\media\inspection_photos\NOK\
```

## View Results

### Check in Database
```bash
python manage.py dbshell
```
```sql
SELECT id, status, defecto_encontrado, product_code 
FROM main_inspection 
ORDER BY id DESC 
LIMIT 10;
```

### Check in Django Admin
```
http://localhost:8000/admin/main/inspection/
```

## Full Documentation

📖 See `PLC_PROCESSOR_README.md` for complete details.

## That's It! 🎉

The processor is ready to use. Run it to create inspections from your PLC data!

