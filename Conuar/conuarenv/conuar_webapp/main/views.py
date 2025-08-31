from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.db import models

def home(request):
    """Home page view"""
    context = {
        'title': 'Welcome to Conuar WebApp',
        'description': 'A modern Django-based website built with love and care.',
        'features': [
            'Responsive Design',
            'Modern UI/UX',
            'Fast Performance',
            'SEO Optimized'
        ]
    }
    return render(request, 'main/home.html', context)

def about(request):
    """About page view"""
    context = {
        'title': 'About Us',
        'description': 'Learn more about our company and mission.',
        'company_info': {
            'name': 'Conuar',
            'founded': '2024',
            'mission': 'To create amazing web experiences'
        }
    }
    return render(request, 'main/about.html', context)

def contact(request):
    """Contact page view"""
    context = {
        'title': 'Contact Us',
        'description': 'Get in touch with our team.',
        'contact_info': {
            'email': 'info@conuar.com',
            'phone': '+1 (555) 123-4567',
            'address': '123 Web Street, Digital City, DC 12345'
        }
    }
    return render(request, 'main/contact.html', context)

def services(request):
    """Services page view"""
    context = {
        'title': 'Our Services',
        'description': 'Discover what we can do for you.',
        'services': [
            {
                'name': 'Web Development',
                'description': 'Custom websites and web applications',
                'icon': 'fas fa-code'
            },
            {
                'name': 'Mobile Apps',
                'description': 'iOS and Android development',
                'icon': 'fas fa-mobile-alt'
            },
            {
                'name': 'Cloud Solutions',
                'description': 'Scalable cloud infrastructure',
                'icon': 'fas fa-cloud'
            },
            {
                'name': 'Consulting',
                'description': 'Expert technical guidance',
                'icon': 'fas fa-users'
            }
        ]
    }
    return render(request, 'main/services.html', context)

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
            messages.success(request, f'Welcome back, {user.username}!')
            # Redirect to the page they were trying to access, or home
            next_url = request.GET.get('next', 'main:home')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password.')
    
    context = {
        'title': 'Login - Conuar WebApp',
        'next': request.GET.get('next', '')
    }
    return render(request, 'main/login.html', context)

def logout_view(request):
    """User logout view"""
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('main:home')

# Protected views that require authentication
@login_required(login_url='main:login')
def protected_home(request):
    """Protected home page view"""
    context = {
        'title': 'Welcome to Conuar WebApp (Protected)',
        'description': 'This is a protected area of our website.',
        'user': request.user,
        'features': [
            'Secure Access',
            'User Dashboard',
            'Personalized Content',
            'Premium Features'
        ]
    }
    return render(request, 'main/protected_home.html', context)

@login_required(login_url='main:login')
def dashboard(request):
    """User dashboard view"""
    context = {
        'title': 'Dashboard',
        'description': 'Welcome to your personal dashboard.',
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
        'title': 'Inspection List',
        'description': 'View all product inspections',
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
        'title': f'Inspection: {inspection.title}',
        'description': f'Detailed view of {inspection.product_name} inspection',
        'inspection': inspection,
        'photos': photos,
        'photo_count': photos.count(),
    }
    
    return render(request, 'main/inspection_detail.html', context)
