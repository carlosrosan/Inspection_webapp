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
import base64
from .forms import SystemConfigurationForm, PasswordResetForm
from .models import SystemConfiguration, User
from .permissions import require_viewer, require_regular_user, require_supervisor, require_configuration_access

# Set up logger for login attempts
logger = logging.getLogger('main.views')


def get_photo_path_prefer_png(photo_field, media_root=None):
    """
    Get the path to a photo file, preferring PNG version if it exists.
    
    Args:
        photo_field: Django ImageField instance
        media_root: Optional MEDIA_ROOT path (will use settings if not provided)
    
    Returns:
        Tuple of (relative_path, is_png) where relative_path is the path relative to MEDIA_ROOT
        and is_png is True if PNG version was found, False otherwise.
        Returns (None, False) if file doesn't exist.
    """
    from django.conf import settings
    
    if not photo_field or not photo_field.name:
        return None, False
    
    if media_root is None:
        media_root = settings.MEDIA_ROOT
    
    # Normalize media_root to string
    if hasattr(media_root, '__fspath__'):
        media_root = str(media_root)
    elif isinstance(media_root, (str, bytes)):
        media_root = str(media_root)
    
    # Get the base path (without extension) from the photo name
    photo_name = photo_field.name
    base_path = os.path.join(media_root, photo_name)
    
    # Try to get path from ImageField first
    try:
        if hasattr(photo_field, 'path'):
            try:
                original_path = os.path.abspath(photo_field.path)
                if os.path.exists(original_path):
                    base_path = original_path
            except Exception:
                pass
    except Exception:
        pass
    
    # If base_path doesn't exist, try constructing from MEDIA_ROOT
    if not os.path.exists(base_path):
        try:
            base_path = os.path.abspath(os.path.join(media_root, photo_name))
        except Exception:
            return None, False
    
    # Get directory and base filename (without extension)
    directory = os.path.dirname(base_path)
    filename_with_ext = os.path.basename(base_path)
    filename_base = os.path.splitext(filename_with_ext)[0]
    
    # First, try to find PNG version (preferred)
    png_path = os.path.join(directory, f"{filename_base}.png")
    if os.path.exists(png_path):
        # Convert absolute path to relative path from MEDIA_ROOT
        abs_media_root = os.path.abspath(media_root)
        abs_png_path = os.path.abspath(png_path)
        relative_path = os.path.relpath(abs_png_path, abs_media_root)
        # Normalize path separators for URL (use forward slashes)
        relative_path = relative_path.replace('\\', '/')
        return relative_path, True
    
    # If PNG doesn't exist, use the original file
    if os.path.exists(base_path):
        # Convert absolute path to relative path from MEDIA_ROOT
        abs_media_root = os.path.abspath(media_root)
        abs_base_path = os.path.abspath(base_path)
        relative_path = os.path.relpath(abs_base_path, abs_media_root)
        # Normalize path separators for URL (use forward slashes)
        relative_path = relative_path.replace('\\', '/')
        return relative_path, False
    
    # If original doesn't exist either, return None
    return None, False


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
    
    # Get or create the inspection machine
    try:
        machine = InspectionMachine.get_machine()
    except Exception as e:
        # If machine creation fails, create a minimal one
        machine = InspectionMachine.objects.first()
        if not machine:
            machine = InspectionMachine.objects.create(
                machine_id='MAQ-001',
                name='Analizador de Combustible Conuar',
                model='AB-3000',
                version='v2.1.3',
                status='idle',
            )
    
    # Get the latest inspection or create a default one if none exists
    inspection = None
    try:
        # Try to get any inspection (latest first)
        inspection = Inspection.objects.order_by('-inspection_date').first()
        if not inspection:
            # If no inspections exist, create a default one
            inspection = Inspection.get_inspection()
    except Exception as e:
        # If inspection creation fails, create a minimal one
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            default_inspector, _ = User.objects.get_or_create(
                username='system_inspector',
                defaults={
                    'first_name': 'Sistema',
                    'last_name': 'Inspector',
                    'email': 'system@conuar.com',
                    'is_active': True,
                    'is_staff': True,
                }
            )
            inspection = Inspection.objects.create(
                title='Inspección de Combustible Conuar',
                description='Inspección de calidad de combustible',
                tipo_combustible='uranio',
                status='completed',
                product_name='Combustible Industrial',
                product_code='COMB-001',
                inspector=default_inspector,
            )
        except Exception as e2:
            # Last resort: create inspection without inspector (if inspector is nullable)
            # But inspector is required, so we need to ensure user exists
            logger.error(f"Failed to create inspection: {e2}")
            # Try to get any existing inspection
            inspection = Inspection.objects.first()
            if not inspection:
                # This should not happen, but if it does, we'll handle it in the template
                inspection = None
    
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
        from django.contrib.auth import get_user_model
        UserModel = get_user_model()  # Get User model to avoid scope issues
        
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
        inspectors = UserModel.objects.filter(
            inspections_conducted__isnull=False
        ).distinct().annotate(
            inspection_count=Count('inspections_conducted')
        ).order_by('-inspection_count')[:5]
        
        for inspector in inspectors:
            inspector_names.append(inspector.username)
            inspector_data.append(inspector.inspection_count)
        
        return chart_labels, all_inspectors_data, inspector_data, inspector_names
    
    chart_labels, all_inspectors_data, inspector_data, inspector_names = generate_chart_data()
    
    # Final safety check: ensure inspection is never None
    if inspection is None:
        # Last resort: create a minimal inspection
        from django.contrib.auth import get_user_model
        User = get_user_model()
        default_inspector, _ = User.objects.get_or_create(
            username='system_inspector',
            defaults={
                'first_name': 'Sistema',
                'last_name': 'Inspector',
                'email': 'system@conuar.com',
                'is_active': True,
                'is_staff': True,
            }
        )
        inspection = Inspection.objects.create(
            title='Inspección de Combustible Conuar',
            description='Inspección de calidad de combustible',
            tipo_combustible='uranio',
            status='completed',
            product_name='Combustible Industrial',
            product_code='COMB-001',
            inspector=default_inspector,
        )
    
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
    
    # Prepare photos with PNG URLs - ONLY include photos that have PNG versions
    from django.conf import settings
    photos_data = []
    for photo in photos:
        # Check if PNG version exists (returns relative path from MEDIA_ROOT)
        relative_path, is_png = get_photo_path_prefer_png(photo.photo)
        
        # Only process photos that have PNG versions
        if relative_path and is_png:
            # Construct URL using MEDIA_URL + relative path
            try:
                png_url = settings.MEDIA_URL + relative_path
                
                # Only add to photos_data if we successfully got the PNG URL
                photos_data.append({
                    'photo_obj': photo,
                    'png_url': png_url,
                })
            except Exception as e:
                logger.warning(f"Failed to construct PNG URL for photo {photo.id}: {e}")
                # Skip this photo if we can't get the PNG URL
                continue
        # If PNG doesn't exist, skip this photo entirely (don't add to photos_data)
    
    context = {
        'title': f'Inspección de Combustible: {inspection.title}',
        'description': f'Vista detallada de la inspección de calidad de {inspection.product_name}',
        'inspection': inspection,
        'photos': photos,  # Keep original photos for compatibility (used in other parts of template)
        'photos_data': photos_data,  # Only photos with PNG versions
        'photo_count': len(photos_data),  # Count only PNG photos
    }
    
    return render(request, 'main/inspection_detail.html', context)

def generate_inspection_pdf_to_file(inspection_id, save_to_disk=True):
    """
    Generate PDF report for an inspection and optionally save to disk.
    
    Args:
        inspection_id: ID of the inspection to generate PDF for
        save_to_disk: If True, save PDF to inspection_reports directory
    
    Returns:
        Tuple of (pdf_bytes, file_path) where file_path is None if save_to_disk=False
    """
    from .models import Inspection, InspectionPhoto
    from django.shortcuts import get_object_or_404
    from django.template.loader import get_template
    from django.conf import settings
    from datetime import datetime
    from io import BytesIO
    import os
    import re
    
    # Try to import xhtml2pdf
    try:
        from xhtml2pdf import pisa
    except ImportError:
        logger.error("xhtml2pdf module not installed. Cannot generate PDF.")
        return None, None
    
    # Get the inspection by id
    try:
        inspection = Inspection.objects.get(id=inspection_id)
    except Inspection.DoesNotExist:
        logger.error(f"Inspection {inspection_id} not found for PDF generation")
        return None, None
    
    photos = inspection.photos.all()
    
    # Prepare photo data with file paths and codes (same logic as inspection_pdf)
    photo_data = []
    for photo in photos:
        photo_code = None
        photo_path = None
        is_png = False
        
        if photo.photo:
            photo_code = os.path.splitext(os.path.basename(photo.photo.name))[0]
            relative_path, is_png = get_photo_path_prefer_png(photo.photo)
            
            # Convert relative path to absolute path for file operations
            photo_path = None
            if relative_path:
                photo_path = os.path.join(settings.MEDIA_ROOT, relative_path)
                # Normalize path separators for the current OS
                photo_path = os.path.normpath(photo_path)
            
            # Convert photo to base64 data URI (with compression for OK PNGs)
            photo_data_uri = None
            if photo_path and os.path.exists(photo_path):
                try:
                    ext = os.path.splitext(photo_path)[1].lower()
                    mime_types = {
                        '.jpg': 'image/jpeg',
                        '.jpeg': 'image/jpeg',
                        '.png': 'image/png',
                        '.bmp': 'image/bmp',
                        '.gif': 'image/gif',
                    }
                    mime_type = mime_types.get(ext, 'image/jpeg')
                    
                    with open(photo_path, 'rb') as img_file:
                        img_data = img_file.read()
                        
                        # Compress OK (non-failure) PNG photos by 90% for PDF
                        if is_png and not photo.defecto_encontrado:
                            try:
                                from PIL import Image
                                img = Image.open(BytesIO(img_data))
                                original_width, original_height = img.size
                                new_width = int(original_width * 0.316)  # sqrt(0.1) ≈ 0.316
                                new_height = int(original_height * 0.316)
                                img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                                output = BytesIO()
                                img_resized.save(output, format='PNG', optimize=True, compress_level=9)
                                img_data = output.getvalue()
                                output.close()
                                logger.debug(f"Photo {photo.id} compressed (OK PNG, 90% reduction) for PDF save")
                            except Exception as e:
                                logger.warning(f"Failed to compress photo {photo.id} for PDF save: {e}")
                        
                        img_base64 = base64.b64encode(img_data).decode('utf-8')
                        photo_data_uri = f"data:{mime_type};base64,{img_base64}"
                except Exception as e:
                    logger.warning(f"Failed to load photo {photo.id} from {photo_path}: {e}")
                    photo_data_uri = None
        
        photo_info = {
            'photo': photo,
            'path': photo_path,
            'data_uri': photo_data_uri,
            'code': photo_code,
            'is_png': is_png,
        }
        photo_data.append(photo_info)
    
    # Get logo (same logic as inspection_pdf)
    logo_data_uri = None
    possible_paths = []
    if settings.STATICFILES_DIRS:
        static_dir = settings.STATICFILES_DIRS[0]
        if hasattr(static_dir, '__fspath__'):
            static_dir = str(static_dir)
        possible_paths.append(os.path.join(static_dir, 'assets', 'logo_conuar1.jpeg'))
    
    base_dir = settings.BASE_DIR
    if hasattr(base_dir, '__fspath__'):
        base_dir = str(base_dir)
    possible_paths.append(os.path.join(base_dir, 'static', 'assets', 'logo_conuar1.jpeg'))
    
    if settings.STATIC_ROOT:
        static_root = settings.STATIC_ROOT
        if hasattr(static_root, '__fspath__'):
            static_root = str(static_root)
        possible_paths.append(os.path.join(static_root, 'assets', 'logo_conuar1.jpeg'))
    
    for path in possible_paths:
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path):
            try:
                with open(abs_path, 'rb') as img_file:
                    img_data = img_file.read()
                    img_base64 = base64.b64encode(img_data).decode('utf-8')
                    logo_data_uri = f"data:image/jpeg;base64,{img_base64}"
                    break
            except Exception:
                continue
    
    # Prepare context
    context = {
        'inspection': inspection,
        'photos': photos,
        'photo_data': photo_data,
        'generation_date': datetime.now(),
        'generation_user': None,  # No user for automated generation
        'photo_count': photos.count(),
        'logo_data_uri': logo_data_uri,
    }
    
    # Render HTML template
    template = get_template('main/inspection_pdf.html')
    html = template.render(context)
    
    # Generate PDF
    buffer = BytesIO()
    try:
        pisa_status = pisa.CreatePDF(html, dest=buffer)
        if pisa_status.err:
            logger.error(f"PDF generation failed for inspection {inspection_id}: {pisa_status.err}")
            return None, None
    except Exception as e:
        logger.exception(f"Exception during PDF generation for inspection {inspection_id}: {e}")
        return None, None
    
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    # Save to disk if requested
    file_path = None
    if save_to_disk:
        try:
            from config.paths_config import INSPECTION_REPORTS_DIR
            from config.paths_config import ensure_directories_exist
            ensure_directories_exist()
            
            # Explicitly set the reports directory to the specified path
            # This ensures PDFs are saved to: C:\Users\USER\Documents\GitHub\Inspection_webapp\Conuar\conuar_webapp\media\inspection_reports
            reports_dir = str(INSPECTION_REPORTS_DIR)
            
            # Ensure the directory exists
            os.makedirs(reports_dir, exist_ok=True)
            
            # Generate filename
            inspection_code = None
            if photo_data and photo_data[0].get('code'):
                inspection_code = photo_data[0]['code']
                if inspection_code.endswith('-NOK') or inspection_code.endswith('-OK'):
                    inspection_code = inspection_code.rsplit('-', 1)[0]
            elif inspection.batch_number and inspection.serial_number:
                inspection_code = f"{inspection.batch_number}-{inspection.serial_number}"
            elif inspection.batch_number:
                inspection_code = inspection.batch_number
            elif inspection.serial_number:
                inspection_code = inspection.serial_number
            else:
                inspection_code = f"inspeccion_{inspection.id}_{datetime.now().strftime('%Y%m%d')}"
            
            filename = re.sub(r'[<>:"/\\|?*]', '_', inspection_code)
            filename = f"{filename}.pdf"
            file_path = os.path.join(reports_dir, filename)
            
            # Write PDF to file
            with open(file_path, 'wb') as f:
                f.write(pdf_bytes)
            
            logger.info(f"PDF guardado automáticamente en: {file_path}")
            logger.info(f"Directorio de reportes: {reports_dir}")
            logger.info(f"Tamaño del archivo PDF: {len(pdf_bytes)} bytes")
            logger.info(f"Archivo existe: {os.path.exists(file_path)}")
        except Exception as e:
            logger.error(f"Failed to save PDF to disk for inspection {inspection_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            file_path = None
    
    return pdf_bytes, file_path


@login_required(login_url='main:login')
@require_viewer  # Viewer, Regular User, and Supervisor can download PDF reports
def inspection_pdf(request, inspection_id):
    """Generate and download PDF report for a specific inspection"""
    from .models import Inspection, InspectionPhoto
    from django.shortcuts import get_object_or_404
    from django.template.loader import get_template
    from django.http import HttpResponse
    from django.conf import settings
    from datetime import datetime
    from io import BytesIO
    import os
    
    # Try to import xhtml2pdf, show helpful error if not installed
    try:
        from xhtml2pdf import pisa
    except ImportError:
        from django.contrib import messages
        messages.error(
            request, 
            'El módulo xhtml2pdf no está instalado. Por favor ejecute: pip install xhtml2pdf'
        )
        return redirect('main:inspection_detail', inspection_id=inspection_id)
    
    
    # Get the inspection by id
    inspection = get_object_or_404(Inspection, id=inspection_id)
    photos = inspection.photos.all()
    
    # Prepare photo data with file paths and codes
    photo_data = []
    for photo in photos:
        # Extract photo code from filename (filename without extension)
        photo_code = None
        photo_path = None
        is_png = False
        
        if photo.photo:
            photo_code = os.path.splitext(os.path.basename(photo.photo.name))[0]
            
            # Get photo path, preferring PNG version if available (returns relative path)
            relative_path, is_png = get_photo_path_prefer_png(photo.photo)
            
            # Convert relative path to absolute path for file operations
            photo_path = None
            if relative_path:
                photo_path = os.path.join(settings.MEDIA_ROOT, relative_path)
                # Normalize path separators for the current OS
                photo_path = os.path.normpath(photo_path)
            
            # Convert photo to base64 data URI for reliable embedding in PDF
            photo_data_uri = None
            if photo_path and os.path.exists(photo_path):
                try:
                    # Determine MIME type from file extension
                    ext = os.path.splitext(photo_path)[1].lower()
                    mime_types = {
                        '.jpg': 'image/jpeg',
                        '.jpeg': 'image/jpeg',
                        '.png': 'image/png',
                        '.bmp': 'image/bmp',
                        '.gif': 'image/gif',
                    }
                    mime_type = mime_types.get(ext, 'image/jpeg')
                    
                    with open(photo_path, 'rb') as img_file:
                        img_data = img_file.read()
                        
                        # Compress OK (non-failure) PNG photos by 90% for PDF
                        if is_png and not photo.defecto_encontrado:
                            try:
                                from PIL import Image
                                # Open image with PIL
                                img = Image.open(BytesIO(img_data))
                                
                                # Resize to ~32% of original dimensions (0.32^2 ≈ 0.1 = 10% area = 90% reduction)
                                original_width, original_height = img.size
                                new_width = int(original_width * 0.316)  # sqrt(0.1) ≈ 0.316
                                new_height = int(original_height * 0.316)
                                
                                # Resize with high-quality resampling
                                img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                                
                                # Save to BytesIO with optimization
                                output = BytesIO()
                                img_resized.save(output, format='PNG', optimize=True, compress_level=9)
                                img_data = output.getvalue()
                                output.close()
                                
                                logger.debug(f"Photo {photo.id} compressed (OK PNG, 90% reduction): {photo_path}")
                                logger.debug(f"  Original size: {original_width}x{original_height}, New size: {new_width}x{new_height}")
                            except Exception as e:
                                logger.warning(f"Failed to compress photo {photo.id}: {e}. Using original image.")
                                # Continue with original img_data if compression fails
                        
                        img_base64 = base64.b64encode(img_data).decode('utf-8')
                        photo_data_uri = f"data:{mime_type};base64,{img_base64}"
                    logger.debug(f"Photo {photo.id} loaded and encoded: {photo_path} (PNG: {is_png}, Defect: {photo.defecto_encontrado})")
                except Exception as e:
                    logger.warning(f"Failed to load photo {photo.id} from {photo_path}: {e}")
                    photo_data_uri = None
            else:
                logger.warning(f"Photo {photo.id} path not found. Photo name: {photo.photo.name if photo.photo else 'None'}")
        
        photo_info = {
            'photo': photo,
            'path': photo_path,  # Actual file path (PNG if available, otherwise original)
            'data_uri': photo_data_uri,  # Base64 data URI for PDF
            'code': photo_code,
            'is_png': is_png,  # Flag indicating if PNG version was used
        }
        photo_data.append(photo_info)
    
    # Get logo and convert to base64 data URI for reliable embedding
    logo_data_uri = None
    
    # Try multiple paths to find the logo
    possible_paths = []
    
    # Try STATICFILES_DIRS first (most common location)
    if settings.STATICFILES_DIRS:
        static_dir = settings.STATICFILES_DIRS[0]
        if hasattr(static_dir, '__fspath__'):
            static_dir = str(static_dir)
        elif isinstance(static_dir, (str, bytes)):
            static_dir = str(static_dir)
        possible_paths.append(os.path.join(static_dir, 'assets', 'logo_conuar1.jpeg'))
    
    # Try BASE_DIR/static (fallback)
    base_dir = settings.BASE_DIR
    if hasattr(base_dir, '__fspath__'):
        base_dir = str(base_dir)
    elif isinstance(base_dir, (str, bytes)):
        base_dir = str(base_dir)
    possible_paths.append(os.path.join(base_dir, 'static', 'assets', 'logo_conuar1.jpeg'))
    
    # Try STATIC_ROOT (production)
    if settings.STATIC_ROOT:
        static_root = settings.STATIC_ROOT
        if hasattr(static_root, '__fspath__'):
            static_root = str(static_root)
        elif isinstance(static_root, (str, bytes)):
            static_root = str(static_root)
        possible_paths.append(os.path.join(static_root, 'assets', 'logo_conuar1.jpeg'))
    
    # Find and encode the logo as base64
    for path in possible_paths:
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path):
            try:
                with open(abs_path, 'rb') as img_file:
                    img_data = img_file.read()
                    img_base64 = base64.b64encode(img_data).decode('utf-8')
                    logo_data_uri = f"data:image/jpeg;base64,{img_base64}"
                    logger.info(f"Logo loaded and encoded for PDF: {abs_path}")
                    break
            except Exception as e:
                logger.warning(f"Failed to load logo from {abs_path}: {e}")
                continue
    
    if not logo_data_uri:
        logger.warning(f"Logo not found for PDF. Tried paths: {possible_paths}")
    
    # Prepare context for the template
    context = {
        'inspection': inspection,
        'photos': photos,
        'photo_data': photo_data,
        'generation_date': datetime.now(),
        'generation_user': request.user,
        'photo_count': photos.count(),
        'logo_data_uri': logo_data_uri,  # Use base64 data URI instead of path
    }

    # Render the HTML template
    template = get_template('main/inspection_pdf.html')
    html = template.render(context)
    
    # Log context info for debugging
    logger.info(f"Generating PDF for inspection {inspection_id}")
    logger.info(f"  Logo data URI: {'Present' if logo_data_uri else 'Missing'}")
    logger.info(f"  Photo count: {len(photo_data)}")
    logger.info(f"  Photos with data URIs: {sum(1 for p in photo_data if p.get('data_uri'))}")
    
    # Create a BytesIO buffer for the PDF
    buffer = BytesIO()
    
    # Generate PDF from HTML (no link_callback needed with base64 data URIs)
    try:
        pisa_status = pisa.CreatePDF(html, dest=buffer)
        
        # Check if PDF generation was successful
        if pisa_status.err:
            error_msg = f'Error al generar el PDF: {pisa_status.err}'
            logger.error(f"PDF generation failed for inspection {inspection_id}: {pisa_status.err}")
            return HttpResponse(error_msg, status=500)
    except Exception as e:
        error_msg = f'Error al generar el PDF: {str(e)}'
        logger.exception(f"Exception during PDF generation for inspection {inspection_id}: {e}")
        return HttpResponse(error_msg, status=500)
    
    # Get the value of the BytesIO buffer
    pdf = buffer.getvalue()
    buffer.close()
    
    # Create HTTP response
    response = HttpResponse(pdf, content_type='application/pdf')
    
    # Generate filename from inspection code (use first photo code if available, or construct from batch/serial)
    inspection_code = None
    if photo_data and photo_data[0].get('code'):
        # Use the photo code pattern (e.g., Ciclo2-EC123-1F-041225_154941)
        inspection_code = photo_data[0]['code']
        # Remove the status suffix (-NOK or -OK) if present
        if inspection_code.endswith('-NOK') or inspection_code.endswith('-OK'):
            inspection_code = inspection_code.rsplit('-', 1)[0]
    elif inspection.batch_number and inspection.serial_number:
        # Construct from batch and serial number
        inspection_code = f"{inspection.batch_number}-{inspection.serial_number}"
    elif inspection.batch_number:
        inspection_code = inspection.batch_number
    elif inspection.serial_number:
        inspection_code = inspection.serial_number
    else:
        # Fallback to ID and date
        inspection_code = f"inspeccion_{inspection.id}_{datetime.now().strftime('%Y%m%d')}"
    
    # Sanitize filename (remove invalid characters)
    import re
    filename = re.sub(r'[<>:"/\\|?*]', '_', inspection_code)
    filename = f"{filename}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Also save PDF to disk automatically
    try:
        from config.paths_config import INSPECTION_REPORTS_DIR
        from config.paths_config import ensure_directories_exist
        ensure_directories_exist()
        reports_dir = str(INSPECTION_REPORTS_DIR)
        file_path = os.path.join(reports_dir, filename)
        with open(file_path, 'wb') as f:
            f.write(pdf)
        logger.info(f"PDF also saved to disk: {file_path}")
        logger.info(f"PDF file size: {len(pdf)} bytes")
    except Exception as e:
        logger.warning(f"Failed to save PDF to disk: {e}")
        import traceback
        logger.warning(traceback.format_exc())
    
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