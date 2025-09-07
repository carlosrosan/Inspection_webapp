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
- SQLite database (can be configured for other databases)

## Installation

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
- **Database**: SQLite for development (easily configurable for production)

## Production Considerations

- Set `DEBUG = False` in settings
- Configure proper database (PostgreSQL recommended)
- Set up static file serving
- Configure media file storage
- Use environment variables for sensitive data
- Set up proper logging

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
- **Database**: MySQL/PostgreSQL via Django ORM

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

