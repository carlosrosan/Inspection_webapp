# 🔍 Inspection Reporting System

A comprehensive Django-based web application for managing industrial inspections with photo documentation, quality control, and role-based access management.

## 📋 Overview

The Inspection Reporting System is a professional-grade web application designed for industry professionals to:

- **Create and manage product inspections** with detailed information and metadata
- **Upload and organize inspection photos** with categorization and captions
- **Track inspection status** through complete lifecycle management
- **Implement quality control workflows** with inspector and supervisor roles
- **Generate comprehensive inspection reports** with photo galleries
- **Maintain audit trails** for compliance and safety requirements

## ✨ Key Features

- **🔐 Secure Authentication**: Role-based access control with Inspector and Supervisor roles
- **📸 Photo Management**: Upload, categorize, and organize inspection photos
- **📊 Status Tracking**: Complete workflow from pending to completed inspections
- **🔍 Advanced Filtering**: Search and filter inspections by type, status, and metadata
- **📱 Responsive Design**: Modern Bootstrap-based interface for all devices
- **🛡️ Security**: CSRF protection, secure file handling, and audit logging
- **📈 Reporting**: Comprehensive inspection reports with photo galleries
- **⚡ Performance**: Optimized database queries and efficient file handling

## 🏗️ System Architecture

### Technology Stack
- **Backend**: Django 4.2.23 (Python web framework)
- **Database**: SQLite (configurable for production databases)
- **Image Processing**: Pillow 10.0.1+ for photo handling
- **Frontend**: Bootstrap 5 for responsive UI
- **Authentication**: Django's built-in user management system

### Core Models

#### Inspection Model
- Product information (name, code, batch, serial numbers)
- Inspection metadata (type, status, location, dates)
- Personnel assignments (inspector, supervisor)
- Results and recommendations
- Audit timestamps

#### InspectionPhoto Model
- Photo uploads with automatic date-based organization
- Caption and categorization system
- Photo type classification (overview, detail, defect, etc.)
- Linked to specific inspections

#### User Model
- Custom user model with role-based permissions
- Inspector and Supervisor role assignments
- Secure authentication and authorization

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- pip (Python package installer)
- Virtual environment (recommended)

### Installation Steps

1. **Clone or navigate to the project**
   ```bash
   cd Conuar/conuarenv/conuar_webapp
   ```

2. **Create and activate virtual environment**
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate
   
   # macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
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

7. **Access the application**
   - Main application: http://127.0.0.1:8000/
   - Admin interface: http://127.0.0.1:8000/admin/
   - Inspections: http://127.0.0.1:8000/inspections/

## 📖 Usage Guide

### 1. Authentication
- Navigate to `/login/` to access the system
- Use your credentials to log in
- Role-based access control determines available features

### 2. Inspection Management
- **View Inspections**: Access `/inspections/` to see all inspection records
- **Create Inspections**: Use the admin interface or API endpoints
- **Upload Photos**: Attach photos to inspections with captions
- **Update Status**: Track inspection progress through workflow stages

### 3. Photo Management
- Photos are automatically organized by date (`media/inspections/YYYY/MM/DD/`)
- Support for multiple photo types (overview, detail, defect, etc.)
- Caption system for detailed documentation
- Automatic thumbnail generation and optimization

### 4. Quality Control
- Status tracking: Pending → In Progress → Completed
- Supervisor approval workflows
- Comprehensive audit trails
- Result documentation and recommendations

## 🗄️ Database Management

### Commands
```bash
# Create new migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Check migration status
python manage.py showmigrations

# Create sample data (if available)
python manage.py create_sample_inspections
```

### Database Models
- **User**: Authentication and role management
- **Inspection**: Core inspection data and metadata
- **InspectionPhoto**: Photo uploads and organization
- **Admin**: Django admin interface for data management

## 🔧 Development

### Project Structure
```
conuar_webapp/
├── main/                    # Main application
│   ├── models.py           # Database models
│   ├── views.py            # View logic and business rules
│   ├── urls.py             # URL routing
│   ├── forms.py            # Form definitions
│   ├── admin.py            # Admin interface configuration
│   └── management/         # Custom management commands
├── templates/main/          # HTML templates
│   ├── base.html           # Base template with navigation
│   ├── login.html          # Authentication page
│   ├── inspection_list.html # Inspection overview
│   └── inspection_detail.html # Detailed inspection view
├── static/css/              # CSS stylesheets
├── media/                   # Uploaded files and photos
├── config/                  # Project configuration
│   ├── settings.py         # Django settings
│   └── urls.py             # Main URL configuration
└── manage.py                # Django management script
```

### Development Features
- **Debug Mode**: Enabled by default for development
- **Media Files**: Automatically served in development
- **Database**: SQLite for development (easily configurable)
- **Hot Reload**: Automatic server restart on code changes

## 🚀 Production Deployment

### Configuration Changes
- Set `DEBUG = False` in settings
- Configure production database (PostgreSQL recommended)
- Set up static file serving (nginx/Apache)
- Configure media file storage (AWS S3, Azure Blob, etc.)
- Use environment variables for sensitive data

### Security Considerations
- HTTPS enforcement
- Secure file upload validation
- Rate limiting and DDoS protection
- Regular security updates
- Comprehensive logging and monitoring

### Performance Optimization
- Database query optimization
- Static file compression and caching
- CDN integration for media files
- Background task processing
- Database connection pooling

## 🧪 Testing

### Running Tests
```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test main

# Run with coverage
coverage run --source='.' manage.py test
coverage report
```

### Test Data
- Sample inspections and photos available
- Management commands for data generation
- Fixtures for consistent testing

## 📚 API Documentation

The system provides RESTful API endpoints for:
- Inspection CRUD operations
- Photo upload and management
- User authentication and management
- Status updates and workflow management

## 🤝 Contributing

### Development Setup
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

### Code Standards
- Follow PEP 8 Python style guidelines
- Include docstrings for all functions
- Write comprehensive tests
- Update documentation as needed

## 📄 License

This project is developed for educational and demonstration purposes. Please ensure compliance with all applicable nuclear industry regulations and safety standards.

## 🆘 Support

### Documentation
- [Django Documentation](https://docs.djangoproject.com/)
- [Project Wiki](link-to-wiki-if-available)
- [API Reference](link-to-api-docs-if-available)

### Getting Help
- Check existing documentation and README files
- Review Django community resources
- Contact the development team for technical support
- Report issues through the project's issue tracker

## 🔄 Version History

- **v1.0.0**: Initial release with core inspection functionality
- **v1.1.0**: Added photo management and advanced filtering
- **v1.2.0**: Enhanced security and role-based access control
- **Current**: Production-ready inspection management system

---

**⚠️ Important Notice**: This system is designed for nuclear industry applications. Ensure all deployments comply with relevant nuclear safety regulations and industry standards.
