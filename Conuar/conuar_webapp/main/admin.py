from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Inspection, InspectionPhoto

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Admin interface for custom User model"""
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_inspector', 'is_supervisor', 'is_staff', 'is_active')
    list_filter = ('is_inspector', 'is_supervisor', 'is_staff', 'is_active', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)
    
    fieldsets = UserAdmin.fieldsets + (
        ('Roles de Control de Calidad Nuclear', {
            'fields': ('is_inspector', 'is_supervisor')
        }),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Roles de Control de Calidad Nuclear', {
            'fields': ('is_inspector', 'is_supervisor')
        }),
    )

@admin.register(Inspection)
class InspectionAdmin(admin.ModelAdmin):
    """Admin interface for Inspection model"""
    list_display = ('id', 'title', 'product_name', 'inspection_type', 'status', 'inspector', 'inspection_date')
    list_filter = ('status', 'inspection_type', 'inspection_date', 'inspector', 'supervisor')
    search_fields = ('title', 'product_name', 'product_code', 'batch_number', 'serial_number', 'inspector__username', 'supervisor__username')
    ordering = ('-inspection_date',)
    date_hierarchy = 'inspection_date'
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('title', 'description', 'inspection_type', 'status')
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
    list_filter = ('photo_type', 'uploaded_at', 'inspection__inspection_type')
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
