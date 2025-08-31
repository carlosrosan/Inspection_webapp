# Nuclear Fuel Rod Inspection System

A Django-based web application for managing nuclear fuel rod inspections with photo documentation and quality control.

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

## Default Users

The system comes with pre-configured test users:

- **Inspector**: `inspector` / `inspector123`
- **Supervisor**: `supervisor` / `supervisor123`
- **Admin**: Use the superuser you created

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

## License

This project is for educational and demonstration purposes.

## Support

For technical support or questions, please refer to the Django documentation or contact the development team.

