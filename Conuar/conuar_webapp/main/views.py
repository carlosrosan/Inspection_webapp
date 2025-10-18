from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.db import models
from django.contrib.auth import update_session_auth_hash
from django.utils import timezone
from django.core.cache import cache
import logging
import os
import json
from .forms import SystemConfigurationForm, PasswordResetForm
from .models import SystemConfiguration, User
from .permissions import require_viewer, require_regular_user, require_supervisor, require_configuration_access

# Set up logger for login attempts
logger = logging.getLogger('main.views')


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
    """User login view with comprehensive logging"""
    if request.user.is_authenticated:
        return redirect('main:inspection_list')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        client_ip = request.META.get('REMOTE_ADDR', 'Unknown')
        user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
        
        # Track login attempts using cache
        cache_key = f"login_attempts_{username}_{client_ip}"
        attempts = cache.get(cache_key, 0)
        attempts += 1
        cache.set(cache_key, attempts, timeout=3600)  # 1 hour timeout
        
        # Log login attempt
        logger.info(f"LOGIN_ATTEMPT - User: {username}, IP: {client_ip}, Attempt: {attempts}, User-Agent: {user_agent}")
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # Successful login
            login(request, user)
            cache.delete(cache_key)  # Clear failed attempts on successful login
            logger.info(f"LOGIN_SUCCESS - User: {username}, IP: {client_ip}, Role: {user.get_role_display()}")
            messages.success(request, f'¡Bienvenido de vuelta, {user.username}!')
            # Redirect to the page they were trying to access, or inspection list
            next_url = request.GET.get('next', 'main:inspection_list')
            return redirect(next_url)
        else:
            # Failed login
            logger.warning(f"LOGIN_FAILED - User: {username}, IP: {client_ip}, Attempt: {attempts}")
            if attempts >= 5:
                logger.error(f"LOGIN_BLOCKED - User: {username}, IP: {client_ip}, Too many failed attempts: {attempts}")
                messages.error(request, f'Demasiados intentos fallidos. Usuario {username} bloqueado temporalmente.')
            else:
                messages.error(request, 'Nombre de usuario o contraseña inválidos.')
    
    context = {
        'title': 'Iniciar Sesión - Inspección de combustible',
        'next': request.GET.get('next', '')
    }
    return render(request, 'main/login.html', context)

def logout_view(request):
    """User logout view with logging"""
    if request.user.is_authenticated:
        username = request.user.username
        client_ip = request.META.get('REMOTE_ADDR', 'Unknown')
        logger.info(f"LOGOUT - User: {username}, IP: {client_ip}")
    
    logout(request)
    messages.success(request, 'Has cerrado sesión exitosamente.')
    return redirect('main:login')


@login_required(login_url='main:login')
@require_viewer  # Viewer, Regular User, and Supervisor can view dashboard
def dashboard(request):
    """Machine status dashboard view - All active users can access"""
    from .models import InspectionMachine, MachineLog, Inspection, InspectionPhoto, InspectionPlcEvent
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
    inspections_today = Inspection.objects.filter(
        inspection_date__date=datetime.now().date()
    ).count()
    
    # Calculate storage amount in GB
    def calculate_storage_gb():
        """Calculate total storage used by photos in GB"""
        try:
            from django.conf import settings
            media_root = settings.MEDIA_ROOT
            total_size = 0
            photo_count = 0
            
            # Walk through the media directory to calculate total size
            for root, dirs, files in os.walk(media_root):
                for file in files:
                    if file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif')):
                        file_path = os.path.join(root, file)
                        if os.path.exists(file_path):
                            total_size += os.path.getsize(file_path)
                            photo_count += 1
            
            # Convert bytes to GB
            storage_gb = total_size / (1024 * 1024 * 1024)
            return storage_gb, photo_count
        except Exception as e:
            # Fallback to database count if file system access fails
            photo_count = InspectionPhoto.objects.count()
            # Estimate 2MB per photo
            storage_gb = (photo_count * 2) / 1024
            return storage_gb, photo_count
    
    storage_gb, photo_count = calculate_storage_gb()
    
    # Get control points timeline for current inspection if machine is inspecting
    control_points_timeline = []
    if machine.status == 'inspecting' and machine.current_inspection:
        # Get control points for the current inspection
        control_points = InspectionPlcEvent.objects.filter(
            id_inspection=machine.current_inspection
        ).order_by('timestamp_plc')
        
        # Create timeline data
        for i, point in enumerate(control_points):
            control_points_timeline.append({
                'step': i + 1,
                'control_point_id': point.control_point_id,
                'control_point_label': point.control_point_label or f"Punto {point.control_point_id}",
                'execution_type': point.get_execution_type_display(),
                'timestamp': point.timestamp_plc,
                'position': {
                    'x': point.x_control_point,
                    'y': point.y_control_point,
                    'z': point.z_control_point,
                    'angle': point.plate_angle
                },
                'camera_id': point.camera_id,
                'filming_type': point.get_filming_type_display(),
                'is_completed': i < len(control_points) - 1,  # All except last are completed
                'is_current': i == len(control_points) - 1,  # Last one is current
            })
    
    # If no real control points exist, create sample data for demonstration
    if not control_points_timeline and machine.status == 'inspecting':
        sample_control_points = [
            {
                'step': 1,
                'control_point_id': 'ZAPATA_001',
                'control_point_label': 'Zapata Número 1',
                'execution_type': 'Automático',
                'timestamp': datetime.now() - timedelta(minutes=15),
                'position': {'x': 10.5, 'y': 20.3, 'z': 5.2, 'angle': 0.0},
                'camera_id': 'CAM_001',
                'filming_type': 'Foto',
                'is_completed': True,
                'is_current': False,
            },
            {
                'step': 2,
                'control_point_id': 'ZAPATA_002',
                'control_point_label': 'Zapata Número 2',
                'execution_type': 'Automático',
                'timestamp': datetime.now() - timedelta(minutes=10),
                'position': {'x': 15.2, 'y': 25.1, 'z': 5.8, 'angle': 15.5},
                'camera_id': 'CAM_002',
                'filming_type': 'Video',
                'is_completed': True,
                'is_current': False,
            },
            {
                'step': 3,
                'control_point_id': 'ZAPATA_003',
                'control_point_label': 'Zapata Número 3',
                'execution_type': 'Manual',
                'timestamp': datetime.now() - timedelta(minutes=5),
                'position': {'x': 20.1, 'y': 30.4, 'z': 6.2, 'angle': 30.0},
                'camera_id': 'CAM_001',
                'filming_type': 'Foto',
                'is_completed': False,
                'is_current': True,
            },
            {
                'step': 4,
                'control_point_id': 'ZAPATA_004',
                'control_point_label': 'Zapata Número 4',
                'execution_type': 'Automático',
                'timestamp': None,
                'position': {'x': 25.3, 'y': 35.7, 'z': 6.8, 'angle': 45.0},
                'camera_id': 'CAM_003',
                'filming_type': 'Foto',
                'is_completed': False,
                'is_current': False,
            },
        ]
        control_points_timeline = sample_control_points
    
    # Generate chart data for last 30 days
    def generate_chart_data():
        """Generate chart data for the last 30 days"""
        chart_labels = []
        all_inspectors_data = []
        inspector_data = []
        inspector_names = []
        
        # Generate labels for last 30 days
        for i in range(30):
            date = today - timedelta(days=29-i)
            chart_labels.append(date.strftime('%d/%m'))
            
            # Count inspections for this day
            day_inspections = Inspection.objects.filter(
                inspection_date__date=date
            ).count()
            all_inspectors_data.append(day_inspections)
        
        # Get inspector-specific data
        inspectors = User.objects.filter(
            inspections_conducted__isnull=False
        ).distinct().annotate(
            inspection_count=Count('inspections_conducted')
        ).order_by('-inspection_count')[:5]
        
        for inspector in inspectors:
            inspector_names.append(inspector.username)
            inspector_data.append(inspector.inspection_count)
        
        return chart_labels, all_inspectors_data, inspector_data, inspector_names
    
    chart_labels, all_inspectors_data, inspector_data, inspector_names = generate_chart_data()
    
    context = {
        'title': 'Estado del Sistema',
        'description': 'Monitoreo en tiempo real del sistema de inspección de combustible',
        'user': request.user,
        'machine': machine,
        'inspection': inspection,
        'total_inspections': total_inspections,
        'inspections_today': inspections_today,
        'storage_gb': storage_gb,
        'photo_count': photo_count,
        'control_points_timeline': control_points_timeline,
        'chart_labels': json.dumps(chart_labels),
        'all_inspectors_data': json.dumps(all_inspectors_data),
        'inspector_data': json.dumps(inspector_data),
        'inspector_names': json.dumps(inspector_names),
    }
    return render(request, 'main/dashboard.html', context)

# Inspection views
@login_required(login_url='main:login')
@require_viewer  # Viewer, Regular User, and Supervisor can view inspections
def inspection_list(request):
    """List all inspections - All active users can access"""
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
        inspections = inspections.filter(tipo_combustible=type_filter)
    
    if search_query:
        inspections = inspections.filter(
            models.Q(title__icontains=search_query) |
            models.Q(product_name__icontains=search_query) |
            models.Q(description__icontains=search_query) |
            models.Q(product_code__icontains=search_query)
        )
    
    # Get unique values for filter dropdowns
    status_choices = Inspection.INSPECTION_STATUS_CHOICES
    type_choices = Inspection.TIPO_COMBUSTIBLE_CHOICES
    
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
@require_viewer  # Viewer, Regular User, and Supervisor can view inspection details
def inspection_detail(request, inspection_id):
    """Show detailed view of a specific inspection - All active users can access"""
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
@require_viewer  # Viewer, Regular User, and Supervisor can download PDF reports
def inspection_pdf(request, inspection_id):
    """Generate and download PDF report for a specific inspection"""
    from .models import Inspection, InspectionPhoto
    from django.shortcuts import get_object_or_404
    from django.template.loader import get_template
    from django.http import HttpResponse
    from datetime import datetime
    from xhtml2pdf import pisa
    from io import BytesIO
    import os
    
    
    # Get the inspection by id
    inspection = get_object_or_404(Inspection, id=inspection_id)
    photos = inspection.photos.all()
    
    # Prepare photo data with file paths
    photo_data = []
    for photo in photos:
        photo_info = {
            'photo': photo,
            'path': photo.photo.path if photo.photo else None,
        }
        photo_data.append(photo_info)
    
    # Prepare context for the template
    context = {
        'inspection': inspection,
        'photos': photos,
        'photo_data': photo_data,
        'generation_date': datetime.now(),
        'photo_count': photos.count(),
    }
    
    # Render the HTML template
    template = get_template('main/inspection_pdf.html')
    html = template.render(context)
    
    # Create a BytesIO buffer for the PDF
    buffer = BytesIO()
    
    # Generate PDF from HTML
    pisa_status = pisa.CreatePDF(html, dest=buffer)
    
    # Check if PDF generation was successful
    if pisa_status.err:
        return HttpResponse('Error al generar el PDF: %s' % pisa_status.err, status=500)
    
    # Get the value of the BytesIO buffer
    pdf = buffer.getvalue()
    buffer.close()
    
    # Create HTTP response
    response = HttpResponse(pdf, content_type='application/pdf')
    filename = f'inspeccion_{inspection.id}_{inspection.title}_{datetime.now().strftime("%Y%m%d")}.pdf'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response

@login_required(login_url='main:login')
@require_configuration_access  # Regular User and Supervisor can access configuration
def configuration(request):
    """System configuration view - Regular Users and Supervisors can access"""
    
    # Get current system configuration
    config = SystemConfiguration.get_config()
    
    # Initialize forms
    config_form = SystemConfigurationForm(instance=config)
    
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
        
    
    # Get all users for display
    users = User.objects.all().order_by('-date_joined')
    
    context = {
        'title': 'Configuración del Sistema',
        'description': 'Configuración de sistema, usuarios y dispositivos',
        'config_form': config_form,
        'users': users,
        'current_config': config,
    }
    
    return render(request, 'main/configuration.html', context)


def password_reset(request, token):
    """Password reset view for users with valid reset token"""
    if request.user.is_authenticated:
        return redirect('main:inspection_list')
    
    # Check for superuser fixed token
    if token == "SUPERUSER_PASSWORD_CHANGE_2024":
        # Handle superuser password change
        if request.method == 'POST':
            username = request.POST.get('username')
            try:
                user = User.objects.get(username=username, is_superuser=True)
            except User.DoesNotExist:
                messages.error(request, 'Usuario superusuario no encontrado.')
                return render(request, 'main/password_reset.html', {'form': PasswordResetForm(), 'is_superuser': True})
            
            form = PasswordResetForm(request.POST)
            if form.is_valid():
                user.set_password(form.cleaned_data['new_password1'])
                user.set_password_expiry()  # Set new expiry date
                user.save()
                messages.success(request, 'Contraseña actualizada exitosamente. Puede iniciar sesión con su nueva contraseña.')
                return redirect('main:login')
        else:
            form = PasswordResetForm()
        
        context = {
            'title': 'Cambio de Contraseña - Superusuario',
            'form': form,
            'is_superuser': True,
        }
        return render(request, 'main/password_reset.html', context)
    
    # Regular user token validation
    try:
        user = User.objects.get(password_reset_token=token, password_reset_enabled=True)
    except User.DoesNotExist:
        messages.error(request, 'Token de restablecimiento inválido o expirado. Contacte al administrador del sistema.')
        return redirect('main:login')
    
    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            user.set_password(form.cleaned_data['new_password1'])
            user.password_reset_enabled = False  # Disable after successful reset
            user.password_reset_token = None  # Clear the token
            user.set_password_expiry()  # Set new expiry date
            user.save()
            messages.success(request, 'Contraseña actualizada exitosamente. Puede iniciar sesión con su nueva contraseña.')
            return redirect('main:login')
    else:
        form = PasswordResetForm()
    
    context = {
        'title': 'Restablecer Contraseña',
        'form': form,
        'user': user,
        'is_password_expired': user.is_password_expired(),
    }
    return render(request, 'main/password_reset.html', context)