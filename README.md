# Conuar Inspection System  

## English

### Overview
- Django-based platform that centralises inspection records, photo evidence, and PLC telemetry for Conuar’s fuel-element quality workflow.  
- Real-time ingestion is driven by two ETL services: a CSV loader that captures PLC snapshots and a cycle-based photo processor that assembles inspections from staged images.

### Core Components
- **Web Application (`main/`)** – authentication, inspection dashboards, password governance, photo galleries, and machine statistics.  
- **ETL Layer (`etl/`)**  
  - `plc_data_reader.py` ingests JSON rows from `plc_reads_nodered.csv` into `plc_data_raw`, de-duplicated by MD5 hash.  
  - `plc_data_processor.py` groups unprocessed rows into PLC cycles, builds or reuses a single inspection per cycle, links staged photos, and updates machine KPIs.  
- **Media Workflow (`media/inspection_photos/`)**  
  - Place new captures inside `STAGING/` using the convention  
    `nombre_ciclo_id_puntero_defecto_elemento_combustible_datetime.ext`.  
  - When a cycle is completed for the same identifiers, photos are moved automatically to `PROCESSED/` and referenced by `InspectionPhoto`.

### Data Flow
```
NodeRED CSV  ─→  plc_data_reader.py  ─→  plc_data_raw (JSON history)
plc_data_raw ─→  cycle grouping       ─→  Inspection + InspectionPhoto + InspectionMachine
STAGING photos ─→ name match          ─→  Linked to inspection, moved to PROCESSED
```

### Key Paths
| Purpose | Location |
| ------- | -------- |
| Django project root | `Conuar/conuar_webapp/` |
| PLC CSV source | `etl/Conuar test NodeRed/plc_reads/plc_reads_nodered.csv` |
| ETL scripts | `etl/` |
| Logs | `logs/` (`plc_data_reader.log`, `plc_data_processor.log`, `django.log`, `user_login.log`) |
| Media staging | `media/inspection_photos/STAGING/` |
| Processed photos | `media/inspection_photos/PROCESSED/` |

### Development Quick Start (Windows)
1. `cd Conuar\conuar_webapp`  
2. Activate the virtual environment (for example `..\conuar_env\Scripts\activate`).  
3. `pip install -r requirements.txt`  
4. `python manage.py migrate`  
5. (Optional) `python manage.py createsuperuser`  
6. `python manage.py runserver`

### Operating the Pipelines
- **Load new PLC rows once**  
  ```powershell
  python etl/plc_data_reader.py
  ```  
- **Process pending cycles once**  
  ```powershell
  python etl/plc_data_processor.py   # choose option 1 at prompt
  ```  
- **Continuous monitoring** – choose option 2 or invoke `start_background_monitor()` so cycles are checked every 30 s after Django startup.  
- **Photo requirements** – a cycle is started when `bit_inicio_ciclo == "1"`; all subsequent rows belong to that inspection until the first row with `bit_inicio_ciclo == "0"`. Every staged photo whose filename matches the cycle metadata (`nombre_ciclo`, `id_puntero`, `defecto`, `elemento_combustible`, timestamp) is attached; unmatched files remain in `STAGING/` and are logged.

### Logging & Monitoring
- Tail ETL logs – `type logs\plc_data_processor.log`, `type logs\plc_data_reader.log`.  
- Authentication events – `logs/user_login.log` stores successes, failures, IPs, and blocks (rate limited after 5 failures/hour).  
- Django runtime – `logs/django.log`.  
- Inspect processed photo history via Django shell:  
  ```python
  from main.models import InspectionPhoto
  print(InspectionPhoto.objects.count())
  ```

### Deployment Highlights
- Designed for MySQL/MariaDB; production guidance covers Gunicorn + Nginx, systemd services, backup scripts, and SSL via Certbot.  
- `apps.py` kicks off both monitors at startup while avoiding duplicate threads during the Django autoreloader cycle.

### Security Features
- Custom password policy (≥10 chars, mixed case, digit, `. ! # % $`).  
- Password reset tokens managed by superusers; single-use links and 90‑day expiry enforcement with middleware redirects.  
- Login throttling via cache-backed attempt counting.  
- Role separation: inspectors, supervisors, and admins.

### Maintenance Checklist
- Review `logs/*.log` daily for ingestion or authentication errors.  
- Keep `media/inspection_photos/STAGING/` tidy—anything left indicates missing PLC metadata.  
- Run `python etl/plc_data_processor.py` manually after large CSV imports.  
- Ensure database backups and log rotation scripts remain active on production hosts.  
- Periodically archive `PROCESSED/` images if disk usage grows; database rows retain the relative path.

---

## Español

### Descripción General
- Plataforma en Django que centraliza registros de inspección, evidencia fotográfica y telemetría PLC del proceso de combustibles Conuar.  
- Dos servicios ETL sostienen el flujo en tiempo real: un cargador CSV que guarda instantáneas del PLC y un procesador de fotos basado en ciclos que arma inspecciones a partir de imágenes en staging.

### Componentes Principales
- **Aplicación web (`main/`)** – autenticación, paneles de inspección, control de contraseñas, galerías y métricas de máquina.  
- **Capa ETL (`etl/`)**  
  - `plc_data_reader.py` ingresa filas JSON de `plc_reads_nodered.csv` en `plc_data_raw` evitando duplicados con hash MD5.  
  - `plc_data_processor.py` agrupa lecturas sin procesar en ciclos, crea o reutiliza una única inspección por ciclo, vincula las fotos en staging y actualiza estadísticas de la máquina.  
- **Flujo de imágenes (`media/inspection_photos/`)**  
  - Coloque nuevas capturas en `STAGING/` usando el patrón  
    `nombre_ciclo_id_puntero_defecto_elemento_combustible_datetime.ext`.  
  - Al cerrarse el ciclo con los mismos identificadores, las fotos se mueven automáticamente a `PROCESSED/` y quedan registradas en `InspectionPhoto`.

### Flujo de Datos
```
CSV de NodeRED ─→ plc_data_reader.py ─→ plc_data_raw (historial JSON)
plc_data_raw ─→ agrupación por ciclo ─→ Inspection + InspectionPhoto + InspectionMachine
Fotos en STAGING ─→ coincidencia por nombre ─→ Se vinculan y pasan a PROCESSED
```

### Rutas Clave
| Propósito | Ubicación |
| --------- | --------- |
| Raíz del proyecto Django | `Conuar/conuar_webapp/` |
| CSV de PLC | `etl/Conuar test NodeRed/plc_reads/plc_reads_nodered.csv` |
| Scripts ETL | `etl/` |
| Registros | `logs/` (`plc_data_reader.log`, `plc_data_processor.log`, `django.log`, `user_login.log`) |
| Staging de fotos | `media/inspection_photos/STAGING/` |
| Fotos procesadas | `media/inspection_photos/PROCESSED/` |

### Puesta en Marcha (Windows)
1. `cd Conuar\conuar_webapp`  
2. Activar el entorno virtual (ej. `..\conuar_env\Scripts\activate`).  
3. `pip install -r requirements.txt`  
4. `python manage.py migrate`  
5. (Opcional) `python manage.py createsuperuser`  
6. `python manage.py runserver`

### Operación de los Pipelines
- **Cargar nuevas filas del PLC una vez**  
  ```powershell
  python etl/plc_data_reader.py
  ```  
- **Procesar ciclos pendientes una vez**  
  ```powershell
  python etl/plc_data_processor.py   # elegir opción 1 al iniciar
  ```  
- **Monitoreo continuo** – elegir opción 2 o llamar a `start_background_monitor()` para revisar cada 30 s tras iniciar Django.  
- **Requisitos de fotos** – un ciclo comienza cuando `bit_inicio_ciclo == "1"`; todas las filas siguientes pertenecen a esa inspección hasta encontrar la primera con `bit_inicio_ciclo == "0"`. Cada foto en staging cuyo nombre coincide con los campos del ciclo (`nombre_ciclo`, `id_puntero`, `defecto`, `elemento_combustible`, fecha-hora) se adjunta; las restantes permanecen en `STAGING/` y se registran en el log.

### Registros y Monitoreo
- Observar los logs ETL – `type logs\plc_data_processor.log`, `type logs\plc_data_reader.log`.  
- Eventos de autenticación – `logs/user_login.log` guarda éxitos, fallos, IPs y bloqueos (límite de 5 fallos por hora).  
- Runtime de Django – `logs/django.log`.  
- Consultar fotos procesadas desde el shell:  
  ```python
  from main.models import InspectionPhoto
  print(InspectionPhoto.objects.count())
  ```

### Despliegue
- Optimizado para MySQL/MariaDB; la documentación incluye pautas con Gunicorn + Nginx, servicios systemd, copias de seguridad y certificados SSL mediante Certbot.  
- `apps.py` arranca ambos monitores durante el `ready()` evitando hilos duplicados por el auto-reloader.

### Seguridad
- Política de contraseñas personalizada (≥10 caracteres con mayúscula, minúscula, número y `.!#%$`).  
- Tokens de restablecimiento administrados por superusuarios; enlaces de un solo uso y vencimiento obligatorio a los 90 días con middleware dedicado.  
- Limitación de intentos en el login usando cache.  
- Separación de roles: inspectores, supervisores y administradores.

### Mantenimiento
- Revisar `logs/*.log` diariamente para detectar errores de ingesta o autenticación.  
- Mantener limpio `media/inspection_photos/STAGING/`; cada archivo retenido indica que falta información PLC asociada.  
- Ejecutar `python etl/plc_data_processor.py` manualmente tras grandes importaciones de CSV.  
- Verificar que los respaldos de base de datos y la rotación de logs sigan activos en entornos productivos.  
- Archivar periódicamente las fotos de `PROCESSED/` si el espacio empieza a crecer; las rutas relativas se conservan en la base.



