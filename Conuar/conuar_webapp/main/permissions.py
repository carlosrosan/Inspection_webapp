"""
Permission system for the Inspection Webapp using Django's built-in permissions.
Defines 3 roles:
1. Supervisor (is_superuser=True): Can do anything
2. Regular User (is_staff=True, is_superuser=False): Can see config, use admin, but not create users
3. Viewer (is_active=True, is_staff=False, is_superuser=False): Can see everything except config and admin
"""

from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def require_permission(permission_type):
    """
    Decorator to require specific permissions using Django's built-in fields
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, 'Debes iniciar sesión para acceder a esta página.')
                return redirect('main:login')
            
            # Permission mapping using Django's built-in fields
            permissions = {
                # Viewer permissions (is_active=True)
                'view_dashboard': lambda user: user.is_active,
                'view_inspections': lambda user: user.is_active,
                'view_inspection_detail': lambda user: user.is_active,
                'view_about': lambda user: user.is_active,
                
                # Regular User permissions (is_staff=True)
                'view_configuration': lambda user: user.is_staff,
                'access_admin': lambda user: user.is_staff,
                'view_users': lambda user: user.is_staff,
                
                # Supervisor permissions (is_superuser=True)
                'create_users': lambda user: user.is_superuser,
                'modify_users': lambda user: user.is_superuser,
                'manage_system': lambda user: user.is_superuser,
                'full_access': lambda user: user.is_superuser,
            }
            
            if permission_type not in permissions:
                messages.error(request, 'Permiso no definido.')
                return redirect('main:dashboard')
            
            if not permissions[permission_type](request.user):
                messages.error(request, 'No tienes permisos para acceder a esta función.')
                return redirect('main:dashboard')
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# Convenience decorators for the 3 roles
def require_viewer(view_func):
    """Require at least viewer access (is_active=True)"""
    return require_permission('view_dashboard')(view_func)


def require_regular_user(view_func):
    """Require regular user access (is_staff=True)"""
    return require_permission('view_configuration')(view_func)


def require_supervisor(view_func):
    """Require supervisor access (is_superuser=True)"""
    return require_permission('full_access')(view_func)


# Specific permission decorators
def require_configuration_access(view_func):
    """Require access to configuration page (staff or superuser)"""
    return require_permission('view_configuration')(view_func)


def require_admin_access(view_func):
    """Require admin panel access (staff or superuser)"""
    return require_permission('access_admin')(view_func)


def require_user_management(view_func):
    """Require user creation/modification (superuser only)"""
    return require_permission('create_users')(view_func)
