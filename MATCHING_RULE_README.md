# Photo-to-CSV Matching Rule - Conuar System

## ⚠️ Critical Rule Implemented

**ONLY create inspections when photo filename matches an InSight_3800-AcquisitionID from the CSV file.**

## 🎯 The Rule

### Before (Old Behavior - REMOVED)
```
Photo found → Create inspection (even without CSV data)
Result: Inspections created for ALL photos
```

### After (New Behavior - ENFORCED)
```
Photo found → Check if AcquisitionID exists in CSV → Only then create inspection
Result: Inspections created ONLY for photos with matching CSV data
```

## 📋 How It Works

### Step-by-Step Process

1. **Photo Monitor** detects new photo in OK/ or NOK/ folder
   - Example: `101.bmp`

2. **Extract Acquisition ID** from filename (without extension)
   - Photo: `101.bmp` → Acquisition ID: `101`
   - Photo: `5.bmp` → Acquisition ID: `5`

3. **Search CSV/Database** for matching InSight_3800-AcquisitionID
   - Searches in `plc_data_raw` table
   - Looks for JSON records with matching acquisition ID

4. **Decision**:
   - ✅ **Match Found**: Create inspection with photo
   - ❌ **No Match**: Skip photo (log warning, don't create inspection)

## 🔍 Example Scenarios

### Scenario 1: Matching Photo ✅

**CSV Data:**
```json
{"datetime":"2025-11-04T00:47:18.786Z"," InSight_3800-AcquisitionID":"5",...}
```

**Photo:** `5.bmp` in `OK/` folder

**Result:**
```
[MATCH] Encontrados datos PLC para foto 5.bmp (AcquisitionID: 5)
[OK] Inspección creada para foto 5.bmp - Estado: OK
✓ Inspection created with ID 5, status 'approved'
```

### Scenario 2: Non-Matching Photo ❌

**CSV Data:**
```json
{"datetime":"2025-11-04T00:47:18.786Z"," InSight_3800-AcquisitionID":"5",...}
```

**Photo:** `101.bmp` in `OK/` folder

**Result:**
```
[SKIP] OMITIDA foto 101.bmp - No hay datos PLC con AcquisitionID='101' en CSV/base de datos
✗ NO inspection created
✗ Photo marked as processed (won't check again)
```

### Scenario 3: Multiple Photos, Some Match ✅❌

**CSV Data:**
```json
{"datetime":"...","InSight_3800-AcquisitionID":"1",...}
{"datetime":"...","InSight_3800-AcquisitionID":"2",...}
{"datetime":"...","InSight_3800-AcquisitionID":"3",...}
```

**Photos in OK/ folder:**
- `1.bmp` ✅ Match → Inspection created
- `2.bmp` ✅ Match → Inspection created
- `3.bmp` ✅ Match → Inspection created
- `101.bmp` ❌ No match → Skipped
- `999.bmp` ❌ No match → Skipped

**Result:**
```
Fotos nuevas: 5
Inspecciones creadas: 3
Omitidas: 2
```

## 📊 Current CSV Acquisition IDs

**File:** `plc_reads_nodered.csv`

Currently contains these Acquisition IDs:
- 1
- 2
- 3
- 4
- 5

**Photos that will create inspections:**
- ✅ `1.bmp`, `2.bmp`, `3.bmp`, `4.bmp`, `5.bmp`

**Photos that will be skipped:**
- ❌ Any other ID (e.g., `6.bmp`, `10.bmp`, `101.bmp`, `999.bmp`)

## 🔧 Log Output Examples

### When Photo Matches
```
[Ciclo 5] Verificando fotos nuevas...
Encontradas 1 fotos nuevas para procesar
Procesando 1 fotos nuevas...
[MATCH] Encontrados datos PLC para foto 5.bmp (AcquisitionID: 5)
Inspección creada - ID: 5, Estado: approved, Foto: 5.bmp
Foto vinculada a inspección 5: inspection_photos/OK/5.bmp
[OK] Inspección creada para foto 5.bmp - Estado: OK
[SUCCESS] 1 nuevas inspecciones creadas
[Ciclo 5] Fotos nuevas: 1, Inspecciones creadas: 1, Omitidas: 0, Errores: 0
```

### When Photo Doesn't Match
```
[Ciclo 6] Verificando fotos nuevas...
Encontradas 2 fotos nuevas para procesar
Procesando 2 fotos nuevas...
[SKIP] OMITIDA foto 101.bmp - No hay datos PLC con AcquisitionID='101' en CSV/base de datos
[SKIP] OMITIDA foto 999.bmp - No hay datos PLC con AcquisitionID='999' en CSV/base de datos
[INFO] 2 fotos omitidas (sin datos PLC correspondientes)
[Ciclo 6] Fotos nuevas: 2, Inspecciones creadas: 0, Omitidas: 2, Errores: 0
```

### Mixed Results
```
[Ciclo 7] Verificando fotos nuevas...
Encontradas 4 fotos nuevas para procesar
Procesando 4 fotos nuevas...
[MATCH] Encontrados datos PLC para foto 1.bmp (AcquisitionID: 1)
[OK] Inspección creada para foto 1.bmp - Estado: OK
[SKIP] OMITIDA foto 101.bmp - No hay datos PLC con AcquisitionID='101' en CSV/base de datos
[MATCH] Encontrados datos PLC para foto 3.bmp (AcquisitionID: 3)
[OK] Inspección creada para foto 3.bmp - Estado: NOK
[SKIP] OMITIDA foto 55.bmp - No hay datos PLC con AcquisitionID='55' en CSV/base de datos
[SUCCESS] 2 nuevas inspecciones creadas
[INFO] 2 fotos omitidas (sin datos PLC correspondientes)
[Ciclo 7] Fotos nuevas: 4, Inspecciones creadas: 2, Omitidas: 2, Errores: 0
```

## 🧪 Testing the Rule

### Test 1: Add Photo with Matching ID ✅

```bash
# CSV has AcquisitionID "5"
# Add photo with matching name
copy test.bmp media\inspection_photos\OK\5.bmp

# Wait 30 seconds

# Check result
python manage.py dbshell
SELECT * FROM main_inspection WHERE product_code='COMB-5';
# Should return 1 row ✅
```

### Test 2: Add Photo without Matching ID ❌

```bash
# CSV does NOT have AcquisitionID "999"
# Add photo with non-matching name
copy test.bmp media\inspection_photos\OK\999.bmp

# Wait 30 seconds

# Check result
python manage.py dbshell
SELECT * FROM main_inspection WHERE product_code='COMB-999';
# Should return 0 rows ❌
```

### Test 3: Add CSV Data First, Then Photo ✅

```bash
# Step 1: Add CSV line with AcquisitionID "100"
echo {"datetime":"2025-11-04T10:00:00.000Z"," InSight_3800-AcquisitionID":"100",...} >> plc_reads_nodered.csv

# Wait 30 seconds (CSV monitor loads it)

# Step 2: Add matching photo
copy test.bmp media\inspection_photos\OK\100.bmp

# Wait 30 seconds (Photo monitor processes it)

# Check result
python manage.py dbshell
SELECT * FROM main_inspection WHERE product_code='COMB-100';
# Should return 1 row ✅
```

## 📝 Important Notes

### 1. Skipped Photos Are Marked as Processed
Once a photo is skipped (no matching CSV data), it's marked as "processed" and won't be checked again. This prevents spam in logs.

**Implication:** If you later add CSV data for a skipped photo, you need to:
- Remove the photo from the folder
- Add it again (so it's detected as "new")

### 2. Case Sensitivity
Matching is case-insensitive and whitespace is trimmed:
- `"5"` matches `"5"`
- `" 5"` matches `"5"`
- `"05"` does NOT match `"5"`

### 3. File Extension Doesn't Matter
Only the filename (without extension) is used:
- `5.bmp` → ID: `5`
- `5.jpg` → ID: `5`
- `5.png` → ID: `5`

All would match CSV AcquisitionID `"5"`

### 4. Folder Location Still Determines Status
The OK/NOK folder location still determines inspection status:
- `OK/5.bmp` → Status: `approved` (Pasa)
- `NOK/5.bmp` → Status: `rejected` (No pasa)

## 🔒 Why This Rule?

### Problem Without Rule
```
Photo 999.bmp added → Inspection created with no PLC context
Result: Orphaned inspections without associated sensor data
```

### Solution With Rule
```
Photo 999.bmp added → No matching CSV → Skip
Result: Only valid inspections with complete data
```

### Benefits
1. ✅ **Data Integrity**: Every inspection has associated PLC data
2. ✅ **Traceability**: Can trace back to exact PLC reading
3. ✅ **No Orphans**: No inspections without context
4. ✅ **Quality Control**: Ensures proper workflow (CSV first, photo second)

## 📊 Monitoring

### Check Skipped Photos
```bash
# View log file
type logs\plc_data_processor.log | findstr "SKIP"

# You'll see:
# [SKIP] OMITIDA foto 101.bmp - No hay datos PLC con AcquisitionID='101'...
```

### Check Processed Photos
```python
# Django shell
from etl.plc_data_processor import PlcDataProcessor
processor = PlcDataProcessor()
print(f"Processed photos: {len(processor.processed_photos)}")
print(processor.processed_photos)
```

### Check Available Acquisition IDs
```python
# Django shell
from main.models import PlcDataRaw
import json

# Get all unique acquisition IDs from database
ids = set()
for raw in PlcDataRaw.objects.all():
    try:
        data = json.loads(raw.json_data)
        acq_id = data.get(' InSight_3800-AcquisitionID') or data.get('InSight_3800-AcquisitionID')
        if acq_id:
            ids.add(str(acq_id).strip())
    except:
        pass

print(f"Available Acquisition IDs: {sorted(ids)}")
```

## 🚀 Summary

**The Rule:** Only create inspections when photo filename matches a CSV AcquisitionID.

**Result:**
- ✅ Photos with matching CSV data → Inspections created
- ❌ Photos without matching CSV data → Skipped (logged as warning)

**To create an inspection:**
1. Add CSV line with InSight_3800-AcquisitionID (e.g., "100")
2. Wait 30 seconds (CSV loads)
3. Add photo with matching name (e.g., `100.bmp`)
4. Wait 30 seconds (inspection created)

**This ensures data integrity and proper workflow!** 🎯


