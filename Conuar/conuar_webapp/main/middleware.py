from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages


class PasswordExpiryMiddleware:
    """
    Middleware to check if user's password has expired and redirect to password change
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Skip password expiry check for certain paths
        exempt_paths = [
            '/login/',
            '/logout/',
            '/password-reset/',
            '/admin/',
            '/static/',
            '/media/',
        ]
        
        # Check if current path should be exempt
        current_path = request.path
        if any(current_path.startswith(path) for path in exempt_paths):
            return self.get_response(request)
        
        # Check if user is authenticated and password is expired
        if request.user.is_authenticated and not request.user.is_superuser:
            if request.user.is_password_expired():
                # Redirect to password reset with token
                if request.user.password_reset_token:
                    return redirect('main:password_reset', token=request.user.password_reset_token)
                else:
                    # If no token, show message to contact admin
                    messages.error(
                        request, 
                        'Su contraseña ha expirado. Contacte al administrador del sistema para obtener un enlace de restablecimiento.'
                    )
                    return redirect('main:login')
        
        return self.get_response(request)
