from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import User, Inspection, InspectionPhoto, InspectionMachine, MachineLog, PlcDataRaw
from .validators import CustomPasswordValidator

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Admin interface for custom User model using Django built-in permissions"""
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_role_display', 'is_staff', 'is_active', 'password_expiry_date', 'password_expired', 'date_joined')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Información Personal', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permisos', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'description': 'Supervisor: is_superuser=True | Usuario Regular: is_staff=True | Visualizador: is_active=True'
        }),
        ('Gestión de Contraseña', {
            'fields': ('password_reset_enabled', 'password_reset_token', 'password_expiry_date', 'password_expired'),
            'description': 'Solo los supervisores pueden habilitar el cambio de contraseña para otros usuarios'
        }),
        ('Fechas Importantes', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2'),
        }),
        ('Información Personal', {
            'fields': ('first_name', 'last_name', 'email'),
        }),
        ('Permisos', {
            'fields': ('is_active', 'is_staff', 'is_superuser'),
            'description': 'Supervisor: is_superuser=True | Usuario Regular: is_staff=True | Visualizador: is_active=True'
        }),
        ('Gestión de Contraseña', {
            'fields': ('password_reset_enabled', 'password_reset_token'),
            'description': 'Solo los supervisores pueden habilitar el cambio de contraseña para otros usuarios'
        }),
    )
    
    def get_role_display(self, obj):
        """Display user role based on Django built-in fields"""
        if obj.is_superuser:
            return "Supervisor"
        elif obj.is_staff:
            return "Usuario Regular"
        elif obj.is_active:
            return "Visualizador"
        else:
            return "Inactivo"
    get_role_display.short_description = 'Rol'
    
    def save_model(self, request, obj, form, change):
        """Override save to validate password with custom validator"""
        if not change:  # Only for new users
            password = form.cleaned_data.get('password1')
            if password:
                # Validate password with custom validator
                validator = CustomPasswordValidator()
                try:
                    validator.validate(password, obj)
                except ValidationError as e:
                    from django.contrib import messages
                    messages.error(request, f"Error de validación de contraseña: {e.message}")
                    return
        
        super().save_model(request, obj, form, change)
        
        # Set password expiry for new users (except superusers)
        if not change and not obj.is_superuser:
            obj.set_password_expiry()
    
    def generate_password_reset_url(self, request, queryset):
        """Admin action to generate password reset URLs for selected users"""
        from django.contrib import messages
        from django.urls import reverse
        
        for user in queryset:
            if not user.is_superuser:  # Only allow for non-superusers
                token = user.generate_password_reset_token()
                reset_url = user.get_password_reset_url(request)
                messages.success(request, f'URL de restablecimiento para {user.username}: {reset_url}')
            else:
                messages.warning(request, f'No se puede generar URL de restablecimiento para superusuario: {user.username}')
    
    generate_password_reset_url.short_description = "Generar URL de restablecimiento de contraseña"
    
    def set_password_expiry(self, request, queryset):
        """Admin action to set password expiry for selected users"""
        from django.contrib import messages
        
        for user in queryset:
            if not user.is_superuser:  # Only for non-superusers
                user.set_password_expiry()
                messages.success(request, f'Fecha de expiración establecida para {user.username}')
            else:
                messages.warning(request, f'Los superusuarios están exentos de expiración de contraseña: {user.username}')
    
    set_password_expiry.short_description = "Establecer expiración de contraseña (90 días)"
    
    def get_superuser_reset_url(self, request, queryset):
        """Admin action to get superuser fixed reset URL"""
        from django.contrib import messages
        
        for user in queryset:
            if user.is_superuser:
                from django.urls import reverse
                reset_url = request.build_absolute_uri(
                    reverse('main:password_reset', kwargs={'token': user.get_superuser_fixed_token()})
                )
                messages.success(request, f'URL de restablecimiento para superusuario {user.username}: {reset_url}')
            else:
                messages.warning(request, f'Esta acción solo es para superusuarios: {user.username}')
    
    get_superuser_reset_url.short_description = "Obtener URL de restablecimiento para superusuario"
    
    readonly_fields = ('password_reset_token',)
    actions = ['generate_password_reset_url', 'set_password_expiry', 'get_superuser_reset_url']

@admin.register(Inspection)
class InspectionAdmin(admin.ModelAdmin):
    """Admin interface for Inspection model"""
    list_display = ('id', 'title', 'product_name', 'tipo_combustible', 'status', 'inspector', 'inspection_date')
    list_filter = ('status', 'tipo_combustible', 'inspection_date', 'inspector')
    search_fields = ('title', 'product_name', 'product_code', 'batch_number', 'serial_number', 'inspector__username')
    ordering = ('-inspection_date',)
    date_hierarchy = 'inspection_date'
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('title', 'description', 'tipo_combustible', 'status')
        }),
        ('Información del Producto', {
            'fields': ('product_name', 'product_code', 'batch_number', 'serial_number')
        }),
        ('Ubicación y Fechas', {
            'fields': ('location', 'inspection_date', 'completed_date')
        }),
        ('Personal', {
            'fields': ('inspector',)
        }),
        ('Resultados y Notas', {
            'fields': ('result', 'notes', 'recommendations')
        }),
        ('Marcas de Tiempo', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')

@admin.register(InspectionPhoto)
class InspectionPhotoAdmin(admin.ModelAdmin):
    """Admin interface for InspectionPhoto model"""
    list_display = ('id', 'inspection', 'photo_type', 'caption', 'uploaded_at')
    list_filter = ('photo_type', 'uploaded_at', 'inspection__tipo_combustible')
    search_fields = ('inspection__title', 'inspection__product_name', 'caption', 'photo_type')
    ordering = ('-uploaded_at',)
    date_hierarchy = 'uploaded_at'
    
    fieldsets = (
        ('Información de la Foto', {
            'fields': ('inspection', 'photo', 'photo_type', 'caption')
        }),
        ('Timestamps', {
            'fields': ('uploaded_at',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('uploaded_at',)

@admin.register(InspectionMachine)
class InspectionMachineAdmin(admin.ModelAdmin):
    """Admin interface for InspectionMachine model"""
    list_display = ('machine_id', 'name', 'model', 'version', 'status', 'current_stage', 'total_inspections', 'success_rate')
    list_filter = ('status', 'current_stage', 'model', 'version')
    search_fields = ('machine_id', 'name', 'model')
    ordering = ('machine_id',)
    
    fieldsets = (
        ('Información de la Máquina', {
            'fields': ('machine_id', 'name', 'model', 'version')
        }),
        ('Estado Actual', {
            'fields': ('status', 'current_stage')
        }),
        ('Métricas de Rendimiento', {
            'fields': ('total_inspections', 'inspections_today', 'uptime_hours', 'success_rate', 'average_inspection_time')
        }),
        ('Fechas Importantes', {
            'fields': ('last_inspection', 'last_maintenance', 'last_status_change')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at', 'last_status_change')

@admin.register(MachineLog)
class MachineLogAdmin(admin.ModelAdmin):
    """Admin interface for MachineLog model"""
    list_display = ('id', 'machine', 'log_type', 'message', 'timestamp')
    list_filter = ('log_type', 'timestamp', 'machine')
    search_fields = ('machine__name', 'machine__machine_id', 'message')
    ordering = ('-timestamp',)
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Información del Registro', {
            'fields': ('machine', 'log_type', 'message')
        }),
        ('Timestamp', {
            'fields': ('timestamp',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('timestamp',)

@admin.register(PlcDataRaw)
class PlcDataRawAdmin(admin.ModelAdmin):
    """Admin interface for PlcDataRaw model"""
    list_display = ('id', 'timestamp', 'processed', 'created_at', 'json_preview')
    list_filter = ('processed', 'timestamp', 'created_at')
    search_fields = ('json_data',)
    ordering = ('-timestamp',)
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Información del Dato PLC', {
            'fields': ('timestamp', 'json_data', 'processed')
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at',)
    
    def json_preview(self, obj):
        """Show a preview of the JSON data"""
        if len(obj.json_data) > 100:
            return obj.json_data[:100] + '...'
        return obj.json_data
    json_preview.short_description = 'JSON Preview'
