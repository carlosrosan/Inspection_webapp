from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Inspection, InspectionPhoto, InspectionMachine, MachineLog

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Admin interface for custom User model using Django built-in permissions"""
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_role_display', 'is_staff', 'is_active', 'date_joined')
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

@admin.register(Inspection)
class InspectionAdmin(admin.ModelAdmin):
    """Admin interface for Inspection model"""
    list_display = ('id', 'title', 'product_name', 'tipo_combustible', 'status', 'inspector', 'inspection_date')
    list_filter = ('status', 'tipo_combustible', 'inspection_date', 'inspector', 'supervisor')
    search_fields = ('title', 'product_name', 'product_code', 'batch_number', 'serial_number', 'inspector__username', 'supervisor__username')
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
            'fields': ('inspector', 'supervisor')
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
