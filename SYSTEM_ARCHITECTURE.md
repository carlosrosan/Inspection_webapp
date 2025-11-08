# Conuar Inspection Platform – Solution Architecture

## 1. High-Level View

```
┌────────────┐        ┌───────────────────────────┐        ┌──────────────────────┐
│  PLC +     │  CSV   │  ETL – Data Reader        │  ORM   │  Database (MySQL /    │
│  NodeRED   ├───────►│  (plc_data_reader.py)     ├───────►│  MariaDB)             │
└────────────┘        └──────────────┬────────────┘        └─────────┬────────────┘
                                      │                               │
                                      │ cycles + photos               │
                                      ▼                               │
                             ┌───────────────────────────┐            │
                             │  ETL – Cycle Processor    │            │
                             │  (plc_data_processor.py)  │            │
                             └──────────────┬────────────┘            │
                                            │ inspections + photos     │
                                            ▼                          │
                             ┌───────────────────────────┐            │
                             │  Django Web Application   │◄────────────┘
                             │  (users, dashboards, API) │
                             └──────────────┬────────────┘
                                            │
                                            ▼
                             ┌───────────────────────────┐
                             │  Media Storage            │
                             │  STAGING / PROCESSED      │
                             └───────────────────────────┘
```

Key pillars:
- **ETL ingestion** turns PLC output into structured inspections.
- **Django app** serves operators (dashboards, photo galleries, auth, machine KPIs).
- **Media pipeline** controls staged vs. processed photos.
- **Database** keeps raw readings, inspections, photos, machine metrics, security artefacts.

## 2. ETL Architecture

### 2.1 PLC Data Reader (`etl/plc_data_reader.py`)
- Watches `etl/Conuar test NodeRed/plc_reads/plc_reads_nodered.csv` (JSON-per-line).
- Uses MD5 hashes to skip previously ingested lines.
- Persists rows in `plc_data_raw` via direct SQL (ordered by timestamp).
- Runs on demand or via Django’s startup hook (`apps.py` ready method).

### 2.2 Cycle-Based Photo Processor (`etl/plc_data_processor.py`)
1. Fetches unprocessed rows from `plc_data_raw`.
2. Groups them into **cycles**:
   - Cycle starts at first row with `bit_inicio_ciclo == "1"`.
   - Cycle ends at the next row where `bit_inicio_ciclo == "0"`.
3. Creates or reuses a single `Inspection` per cycle (natural key: `nombre_ciclo + elemento_combustible + first datetime`).
4. Resolves staged photos in `media/inspection_photos/STAGING/` using filename schema  
   `nombre_ciclo_id_puntero_defecto_elemento_combustible_datetime.ext`.
5. Moves matched photos into `media/inspection_photos/PROCESSED/` and records them in `InspectionPhoto`.
6. Updates `InspectionMachine` statistics (totals, success rate, defect count).
7. Marks raw rows as processed even when no photos exist (inspection is rolled back in that case).
8. Optionally runs every 30 s via `monitor_and_process()` (background thread or CLI option).

### 2.3 Error Handling & Logging
- All ETL scripts log to `logs/` (`plc_data_reader.log`, `plc_data_processor.log`).
- Missing photos, duplicate cycles, and DB issues are reported with contextual warnings.
- Processed photo filenames are memoised to avoid reprocessing.

## 3. Django Application Layer

### 3.1 Modules
- `main/models.py` – users, inspections, photos, machine, raw PLC data.
- `main/views.py` / `templates/main/` – dashboards, inspection detail, PDF, login flows.
- `main/management/commands/` – sample data, cleanup, password expiry tasks.
- `main/apps.py` – orchestrates ETL startup threads (only in the main process, not reloader).

### 3.2 Security & Identity
- Custom password validator (≥10 chars, upper, lower, digit, `. ! # % $`).
- Password expiry middleware (90‑day cadence) forcing reset via token if expired.
- Superuser-only generation of password reset URLs (single-use tokens).
- Login attempt throttling: tracked per user/IP in cache, 5 failures/hour threshold.
- Role differentiation through Django’s native permissions (inspectors, supervisors, admins).

### 3.3 Observability
- `logs/django.log` – framework events.
- `logs/user_login.log` – successful logins, failures, blocks, IP/user-agent metadata.
- KPIs displayed in UI: inspection counts, machine uptime, defect totals.

## 4. Media & File Management

| Directory | Purpose |
| --------- | ------- |
| `media/inspection_photos/STAGING/` | Drop new camera images with required filename pattern. |
| `media/inspection_photos/PROCESSED/` | Photos that have been linked to inspections. |

Operational rules:
- Only photos whose metadata matches an active cycle are moved to `PROCESSED/`.
- Unmatched files remain in staging, with warnings in `plc_data_processor.log`.
- `InspectionPhoto.photo` stores the relative path (e.g. `inspection_photos/PROCESSED/<file>`).

## 5. Database Schema Highlights

| Table | Role |
| ----- | ---- |
| `plc_data_raw` | Raw PLC JSON lines, processed flag, created_at. |
| `main_inspection` | Single inspection per cycle; stores status, defect flag, product info, timestamps. |
| `main_inspectionphoto` | Linked photos with captions, defect flag per image. |
| `main_inspectionmachine` | Aggregated machine metrics (totals, success rate, last inspection). |
| `auth_user` (custom) | Extended with password reset toggles, expiry dates, tokens. |

Additional indexes/constraints recommended:
- MD5 hash on `plc_data_raw.json_data`.
- Unique constraint on inspection natural key if race conditions appear.
- Regular maintenance jobs (mysqldump backups, log rotation scripts).

## 6. Deployment Topology

- **Application server**: Django + Gunicorn (Linux) or Waitress (Windows).  
- **Web server**: Nginx reverse proxy (TLS termination, static/media serving).  
- **Database**: MySQL/MariaDB with tuned `my.cnf` (UTF-8, buffer pool, slow log).  
- **Services**: systemd units (e.g., `inspection-webapp`, `plc-reader`, `plc-processor`).  
- **Backups**: Cron-based scripts exporting DB and media archives (retention 7 days).  
- **Monitoring**: Shell scripts reviewing service health, disk usage, slow queries.

## 7. Operations Checklist

Daily:
- Check ETL and Django logs for warnings.
- Verify STAGING folder is draining (no orphaned photos).

Weekly:
- Confirm database backup jobs succeed.
- Review machine KPI trends for anomalies.

Monthly:
- Archive or purge old processed photos and log files.
- Audit user accounts, password status, and permission levels.

## 8. Extensibility Roadmap
- Additional data validation before accepting PLC rows (schema enforcement).  
- Optional duplicate suppression in `plc_data_raw` using timestamp + hash constraints.  
- Migration toward message queue ingestion if PLC cadence increases.

---

**Status:** Architecture reflects the current cycle-based inspection pipeline (November 2025). Update this document whenever ETL naming, folder conventions, or security policies change.***