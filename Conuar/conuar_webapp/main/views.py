from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.db import models

def home(request):
    """Home page view"""
    context = {
        'title': 'Bienvenido a la Aplicación Web de Reportes para Conuar',
        'description': 'Un sitio web moderno basado en Django construido por ArByte/Ingelearn.',
        'features': [
            'Diseño Responsivo',
            'UI/UX Moderna',
            'Rendimiento Rápido',
            'Optimizado para SEO'
        ]
    }
    return render(request, 'main/home.html', context)

def about(request):
    """About page view"""
    context = {
        'title': 'Acerca de Nosotros',
        'description': 'Conoce más sobre nuestra empresa y misión.',
        'company_info': {
            'name': 'ArByte/Ingelearn',
            'founded': '2018',
            'mission': 'Crear experiencias de automatización.'
        }
    }
    return render(request, 'main/about.html', context)

def contact(request):
    """Contact page view"""
    context = {
        'title': 'Contáctanos',
        'description': 'Ponte en contacto con nuestro equipo.',
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
        'title': 'Iniciar Sesión - Aplicación Web Conuar',
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
    """User dashboard view"""
    context = {
        'title': 'Panel de Control',
        'description': 'Bienvenido a tu panel de control personal.',
        'user': request.user,
        'stats': {
            'projects': 5,
            'messages': 12,
            'notifications': 3
        }
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
        'title': 'Lista de Inspecciones',
        'description': 'Ver todas las inspecciones de productos',
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
        'title': f'Inspección: {inspection.title}',
        'description': f'Vista detallada de la inspección de {inspection.product_name}',
        'inspection': inspection,
        'photos': photos,
        'photo_count': photos.count(),
    }
    
    return render(request, 'main/inspection_detail.html', context)
