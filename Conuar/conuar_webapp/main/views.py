from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.db import models
from django.contrib.auth import update_session_auth_hash
from .forms import SystemConfigurationForm, CustomUserCreationForm, CustomPasswordChangeForm
from .models import SystemConfiguration, User


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



def login_view(request):
    """User login view"""
    if request.user.is_authenticated:
        return redirect('main:dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'¡Bienvenido de vuelta, {user.username}!')
            # Redirect to the page they were trying to access, or dashboard
            next_url = request.GET.get('next', 'main:dashboard')
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
    return redirect('main:dashboard')


@login_required(login_url='main:login')
def dashboard(request):
    """Machine status dashboard view"""
    from .models import InspectionMachine, MachineLog, Inspection
    from django.db.models import Count, Q
    from datetime import datetime, timedelta
    import random
    
    # Get or create the inspection machine and single inspection
    machine = InspectionMachine.get_machine()
    inspection = Inspection.get_inspection()
    
    # Update machine metrics with real data
    machine.total_inspections = Inspection.objects.count()
    machine.inspections_today = Inspection.objects.filter(
        inspection_date__date=datetime.now().date()
    ).count()
    machine.uptime_hours = random.uniform(120.5, 200.8)
    machine.success_rate = random.uniform(95.0, 99.8)
    machine.average_inspection_time = random.uniform(8.5, 15.2)
    machine.last_inspection = datetime.now() - timedelta(minutes=random.randint(5, 60))
    machine.last_maintenance = datetime.now() - timedelta(days=random.randint(1, 7))
    machine.save()
    
    # Create some sample logs if none exist
    if not machine.logs.exists():
        log_messages = [
            "Máquina iniciada correctamente",
            "Calibración completada exitosamente",
            "Inspección de muestra completada",
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
        'title': 'Estado del Sistema',
        'description': 'Monitoreo en tiempo real del sistema de inspección de combustible',
        'user': request.user,
        'machine': machine,
        'inspection': inspection,
        'recent_inspections': Inspection.objects.all().order_by('-inspection_date')[:5],
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
    
    # Get all inspections
    inspections = Inspection.objects.all().order_by('-inspection_date')
    
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
    
    # Get the inspection by id
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

@login_required(login_url='main:login')
def configuration(request):
    """System configuration view with all 5 features"""
    
    # Get current system configuration
    config = SystemConfiguration.get_config()
    
    # Initialize forms
    config_form = SystemConfigurationForm(instance=config)
    user_creation_form = CustomUserCreationForm()
    password_change_form = CustomPasswordChangeForm(user=request.user)
    
    # Handle form submissions
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        
        if form_type == 'system_config':
            config_form = SystemConfigurationForm(request.POST, instance=config)
            if config_form.is_valid():
                config_obj = config_form.save(commit=False)
                config_obj.updated_by = request.user
                config_obj.save()
                messages.success(request, 'Configuración del sistema actualizada exitosamente.')
                return redirect('main:configuration')
        
        elif form_type == 'create_user':
            user_creation_form = CustomUserCreationForm(request.POST)
            if user_creation_form.is_valid():
                user_creation_form.save()
                messages.success(request, 'Usuario creado exitosamente.')
                return redirect('main:configuration')
        
        elif form_type == 'change_password':
            password_change_form = CustomPasswordChangeForm(user=request.user, data=request.POST)
            if password_change_form.is_valid():
                password_change_form.save()
                update_session_auth_hash(request, password_change_form.user)
                messages.success(request, 'Contraseña actualizada exitosamente.')
                return redirect('main:configuration')
    
    # Get all users for display
    users = User.objects.all().order_by('-date_joined')
    
    context = {
        'title': 'Configuración del Sistema',
        'description': 'Configuración de sistema, usuarios y dispositivos',
        'config_form': config_form,
        'user_creation_form': user_creation_form,
        'password_change_form': password_change_form,
        'users': users,
        'current_config': config,
    }
    
    return render(request, 'main/configuration.html', context)
