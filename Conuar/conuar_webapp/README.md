# Inspection System Reporting Webapp

A Django-based web application for managing product inspections with photo documentation and quality control.

## Features

- **User Authentication**: Secure login system for privileged users
- **Inspection Management**: Complete inspection lifecycle tracking
- **Photo Documentation**: Upload and manage inspection photos
- **Role-Based Access**: Inspector and Supervisor roles
- **Quality Control**: Status tracking and approval workflows
- **Responsive UI**: Modern Bootstrap-based interface

## System Requirements

- Python 3.8+
- Django 4.2.23
- Pillow 10.0.1+ (for image handling)
- MySQL database (production-ready with MariaDB support)

## Technology Stack

### Backend
- **Framework**: Django 4.2.23
- **Language**: Python 3.8+
- **Database**: MySQL 8.0+ / MariaDB 10.6+
- **ORM**: Django ORM
- **Authentication**: Django built-in authentication system

### Frontend
- **Template Engine**: Django Templates
- **CSS Framework**: Bootstrap 5
- **JavaScript**: Vanilla JavaScript
- **Icons**: Font Awesome
- **Responsive Design**: Mobile-first approach

### PLC Integration
- **Protocol**: Modbus TCP
- **Communication**: pyModbusTCP library
- **Data Processing**: Custom ETL scripts
- **Real-time Monitoring**: Continuous data reading

### Production Stack
- **Web Server**: Nginx
- **WSGI Server**: Gunicorn
- **Process Management**: Systemd
- **Database**: MySQL/MariaDB
- **File Storage**: Local filesystem
- **Logging**: Python logging + systemd journal

### Development Tools
- **Version Control**: Git
- **Package Management**: pip
- **Virtual Environment**: venv
- **Database Migration**: Django migrations
- **Static Files**: Django collectstatic

## Installation

### Windows Development Environment

1. **Clone or navigate to the project directory**
   ```bash
   cd conuarenv/conuar_webapp
   ```

2. **Activate virtual environment**
   ```bash
   ..\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run database migrations**
   ```bash
   python manage.py migrate
   ```

5. **Create superuser (optional)**
   ```bash
   python manage.py createsuperuser
   ```

6. **Start development server**
   ```bash
   python manage.py runserver
   ```

---

## Debian Linux Virtual Machine Installation Guide

This guide will help you install and deploy the Inspection System Webapp on a Debian Linux virtual machine.

### Prerequisites

- Debian 11 (Bullseye) or Debian 12 (Bookworm)
- Root or sudo access
- At least 2GB RAM and 10GB disk space
- Network connectivity

### Step 1: Update System and Install Basic Dependencies

```bash
# Update package lists
sudo apt update && sudo apt upgrade -y

# Install essential packages
sudo apt install -y curl wget git vim nano htop tree unzip
```

### Step 2: Install Python 3.8+ and pip

```bash
# Install Python 3 and development tools
sudo apt install -y python3 python3-pip python3-venv python3-dev

# Install additional Python dependencies
sudo apt install -y build-essential libssl-dev libffi-dev libjpeg-dev zlib1g-dev

# Verify Python installation
python3 --version
pip3 --version
```

### Step 3: Install Database (MySQL/MariaDB)

```bash
# Install MariaDB (MySQL-compatible)
sudo apt install -y mariadb-server mariadb-client

# Start and enable MariaDB
sudo systemctl start mariadb
sudo systemctl enable mariadb

# Secure MariaDB installation
sudo mysql_secure_installation
```

**During MariaDB setup, choose:**
- Set root password: Yes
- Remove anonymous users: Yes
- Disallow root login remotely: Yes
- Remove test database: Yes
- Reload privilege tables: Yes

### Step 4: Create Database and User

```bash
# Login to MariaDB as root
sudo mysql -u root -p

# Create database and user (run these SQL commands)
CREATE DATABASE inspection_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'inspection_user'@'localhost' IDENTIFIED BY 'your_secure_password';
GRANT ALL PRIVILEGES ON inspection_system.* TO 'inspection_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

---

## MySQL Installation Guide for Debian Linux

This section provides detailed instructions for installing and configuring MySQL specifically for the Inspection System Webapp on Debian Linux.

### Prerequisites

- Debian 11 (Bullseye) or Debian 12 (Bookworm)
- Root or sudo access
- At least 1GB RAM available for MySQL
- Network connectivity

### Option 1: Install MySQL Server (Official Oracle MySQL)

#### Step 1: Download MySQL APT Repository

```bash
# Update package index
sudo apt update

# Download MySQL APT repository package
cd /tmp
wget https://dev.mysql.com/get/mysql-apt-config_0.8.24-1_all.deb

# Install the repository package
sudo dpkg -i mysql-apt-config_0.8.24-1_all.deb
```

**During installation:**
- Select "MySQL Server & Cluster" and choose the latest version
- Select "MySQL Tools & Connectors" 
- Select "MySQL Preview Packages" if desired
- Select "Ok" to finish

#### Step 2: Update Package List and Install MySQL

```bash
# Update package list to include MySQL repository
sudo apt update

# Install MySQL Server
sudo apt install -y mysql-server

# Install MySQL client and development libraries
sudo apt install -y mysql-client libmysqlclient-dev
```

#### Step 3: Start and Enable MySQL Service

```bash
# Start MySQL service
sudo systemctl start mysql

# Enable MySQL to start on boot
sudo systemctl enable mysql

# Check MySQL status
sudo systemctl status mysql
```

#### Step 4: Secure MySQL Installation

```bash
# Run MySQL security script
sudo mysql_secure_installation
```

**Security Configuration Options:**
```
Would you like to setup VALIDATE PASSWORD component? → Y
Please set the password for root here → Enter strong password
Re-enter new password → Confirm password
Remove anonymous users? → Y
Disallow root login remotely? → Y
Remove test database and access to it? → Y
Reload privilege tables now? → Y
```

#### Step 5: Configure MySQL for the Web App

```bash
# Login to MySQL as root
sudo mysql -u root -p
```

**Run these SQL commands:**
```sql
-- Create database for the inspection system
CREATE DATABASE inspection_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Create dedicated user for the web application
CREATE USER 'inspection_user'@'localhost' IDENTIFIED BY 'your_secure_password_here';

-- Grant all privileges on the database to the user
GRANT ALL PRIVILEGES ON inspection_system.* TO 'inspection_user'@'localhost';

-- Grant additional privileges for Django migrations
GRANT CREATE, DROP, ALTER, INDEX ON inspection_system.* TO 'inspection_user'@'localhost';

-- Flush privileges to apply changes
FLUSH PRIVILEGES;

-- Verify user creation
SELECT User, Host FROM mysql.user WHERE User = 'inspection_user';

-- Show databases to confirm creation
SHOW DATABASES;

-- Exit MySQL
EXIT;
```

#### Step 6: Test Database Connection

```bash
# Test connection with the new user
mysql -u inspection_user -p inspection_system

# If successful, you should see MySQL prompt
# Type 'EXIT;' to quit
```

### Option 2: Install MariaDB (MySQL-Compatible Alternative)

MariaDB is a popular MySQL-compatible database that's often easier to install and configure.

#### Step 1: Install MariaDB

```bash
# Update package list
sudo apt update

# Install MariaDB server and client
sudo apt install -y mariadb-server mariadb-client

# Install development libraries
sudo apt install -y libmariadb-dev libmariadb-dev-compat
```

#### Step 2: Start and Enable MariaDB

```bash
# Start MariaDB service
sudo systemctl start mariadb

# Enable MariaDB to start on boot
sudo systemctl enable mariadb

# Check MariaDB status
sudo systemctl status mariadb
```

#### Step 3: Secure MariaDB Installation

```bash
# Run MariaDB security script
sudo mysql_secure_installation
```

**Security Configuration:**
```
Enter current password for root: → Press Enter (no password set initially)
Set root password? → Y
New password: → Enter strong password
Re-enter new password: → Confirm password
Remove anonymous users? → Y
Disallow root login remotely? → Y
Remove test database and access to it? → Y
Reload privilege tables now? → Y
```

#### Step 4: Create Database and User (Same as MySQL)

```bash
# Login to MariaDB as root
sudo mysql -u root -p
```

**Run the same SQL commands as in MySQL Option 1, Step 5**

### MySQL Configuration for Production

#### Step 1: Configure MySQL for Better Performance

```bash
# Create MySQL configuration file
sudo nano /etc/mysql/mysql.conf.d/inspection_webapp.cnf
```

**Add this configuration:**
```ini
[mysqld]
# Basic settings
default-storage-engine = InnoDB
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci

# Connection settings
max_connections = 200
max_connect_errors = 1000
wait_timeout = 28800
interactive_timeout = 28800

# Buffer settings
innodb_buffer_pool_size = 256M
innodb_log_file_size = 64M
innodb_log_buffer_size = 16M
innodb_flush_log_at_trx_commit = 2

# Query cache
query_cache_type = 1
query_cache_size = 32M
query_cache_limit = 2M

# Temporary tables
tmp_table_size = 32M
max_heap_table_size = 32M

# Logging
slow_query_log = 1
slow_query_log_file = /var/log/mysql/slow.log
long_query_time = 2

# Security
local_infile = 0
```

#### Step 2: Restart MySQL to Apply Configuration

```bash
# Restart MySQL service
sudo systemctl restart mysql

# Check if MySQL started successfully
sudo systemctl status mysql
```

#### Step 3: Create Log Directory and Set Permissions

```bash
# Create log directory
sudo mkdir -p /var/log/mysql

# Set proper permissions
sudo chown mysql:mysql /var/log/mysql
sudo chmod 755 /var/log/mysql
```

### Configure Django Settings for MySQL

#### Step 1: Install MySQL Python Connector

```bash
# Install MySQL connector for Python
pip install mysqlclient

# Alternative: Install PyMySQL if mysqlclient fails
pip install PyMySQL
```

#### Step 2: Update Django Settings

```bash
# Edit Django settings file
nano config/settings.py
```

**Update database configuration:**
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'inspection_system',
        'USER': 'inspection_user',
        'PASSWORD': 'your_secure_password_here',
        'HOST': 'localhost',
        'PORT': '3306',
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            'charset': 'utf8mb4',
        },
    }
}
```

**If using PyMySQL, add this at the top of settings.py:**
```python
import pymysql
pymysql.install_as_MySQLdb()
```

### Database Migration and Setup

#### Step 1: Run Django Migrations

```bash
# Activate virtual environment
source venv/bin/activate

# Run database migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Load initial data (if available)
python manage.py loaddata initial_data.json
```

#### Step 2: Verify Database Setup

```bash
# Connect to MySQL and verify tables
mysql -u inspection_user -p inspection_system

# Show all tables
SHOW TABLES;

# Check table structure
DESCRIBE main_inspection;

# Exit MySQL
EXIT;
```

### MySQL Monitoring and Maintenance

#### Step 1: Set Up MySQL Monitoring

```bash
# Create monitoring script
sudo nano /opt/inspection_webapp/mysql_monitor.sh
```

**Add this content:**
```bash
#!/bin/bash
# MySQL monitoring script for inspection webapp

echo "=== MySQL Status Report ==="
echo "Date: $(date)"
echo ""

# Check MySQL service status
echo "MySQL Service Status:"
systemctl status mysql --no-pager

echo ""
echo "MySQL Process Status:"
ps aux | grep mysql

echo ""
echo "MySQL Connections:"
mysql -u inspection_user -p -e "SHOW PROCESSLIST;" inspection_system

echo ""
echo "Database Size:"
mysql -u inspection_user -p -e "SELECT table_schema AS 'Database', ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS 'Size (MB)' FROM information_schema.tables WHERE table_schema = 'inspection_system' GROUP BY table_schema;" inspection_system

echo ""
echo "Slow Query Log (last 10 entries):"
tail -n 10 /var/log/mysql/slow.log 2>/dev/null || echo "No slow query log found"
```

```bash
# Make script executable
sudo chmod +x /opt/inspection_webapp/mysql_monitor.sh
```

#### Step 2: Set Up Database Backup

```bash
# Create backup script
sudo nano /opt/inspection_webapp/mysql_backup.sh
```

**Add this content:**
```bash
#!/bin/bash
# MySQL backup script for inspection webapp

BACKUP_DIR="/opt/backups/mysql"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="inspection_system"
DB_USER="inspection_user"

# Create backup directory
mkdir -p $BACKUP_DIR

# Create database backup
mysqldump -u $DB_USER -p $DB_NAME > $BACKUP_DIR/inspection_system_$DATE.sql

# Compress backup
gzip $BACKUP_DIR/inspection_system_$DATE.sql

# Keep only last 7 days of backups
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete

echo "Backup completed: inspection_system_$DATE.sql.gz"
```

```bash
# Make script executable
sudo chmod +x /opt/inspection_webapp/mysql_backup.sh

# Add to crontab for daily backups at 2 AM
sudo crontab -e
# Add this line:
# 0 2 * * * /opt/inspection_webapp/mysql_backup.sh >> /var/log/mysql-backup.log 2>&1
```

### Troubleshooting MySQL Issues

#### Common Issues and Solutions:

1. **MySQL Won't Start:**
   ```bash
   # Check MySQL error log
   sudo tail -f /var/log/mysql/error.log
   
   # Check MySQL configuration
   sudo mysqld --help --verbose
   
   # Reset MySQL root password if needed
   sudo systemctl stop mysql
   sudo mysqld_safe --skip-grant-tables &
   mysql -u root
   ```

2. **Connection Refused:**
   ```bash
   # Check if MySQL is running
   sudo systemctl status mysql
   
   # Check MySQL port
   sudo netstat -tlnp | grep 3306
   
   # Check firewall
   sudo ufw status
   ```

3. **Permission Denied:**
   ```bash
   # Check user privileges
   mysql -u root -p -e "SHOW GRANTS FOR 'inspection_user'@'localhost';"
   
   # Grant privileges again
   mysql -u root -p -e "GRANT ALL PRIVILEGES ON inspection_system.* TO 'inspection_user'@'localhost'; FLUSH PRIVILEGES;"
   ```

4. **Character Set Issues:**
   ```bash
   # Check database character set
   mysql -u inspection_user -p -e "SHOW CREATE DATABASE inspection_system;"
   
   # Check table character set
   mysql -u inspection_user -p -e "SHOW CREATE TABLE main_inspection;" inspection_system
   ```

### Performance Optimization

#### Step 1: Analyze MySQL Performance

```bash
# Enable slow query log
mysql -u root -p -e "SET GLOBAL slow_query_log = 'ON';"
mysql -u root -p -e "SET GLOBAL long_query_time = 2;"

# Check MySQL variables
mysql -u root -p -e "SHOW VARIABLES LIKE '%buffer%';"
mysql -u root -p -e "SHOW VARIABLES LIKE '%cache%';"
```

#### Step 2: Optimize Tables

```bash
# Analyze tables
mysql -u inspection_user -p -e "ANALYZE TABLE main_inspection;" inspection_system

# Optimize tables
mysql -u inspection_user -p -e "OPTIMIZE TABLE main_inspection;" inspection_system
```

This comprehensive MySQL installation guide provides everything needed to set up and configure MySQL specifically for the Inspection System Webapp on Debian Linux.

### Step 5: Install Web Server (Nginx)

```bash
# Install Nginx
sudo apt install -y nginx

# Start and enable Nginx
sudo systemctl start nginx
sudo systemctl enable nginx

# Check Nginx status
sudo systemctl status nginx
```

### Step 6: Create Application User and Directory

```bash
# Create application user
sudo useradd -m -s /bin/bash inspection
sudo usermod -aG www-data inspection

# Create application directory
sudo mkdir -p /opt/inspection_webapp
sudo chown inspection:inspection /opt/inspection_webapp
```

### Step 7: Transfer Application Files

**Option A: Using Git (if repository is available)**
```bash
# Switch to application user
sudo su - inspection

# Clone repository
cd /opt/inspection_webapp
git clone <your-repository-url> .

# Or if you have the files locally, copy them:
# scp -r /path/to/local/files/* inspection@your-vm-ip:/opt/inspection_webapp/
```

**Option B: Manual File Transfer**
```bash
# From your Windows machine, copy files to the VM
# Use SCP, SFTP, or any file transfer method

# Example with SCP:
# scp -r C:\Inspection_webapp\Conuar\conuar_webapp\* inspection@your-vm-ip:/opt/inspection_webapp/
```

### Step 8: Set Up Python Virtual Environment

```bash
# Switch to application user
sudo su - inspection
cd /opt/inspection_webapp

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip
```

### Step 9: Install Python Dependencies

```bash
# Install requirements
pip install -r requirements.txt

# Install additional production dependencies
pip install gunicorn psycopg2-binary mysqlclient
```

### Step 10: Configure Database Settings

```bash
# Edit settings.py
nano config/settings.py
```

**Update database configuration:**
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'inspection_system',
        'USER': 'inspection_user',
        'PASSWORD': 'your_secure_password',
        'HOST': 'localhost',
        'PORT': '3306',
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

# Add these production settings
DEBUG = False
ALLOWED_HOSTS = ['your-vm-ip', 'your-domain.com', 'localhost']

# Static files configuration
STATIC_URL = '/static/'
STATIC_ROOT = '/opt/inspection_webapp/staticfiles/'

# Media files configuration
MEDIA_URL = '/media/'
MEDIA_ROOT = '/opt/inspection_webapp/media/'
```

### Step 11: Run Database Migrations

```bash
# Make sure you're in the virtual environment
source venv/bin/activate

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput
```

### Step 12: Configure Gunicorn

```bash
# Create Gunicorn configuration
nano gunicorn_config.py
```

**Add this content:**
```python
bind = "127.0.0.1:8000"
workers = 3
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 30
keepalive = 2
preload_app = True
```

### Step 13: Create Systemd Service

```bash
# Create systemd service file
sudo nano /etc/systemd/system/inspection-webapp.service
```

**Add this content:**
```ini
[Unit]
Description=Inspection Webapp Gunicorn daemon
After=network.target

[Service]
User=inspection
Group=www-data
WorkingDirectory=/opt/inspection_webapp
Environment="PATH=/opt/inspection_webapp/venv/bin"
ExecStart=/opt/inspection_webapp/venv/bin/gunicorn --config gunicorn_config.py config.wsgi:application
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always

[Install]
WantedBy=multi-user.target
```

### Step 14: Configure Nginx

```bash
# Create Nginx configuration
sudo nano /etc/nginx/sites-available/inspection-webapp
```

**Add this content:**
```nginx
server {
    listen 80;
    server_name your-vm-ip your-domain.com;

    client_max_body_size 100M;

    location /static/ {
        alias /opt/inspection_webapp/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /opt/inspection_webapp/media/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
    }
}
```

### Step 15: Enable and Start Services

```bash
# Enable Nginx site
sudo ln -s /etc/nginx/sites-available/inspection-webapp /etc/nginx/sites-enabled/

# Remove default Nginx site
sudo rm /etc/nginx/sites-enabled/default

# Test Nginx configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx

# Enable and start the application service
sudo systemctl enable inspection-webapp
sudo systemctl start inspection-webapp

# Check service status
sudo systemctl status inspection-webapp
```

### Step 16: Configure Firewall

```bash
# Install UFW if not already installed
sudo apt install -y ufw

# Configure firewall
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'
sudo ufw enable

# Check firewall status
sudo ufw status
```

### Step 17: Set Up Log Rotation

```bash
# Create log rotation configuration
sudo nano /etc/logrotate.d/inspection-webapp
```

**Add this content:**
```
/opt/inspection_webapp/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 inspection www-data
    postrotate
        systemctl reload inspection-webapp
    endscript
}
```

### Step 18: Set Up SSL Certificate (Optional but Recommended)

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtain SSL certificate
sudo certbot --nginx -d your-domain.com

# Test automatic renewal
sudo certbot renew --dry-run
```

### Step 19: Configure PLC Scripts (Production)

```bash
# Create systemd services for PLC scripts
sudo nano /etc/systemd/system/plc-reader.service
```

**Add this content:**
```ini
[Unit]
Description=PLC Data Reader Service
After=network.target

[Service]
Type=simple
User=inspection
Group=inspection
WorkingDirectory=/opt/inspection_webapp
Environment="PATH=/opt/inspection_webapp/venv/bin"
ExecStart=/opt/inspection_webapp/venv/bin/python etl/plc_data_reader.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Create PLC processor service
sudo nano /etc/systemd/system/plc-processor.service
```

**Add this content:**
```ini
[Unit]
Description=PLC Data Processor Service
After=network.target

[Service]
Type=simple
User=inspection
Group=inspection
WorkingDirectory=/opt/inspection_webapp
Environment="PATH=/opt/inspection_webapp/venv/bin"
ExecStart=/opt/inspection_webapp/venv/bin/python etl/plc_data_processor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Step 20: Final Configuration and Testing

```bash
# Enable PLC services
sudo systemctl enable plc-reader
sudo systemctl enable plc-processor

# Start PLC services
sudo systemctl start plc-reader
sudo systemctl start plc-processor

# Check all services
sudo systemctl status inspection-webapp plc-reader plc-processor

# Test the application
curl http://your-vm-ip
```

### Step 21: Set Up Monitoring and Maintenance

```bash
# Create monitoring script
sudo nano /opt/inspection_webapp/monitor.sh
```

**Add this content:**
```bash
#!/bin/bash
# Monitor script for inspection webapp

echo "=== Inspection Webapp Status ==="
echo "Date: $(date)"
echo ""

echo "Services Status:"
systemctl status inspection-webapp --no-pager
systemctl status plc-reader --no-pager
systemctl status plc-processor --no-pager

echo ""
echo "Disk Usage:"
df -h /opt/inspection_webapp

echo ""
echo "Memory Usage:"
free -h

echo ""
echo "Recent Logs:"
tail -n 20 /var/log/nginx/access.log
```

```bash
# Make script executable
sudo chmod +x /opt/inspection_webapp/monitor.sh

# Add to crontab for regular monitoring
sudo crontab -e
# Add this line for daily monitoring at 6 AM:
# 0 6 * * * /opt/inspection_webapp/monitor.sh >> /var/log/inspection-monitor.log
```

### Troubleshooting

**Common Issues and Solutions:**

1. **Database Connection Error:**
   ```bash
   # Check MariaDB status
   sudo systemctl status mariadb
   
   # Test database connection
   mysql -u inspection_user -p inspection_system
   ```

2. **Permission Issues:**
   ```bash
   # Fix file permissions
   sudo chown -R inspection:www-data /opt/inspection_webapp
   sudo chmod -R 755 /opt/inspection_webapp
   ```

3. **Service Won't Start:**
   ```bash
   # Check service logs
   sudo journalctl -u inspection-webapp -f
   sudo journalctl -u plc-reader -f
   sudo journalctl -u plc-processor -f
   ```

4. **Nginx Configuration Error:**
   ```bash
   # Test Nginx configuration
   sudo nginx -t
   
   # Check Nginx logs
   sudo tail -f /var/log/nginx/error.log
   ```

### Security Considerations

1. **Change default passwords**
2. **Configure firewall properly**
3. **Set up regular backups**
4. **Keep system updated**
5. **Monitor logs regularly**
6. **Use SSL certificates**

### Backup Strategy

```bash
# Create backup script
sudo nano /opt/inspection_webapp/backup.sh
```

**Add this content:**
```bash
#!/bin/bash
BACKUP_DIR="/opt/backups/inspection_webapp"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup database
mysqldump -u inspection_user -p inspection_system > $BACKUP_DIR/database_$DATE.sql

# Backup application files
tar -czf $BACKUP_DIR/app_files_$DATE.tar.gz /opt/inspection_webapp

# Keep only last 7 days of backups
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
```

This comprehensive guide will help you successfully deploy the Inspection System Webapp on a Debian Linux virtual machine with production-ready configuration.

## Usage

### 1. Login
- Navigate to `/login/` to access the system
- Use your credentials to log in

### 2. View Inspections
- After login, you'll be redirected to `/inspections/`
- View all inspection records in a paginated table

### 3. Inspection Details
- Click "View" on any inspection to see details
- View uploaded photos and inspection metadata

### 4. Admin Interface
- Access `/admin/` for database management
- Manage users, inspections, and photos

## Database Models

### User
- Custom user model with inspector/supervisor roles
- Authentication and authorization

### Inspection
- Inspection metadata (ID, type, batch, serial numbers)
- Status tracking (pending, in_progress, completed, etc.)
- Inspector and supervisor assignments

### InspectionPhoto
- Photo uploads with captions and categorization
- Linked to specific inspections
- Photo type classification (overview, detail, defect, etc.)

## Security Features

- Login required for inspection access
- CSRF protection on all forms
- Secure password handling
- Role-based access control

## File Structure

```
conuar_webapp/
├── main/                    # Main application
│   ├── models.py           # Database models
│   ├── views.py            # View logic
│   ├── urls.py             # URL routing
│   ├── forms.py            # Form definitions
│   └── admin.py            # Admin interface
├── templates/main/          # HTML templates
│   ├── base.html           # Base template
│   ├── login.html          # Login page
│   ├── inspection_list.html # Inspection list
│   └── inspection_detail.html # Inspection details
├── static/css/              # CSS files
├── media/                   # Uploaded files
└── conuar_webapp/          # Project settings
    ├── settings.py         # Django settings
    └── urls.py             # Main URL configuration
```

## Development

- **Debug Mode**: Enabled by default for development
- **Media Files**: Served automatically in development
- **Database**: MySQL for development and production (with MariaDB compatibility)

## Production Considerations

- Set `DEBUG = False` in settings
- Configure proper database (MySQL/MariaDB recommended)
- Set up static file serving
- Configure media file storage
- Use environment variables for sensitive data
- Set up proper logging

# PLC Scripts - Sistema Conuar

Este directorio contiene dos scripts separados para el monitoreo y procesamiento de datos del PLC en el sistema de inspección de combustible Conuar.

## Scripts Disponibles

### 1. `plc_data_reader.py`
**Propósito**: Lee datos del PLC y los almacena en la tabla `main_plc_readings`

**Funcionalidades**:
- Se conecta al PLC usando Modbus TCP
- Lee todos los registros del PLC cada segundo
- Almacena los datos raw en la tabla `main_plc_readings`
- Marca los registros como no procesados (`processed=False`)
- No realiza procesamiento de inspecciones

**Uso**:
```bash
# Activar entorno virtual
C:\Inspection_webapp\conuar_env\Scripts\activate

# Ejecutar lector PLC
python etl/plc_data_reader.py
```

### 2. `plc_data_processor.py`
**Propósito**: Procesa datos de `main_plc_readings` y actualiza las tablas de inspección

**Funcionalidades**:
- Lee registros no procesados de `main_plc_readings`
- Crea/actualiza inspecciones en `main_inspection`
- Crea eventos PLC en `main_inspectionplcevent`
- Mapea fotos en `main_inspectionphoto`
- Actualiza estado de máquina en `main_inspectionmachine`
- Marca registros como procesados

**Uso**:
```bash
# Activar entorno virtual
C:\Inspection_webapp\conuar_env\Scripts\activate

# Ejecutar procesador PLC
python etl/plc_data_processor.py
```

## Arquitectura

```
PLC ──→ plc_data_reader.py ──→ main_plc_readings ──→ plc_data_processor.py ──→ Tablas de Inspección
```

### Flujo de Datos

1. **Lectura**: `plc_data_reader.py` lee datos del PLC y los guarda en `main_plc_readings`
2. **Procesamiento**: `plc_data_processor.py` lee datos no procesados y los convierte en inspecciones
3. **Actualización**: Se actualizan las tablas `main_inspection`, `main_inspectionphoto`, `main_inspectionmachine`

## Configuración

Los scripts utilizan la configuración del sistema almacenada en `main_systemconfiguration`:
- `plc_ip`: Dirección IP del PLC
- `plc_port`: Puerto del PLC (por defecto 502)
- `media_storage_path`: Ruta de almacenamiento de fotos

## Tabla main_plc_readings

La nueva tabla `main_plc_readings` almacena todos los datos raw del PLC:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `timestamp_plc` | DateTime | Timestamp del PLC |
| `id_inspection` | Integer | ID de la inspección |
| `execution_id` | Integer | ID ejecución |
| `control_point_id` | Integer | ID punto de control |
| `execution_type` | Integer | Tipo de ejecución (1=automatic, 2=manual, 3=free) |
| `control_point_label` | Integer | Etiqueta punto de control |
| `x_control_point` | Float | X punto de control |
| `y_control_point` | Float | Y punto de control |
| `z_control_point` | Float | Z punto de control |
| `plate_angle` | Float | Ángulo del plato |
| `control_point_creator` | Integer | Usuario creador punto de control |
| `program_creator` | Integer | Usuario creador Programa |
| `program_version` | Integer | Version del programa |
| `camera_id` | Integer | ID Cámara |
| `filming_type` | Integer | Tipo filmación (1=video, 2=photo) |
| `last_photo_request_timestamp` | Integer | Último timestamp solicitud foto cámara |
| `new_photos_available` | Boolean | Flag indicando nuevas fotos |
| `photo_count` | Integer | Número de nuevas fotos |
| `processed` | Boolean | Indica si el registro ya fue procesado |
| `processing_error` | Text | Error durante el procesamiento |

## Ejecución en Producción

### Opción 1: Scripts Separados
Ejecutar ambos scripts en procesos separados:

```bash
# Terminal 1 - Lector PLC
C:\Inspection_webapp\conuar_env\Scripts\activate
python etl/plc_data_reader.py

# Terminal 2 - Procesador
C:\Inspection_webapp\conuar_env\Scripts\activate
python etl/plc_data_processor.py
```

### Opción 2: Servicios de Windows
Crear servicios de Windows para ejecutar los scripts automáticamente.

## Logs

Cada script genera sus propios logs:
- `plc_data_reader.log`: Logs del lector PLC
- `plc_data_processor.log`: Logs del procesador

## Monitoreo

Para verificar el estado del sistema:

1. **Verificar lecturas PLC**:
   ```sql
   SELECT COUNT(*) FROM main_plc_readings WHERE processed = FALSE;
   ```

2. **Verificar inspecciones recientes**:
   ```sql
   SELECT * FROM main_inspection ORDER BY created_at DESC LIMIT 10;
   ```

3. **Verificar estado de la máquina**:
   ```sql
   SELECT * FROM main_inspectionmachine;
   ```

## Ventajas de la Separación

1. **Escalabilidad**: Cada script puede ejecutarse en servidores diferentes
2. **Confiabilidad**: Si un script falla, el otro continúa funcionando
3. **Mantenimiento**: Fácil actualización independiente de cada script
4. **Debugging**: Más fácil identificar problemas en cada proceso
5. **Recuperación**: Los datos raw se mantienen para reprocesamiento

## Migración desde Script Original

El script original `plc_inspection_monitor.py` se mantiene como referencia. Los nuevos scripts proporcionan la misma funcionalidad pero con mejor separación de responsabilidades.


# PLC Inspection Monitor ETL System

This ETL (Extract, Transform, Load) system monitors a PLC for inspection events and automatically manages the inspection database.

## Features

- **Real-time PLC Monitoring**: Continuously reads data from PLC via Modbus TCP
- **Automatic Inspection Creation**: Creates new inspections based on PLC data
- **Database Integration**: Updates inspection machine statistics and records PLC events
- **Photo Management**: Automatically captures and stores photos from cameras
- **Configuration Management**: Uses system configuration for PLC and camera settings

## Files

- `plc_inspection_monitor.py` - Main monitoring script
- `setup_plc_monitor.py` - Setup and testing script
- `Demo_Cliente_Modbus.py` - Original demo script (reference)
- `requirements.txt` - Python dependencies
- `README.md` - This documentation

## Installation

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure System**:
   - Use the web interface to set PLC IP and port in Configuration
   - Ensure PLC is accessible on the network

3. **Setup Database**:
   ```bash
   python setup_plc_monitor.py
   ```

## Usage

### Basic Monitoring
```bash
python plc_inspection_monitor.py
```

### Setup and Test
```bash
python setup_plc_monitor.py
```

## PLC Data Mapping

The script reads the following data from PLC registers:

| Register | Field | Description |
|----------|-------|-------------|
| 1 | timestamp_plc | PLC timestamp |
| 2 | id_inspection | Inspection ID |
| 3 | execution_id | Execution ID (between breaks) |
| 4 | control_point_id | Control point ID (e.g., "Zapata num. 5") |
| 5 | execution_type | Execution type (1=Auto, 2=Manual, 3=Free) |
| 6 | control_point_label | Control point label |
| 7 | x_control_point | X coordinate |
| 8 | y_control_point | Y coordinate |
| 9 | z_control_point | Z coordinate |
| 10 | plate_angle | Plate angle |
| 11 | control_point_creator | Control point creator user |
| 12 | program_creator | Program creator user |
| 13 | program_version | Program version |
| 14 | camera_id | Camera ID |
| 15 | filming_type | Filming type (1=Video, 2=Photo) |
| 16 | last_photo_request_timestamp | Last photo request timestamp |
| 17 | new_photos_available | New photos available flag |
| 18 | photo_count | Number of new photos |

## Database Operations

### 1. Inspection Management
- Creates new inspections automatically
- Updates existing inspections
- Links inspections to the inspection machine

### 2. Machine Statistics
- Updates total inspection count
- Updates daily inspection count
- Records last inspection timestamp

### 3. PLC Events
- Records all PLC events in `main_inspection_plc_events` table
- Links events to specific inspections
- Stores position and control data

### 4. Photo Management
- Monitors for new photos in media folder
- Automatically links photos to inspections
- Creates photo records in database

## Configuration

The system uses the Django configuration system:

- **PLC Settings**: IP address and port from SystemConfiguration
- **Media Path**: Photo storage path from SystemConfiguration
- **Camera IPs**: Camera addresses from SystemConfiguration

## Logging

The system creates detailed logs in `plc_monitor.log`:

- Connection status
- Data processing events
- Error messages
- Performance metrics

## Error Handling

- **Connection Errors**: Automatic reconnection attempts
- **Data Errors**: Graceful handling of invalid PLC data
- **Database Errors**: Transaction rollback on failures
- **File Errors**: Safe handling of missing photo files

## Monitoring

The script runs continuously and:
- Reads PLC data every second
- Processes new events immediately
- Updates database in real-time
- Logs all activities

## Stopping the Monitor

- **Ctrl+C**: Graceful shutdown
- **SIGTERM**: Clean exit
- **Database errors**: Automatic stop with logging

## Troubleshooting

### Common Issues

1. **PLC Connection Failed**:
   - Check IP address and port
   - Verify network connectivity
   - Ensure PLC is running

2. **Database Errors**:
   - Check Django configuration
   - Verify database permissions
   - Run migrations if needed

3. **Photo Issues**:
   - Check media folder permissions
   - Verify photo file formats
   - Ensure proper file paths

### Debug Mode

Enable debug logging by modifying the script:
```python
logging.basicConfig(level=logging.DEBUG)
```

## Integration

This ETL system integrates with:
- **Django Web Application**: Uses same models and configuration
- **PLC Systems**: Modbus TCP communication
- **Camera Systems**: File-based photo capture
- **Database**: MySQL/MariaDB via Django ORM

## Performance

- **Memory Usage**: Minimal, processes data in real-time
- **CPU Usage**: Low, efficient Modbus communication
- **Network**: Minimal bandwidth, only register reads
- **Database**: Optimized queries, batch operations

## Security

- **Network**: Uses secure Modbus TCP
- **Database**: Django ORM with proper permissions
- **Files**: Safe file handling, no arbitrary execution
- **Logging**: No sensitive data in logs


## License

This project is for educational and demonstration purposes.

## Support

For technical support or questions, please refer to the Django documentation or contact the development team.

