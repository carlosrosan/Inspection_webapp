from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.db import models

def home(request):
    """Home page view"""
    context = {
        'title': 'Sistema de Inspección de Combustible',
        'description': 'Sistema avanzado de inspección y control de calidad de combustible desarrollado por ArByte.',
        'features': [
            'Inspección de Calidad',
            'Control de Procesos',
            'Reportes Automatizados',
            'Gestión de Documentos'
        ]
    }
    return render(request, 'main/home.html', context)

def about(request):
    """About page view"""
    context = {
        'title': 'Acerca de ArByte',
        'description': 'Conoce más sobre nuestra empresa y especialización en sistemas de inspección de combustible.',
        'company_info': {
            'name': 'ArByte',
            'founded': '2018',
            'mission': 'Desarrollar soluciones tecnológicas innovadoras para la industria del combustible.'
        }
    }
    return render(request, 'main/about.html', context)

def contact(request):
    """Contact page view"""
    context = {
        'title': 'Contáctanos - ArByte',
        'description': 'Ponte en contacto con nuestro equipo de especialistas en inspección de combustible.',
        'contact_info': {
            'email': 'info@arbyte.com',
            'phone': '+549 11 6484 4321',
            'address': 'Pilar, Provincia de Buenos Aires, Argentina.'
        }
    }
    return render(request, 'main/contact.html', context)


def login_view(request):
    """User login view"""
    if request.user.is_authenticated:
        return redirect('main:home')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'¡Bienvenido de vuelta, {user.username}!')
            # Redirect to the page they were trying to access, or home
            next_url = request.GET.get('next', 'main:home')
            return redirect(next_url)
        else:
            messages.error(request, 'Nombre de usuario o contraseña inválidos.')
    
    context = {
        'title': 'Iniciar Sesión - Inspección de combustible',
        'next': request.GET.get('next', '')
    }
    return render(request, 'main/login.html', context)

def logout_view(request):
    """User logout view"""
    logout(request)
    messages.success(request, 'Has cerrado sesión exitosamente.')
    return redirect('main:home')


@login_required(login_url='main:login')
def dashboard(request):
    """Machine status dashboard view"""
    from .models import InspectionMachine, MachineLog, Inspection
    from django.db.models import Count, Q
    from datetime import datetime, timedelta
    import random
    
    # Get or create the inspection machine
    machine, created = InspectionMachine.objects.get_or_create(
        machine_id='MAQ-001',
        defaults={
            'name': 'Analizador de Combustible ArByte-3000',
            'model': 'AB-3000',
            'version': 'v2.1.3',
            'status': 'idle',
            'total_inspections': 0,
            'inspections_today': 0,
            'uptime_hours': 0.0,
            'success_rate': 100.0,
            'average_inspection_time': 0.0,
        }
    )
    
    # Generate sample data if machine was just created
    if created:
        # Generate some sample inspection data
        machine.total_inspections = random.randint(150, 300)
        machine.inspections_today = random.randint(5, 15)
        machine.uptime_hours = random.uniform(120.5, 200.8)
        machine.success_rate = random.uniform(95.0, 99.8)
        machine.average_inspection_time = random.uniform(8.5, 15.2)
        machine.last_inspection = datetime.now() - timedelta(minutes=random.randint(5, 60))
        machine.last_maintenance = datetime.now() - timedelta(days=random.randint(1, 7))
        machine.save()
        
        # Create some sample logs
        log_messages = [
            "Máquina iniciada correctamente",
            "Calibración completada exitosamente",
            "Inspección de muestra #{} completada".format(random.randint(100, 999)),
            "Sistema de análisis funcionando normalmente",
            "Verificación de calidad en progreso",
        ]
        
        for i in range(10):
            MachineLog.objects.create(
                machine=machine,
                log_type=random.choice(['status_change', 'inspection_complete', 'calibration']),
                message=random.choice(log_messages)
            )
    
    # Get recent logs
    recent_logs = machine.logs.all()[:10]
    
    # Calculate additional metrics
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    
    # Get inspection statistics
    total_inspections = Inspection.objects.count()
    inspections_this_week = Inspection.objects.filter(
        inspection_date__date__gte=week_ago
    ).count()
    
    # Calculate machine efficiency
    if machine.total_inspections > 0:
        efficiency = (machine.inspections_today / 24) * 100  # Assuming 24 inspections per day is 100%
    else:
        efficiency = 0
    
    # Generate sample data for charts
    chart_data = {
        'daily_inspections': [random.randint(8, 20) for _ in range(7)],
        'success_rates': [random.uniform(95, 100) for _ in range(7)],
        'inspection_times': [random.uniform(8, 16) for _ in range(7)],
    }
    
    context = {
        'title': 'Panel de Control - Estado de Máquina',
        'description': 'Monitoreo en tiempo real del sistema de inspección de combustible',
        'user': request.user,
        'machine': machine,
        'recent_logs': recent_logs,
        'stats': {
            'total_inspections': total_inspections,
            'inspections_this_week': inspections_this_week,
            'machine_efficiency': round(efficiency, 1),
            'uptime_percentage': round((machine.uptime_hours / 168) * 100, 1),  # Assuming 168 hours per week
        },
        'chart_data': chart_data,
    }
    return render(request, 'main/dashboard.html', context)

# Inspection views
@login_required(login_url='main:login')
def inspection_list(request):
    """List all inspections"""
    from .models import Inspection
    
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    type_filter = request.GET.get('type', '')
    search_query = request.GET.get('search', '')
    
    # Start with all inspections
    inspections = Inspection.objects.all()
    
    # Apply filters
    if status_filter:
        inspections = inspections.filter(status=status_filter)
    
    if type_filter:
        inspections = inspections.filter(inspection_type=type_filter)
    
    if search_query:
        inspections = inspections.filter(
            models.Q(title__icontains=search_query) |
            models.Q(product_name__icontains=search_query) |
            models.Q(description__icontains=search_query) |
            models.Q(product_code__icontains=search_query)
        )
    
    # Get unique values for filter dropdowns
    status_choices = Inspection.INSPECTION_STATUS_CHOICES
    type_choices = Inspection.INSPECTION_TYPE_CHOICES
    
    context = {
        'title': 'Lista de Inspecciones de Combustible',
        'description': 'Ver todas las inspecciones de calidad de combustible',
        'inspections': inspections,
        'status_choices': status_choices,
        'type_choices': type_choices,
        'current_status': status_filter,
        'current_type': type_filter,
        'search_query': search_query,
        'total_count': inspections.count(),
    }
    
    return render(request, 'main/inspection_list.html', context)

@login_required(login_url='main:login')
def inspection_detail(request, inspection_id):
    """Show detailed view of a specific inspection"""
    from .models import Inspection, InspectionPhoto
    from django.shortcuts import get_object_or_404
    
    inspection = get_object_or_404(Inspection, id=inspection_id)
    photos = inspection.photos.all()
    
    context = {
        'title': f'Inspección de Combustible: {inspection.title}',
        'description': f'Vista detallada de la inspección de calidad de {inspection.product_name}',
        'inspection': inspection,
        'photos': photos,
        'photo_count': photos.count(),
    }
    
    return render(request, 'main/inspection_detail.html', context)
