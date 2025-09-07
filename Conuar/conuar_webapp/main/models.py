from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class User(AbstractUser):
    """Custom user model for privileged access"""
    is_inspector = models.BooleanField(default=False)
    is_supervisor = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return self.username

class Inspection(models.Model):
    """Model for product inspections - Single inspection for the system"""
    
    INSPECTION_STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('in_progress', 'En Progreso'),
        ('completed', 'Completada'),
        ('failed', 'Fallida'),
        ('approved', 'Aprobada'),
        ('rejected', 'Rechazada'),
    ]
    
    INSPECTION_TYPE_CHOICES = [
        ('quality', 'Control de Calidad'),
        ('safety', 'Inspección de Seguridad'),
        ('compliance', 'Verificación de Cumplimiento'),
        ('performance', 'Prueba de Rendimiento'),
        ('visual', 'Inspección Visual'),
    ]
    
    # Basic Information
    title = models.CharField(max_length=200, default='Inspección de Combustible ArByte', help_text="Título o nombre de la inspección")
    description = models.TextField(default='Inspección de calidad de combustible utilizando el sistema ArByte-3000', help_text="Descripción detallada de la inspección")
    inspection_type = models.CharField(
        max_length=20, 
        choices=INSPECTION_TYPE_CHOICES,
        default='quality',
        help_text="Tipo de inspección que se está realizando"
    )
    status = models.CharField(
        max_length=20,
        choices=INSPECTION_STATUS_CHOICES,
        default='completed',
        help_text="Estado actual de la inspección"
    )
    
    # Product Information
    product_name = models.CharField(max_length=200, blank=True, null=True, help_text="Nombre del producto que se está inspeccionando")
    product_code = models.CharField(max_length=100, blank=True, help_text="Código del producto o SKU")
    batch_number = models.CharField(max_length=100, blank=True, help_text="Número de lote o partida")
    serial_number = models.CharField(max_length=100, blank=True, help_text="Número de serie si aplica")
    
    # Location and Dates
    location = models.CharField(max_length=200, blank=True, help_text="Ubicación donde se realizó la inspección")
    inspection_date = models.DateTimeField(default=timezone.now, help_text="Fecha y hora de la inspección")
    completed_date = models.DateTimeField(null=True, blank=True, help_text="Fecha cuando se completó la inspección")
    
    # Inspector Information
    inspector = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='inspections_conducted',
        help_text="Usuario que realizó la inspección"
    )
    supervisor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inspections_supervised',
        help_text="Supervisor que revisó la inspección"
    )
    
    # Results and Notes
    result = models.TextField(blank=True, help_text="Resultados y hallazgos de la inspección")
    notes = models.TextField(blank=True, help_text="Notas adicionales o comentarios")
    recommendations = models.TextField(blank=True, help_text="Recomendaciones basadas en la inspección")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-inspection_date']
        verbose_name = 'Inspección'
        verbose_name_plural = 'Inspecciones'
    
    def __str__(self):
        return f"{self.title or 'Sin Título'} - {self.product_name or 'Sin Producto'} ({self.get_status_display()})"
    
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('main:inspection_detail', kwargs={'inspection_id': self.id})
    
    @property
    def is_completed(self):
        return self.status in ['completed', 'approved', 'rejected']
    
    @property
    def duration(self):
        if self.completed_date and self.inspection_date:
            return self.completed_date - self.inspection_date
        return None
    
    @classmethod
    def get_inspection(cls):
        """Get the single inspection, create if doesn't exist"""
        inspection, created = cls.objects.get_or_create(
            id=1,
            defaults={
                'title': 'Inspección de Combustible ArByte',
                'description': 'Inspección de calidad de combustible utilizando el sistema ArByte-3000',
                'inspection_type': 'quality',
                'status': 'completed',
                'product_name': 'Combustible Industrial',
                'product_code': 'COMB-001',
                'batch_number': 'LOTE-2024-001',
                'location': 'Planta de Inspección ArByte',
            }
        )
        return inspection

class InspectionPhoto(models.Model):
    """Model for inspection photos"""
    inspection = models.ForeignKey(Inspection, on_delete=models.CASCADE, related_name='photos')
    photo = models.ImageField(upload_to='inspections/%Y/%m/%d/')
    caption = models.CharField(max_length=200, blank=True)
    photo_type = models.CharField(max_length=50, blank=True, help_text="Tipo de foto (ej., 'antes', 'después', 'defecto', 'vista general')")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['uploaded_at']
        verbose_name = 'Foto de Inspección'
        verbose_name_plural = 'Fotos de Inspección'
    
    def __str__(self):
        return f"Foto para {self.inspection.title or 'Sin Título'} - {self.caption or 'Sin descripción'}"
    
    @property
    def filename(self):
        return self.photo.name.split('/')[-1]

class InspectionMachine(models.Model):
    """Model for inspection machine status and metrics"""
    
    MACHINE_STATUS_CHOICES = [
        ('offline', 'Desconectada'),
        ('idle', 'En Espera'),
        ('calibrating', 'Calibrando'),
        ('inspecting', 'Inspeccionando'),
        ('maintenance', 'En Mantenimiento'),
        ('error', 'Error'),
    ]
    
    MACHINE_STAGE_CHOICES = [
        ('initialization', 'Inicialización'),
        ('sample_preparation', 'Preparación de Muestra'),
        ('analysis', 'Análisis en Progreso'),
        ('quality_check', 'Verificación de Calidad'),
        ('report_generation', 'Generación de Reporte'),
        ('completion', 'Finalización'),
    ]
    
    # Machine Information
    machine_id = models.CharField(max_length=50, unique=True, default='MAQ-001')
    name = models.CharField(max_length=100, default='Analizador de Combustible ArByte-3000')
    model = models.CharField(max_length=50, default='AB-3000')
    version = models.CharField(max_length=20, default='v2.1.3')
    
    # Current Inspection
    current_inspection = models.OneToOneField(
        'Inspection',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='machine',
        help_text="Inspección actual de la máquina"
    )
    
    # Current Status
    status = models.CharField(
        max_length=20,
        choices=MACHINE_STATUS_CHOICES,
        default='offline',
        help_text="Estado actual de la máquina"
    )
    current_stage = models.CharField(
        max_length=30,
        choices=MACHINE_STAGE_CHOICES,
        blank=True,
        null=True,
        help_text="Etapa actual del proceso de inspección"
    )
    
    # Metrics
    total_inspections = models.PositiveIntegerField(default=0, help_text="Total de inspecciones realizadas")
    inspections_today = models.PositiveIntegerField(default=0, help_text="Inspecciones realizadas hoy")
    uptime_hours = models.FloatField(default=0.0, help_text="Horas de funcionamiento")
    last_inspection = models.DateTimeField(null=True, blank=True, help_text="Última inspección realizada")
    last_maintenance = models.DateTimeField(null=True, blank=True, help_text="Último mantenimiento")
    
    # Performance Metrics
    success_rate = models.FloatField(default=100.0, help_text="Tasa de éxito de inspecciones (%)")
    average_inspection_time = models.FloatField(default=0.0, help_text="Tiempo promedio de inspección (minutos)")
    
    # Timestamps
    last_status_change = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Máquina de Inspección'
        verbose_name_plural = 'Máquinas de Inspección'
    
    def __str__(self):
        return f"{self.name} - {self.get_status_display()}"
    
    @property
    def is_online(self):
        return self.status != 'offline'
    
    @property
    def is_busy(self):
        return self.status in ['calibrating', 'inspecting']
    
    @property
    def status_color(self):
        status_colors = {
            'offline': 'danger',
            'idle': 'warning',
            'calibrating': 'info',
            'inspecting': 'success',
            'maintenance': 'secondary',
            'error': 'danger',
        }
        return status_colors.get(self.status, 'secondary')
    
    @classmethod
    def get_machine(cls):
        """Get the single machine, create if doesn't exist"""
        machine, created = cls.objects.get_or_create(
            machine_id='MAQ-001',
            defaults={
                'name': 'Analizador de Combustible ArByte-3000',
                'model': 'AB-3000',
                'version': 'v2.1.3',
                'status': 'idle',
                'total_inspections': 1,
                'inspections_today': 1,
                'uptime_hours': 0.0,
                'success_rate': 100.0,
                'average_inspection_time': 0.0,
            }
        )
        
        # Link to the single inspection if not already linked
        if not machine.current_inspection:
            from .models import Inspection
            inspection = Inspection.get_inspection()
            machine.current_inspection = inspection
            machine.save()
        
        return machine

class MachineLog(models.Model):
    """Model for machine operation logs"""
    
    LOG_TYPE_CHOICES = [
        ('status_change', 'Cambio de Estado'),
        ('inspection_start', 'Inicio de Inspección'),
        ('inspection_complete', 'Inspección Completada'),
        ('maintenance', 'Mantenimiento'),
        ('error', 'Error'),
        ('calibration', 'Calibración'),
    ]
    
    machine = models.ForeignKey(InspectionMachine, on_delete=models.CASCADE, related_name='logs')
    log_type = models.CharField(max_length=20, choices=LOG_TYPE_CHOICES)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Registro de Máquina'
        verbose_name_plural = 'Registros de Máquina'
    
    def __str__(self):
        return f"{self.machine.name} - {self.get_log_type_display()} - {self.timestamp}"

class SystemConfiguration(models.Model):
    """Model for system configuration settings"""
    
    # Storage Configuration
    media_storage_path = models.CharField(
        max_length=500, 
        default='media/inspection_photos/',
        help_text="Ruta de almacenamiento para archivos multimedia"
    )
    
    # Camera Configuration
    camera_1_ip = models.GenericIPAddressField(
        default='192.168.1.100',
        help_text="Dirección IP de la Cámara 1"
    )
    camera_2_ip = models.GenericIPAddressField(
        default='192.168.1.101',
        help_text="Dirección IP de la Cámara 2"
    )
    camera_3_ip = models.GenericIPAddressField(
        default='192.168.1.102',
        help_text="Dirección IP de la Cámara 3"
    )
    
    # PLC Configuration
    plc_ip = models.GenericIPAddressField(
        default='192.168.1.50',
        help_text="Dirección IP del PLC que controla la máquina de inspección"
    )
    plc_port = models.PositiveIntegerField(
        default=502,
        help_text="Puerto del PLC (por defecto 502 para Modbus)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Usuario que realizó la última actualización"
    )
    
    class Meta:
        verbose_name = 'Configuración del Sistema'
        verbose_name_plural = 'Configuraciones del Sistema'
    
    def __str__(self):
        return f"Configuración del Sistema - {self.updated_at.strftime('%d/%m/%Y %H:%M')}"
    
    @classmethod
    def get_config(cls):
        """Get the current system configuration, create if doesn't exist"""
        config, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                'media_storage_path': 'media/inspection_photos/',
                'camera_1_ip': '192.168.1.100',
                'camera_2_ip': '192.168.1.101',
                'camera_3_ip': '192.168.1.102',
                'plc_ip': '192.168.1.50',
                'plc_port': 502,
            }
        )
        return config

class InspectionPlcEvent(models.Model):
    """Model for PLC events during inspections"""
    
    EXECUTION_TYPE_CHOICES = [
        ('automatic', 'Automático'),
        ('manual', 'Manual'),
        ('free', 'Libre'),
    ]
    
    FILMING_TYPE_CHOICES = [
        ('video', 'Video'),
        ('photo', 'Foto'),
    ]
    
    # Basic Information
    timestamp_plc = models.DateTimeField(help_text="Timestamp del PLC")
    id_inspection = models.ForeignKey(
        Inspection, 
        on_delete=models.CASCADE, 
        related_name='plc_events',
        help_text="ID de la inspección relacionada"
    )
    execution_id = models.CharField(
        max_length=100, 
        help_text="ID ejecución: Entre descanso y descanso"
    )
    control_point_id = models.CharField(
        max_length=100, 
        help_text="ID punto de control: Ej. Zapata num. 5"
    )
    execution_type = models.CharField(
        max_length=20,
        choices=EXECUTION_TYPE_CHOICES,
        help_text="Tipo de ejecución"
    )
    control_point_label = models.CharField(
        max_length=200, 
        blank=True,
        help_text="Etiqueta punto de control (solo para rutinas no libres)"
    )
    
    # Position Information
    x_control_point = models.FloatField(help_text="X punto de control")
    y_control_point = models.FloatField(help_text="Y punto de control")
    z_control_point = models.FloatField(help_text="Z punto de control")
    plate_angle = models.FloatField(help_text="Ángulo del plato")
    
    # User Information
    control_point_creator = models.CharField(
        max_length=100, 
        help_text="Usuario creador punto de control"
    )
    program_creator = models.CharField(
        max_length=100, 
        help_text="Usuario creador Programa"
    )
    program_version = models.CharField(
        max_length=50, 
        help_text="Version del programa"
    )
    
    # Camera Information
    camera_id = models.CharField(
        max_length=50, 
        help_text="ID Cámara"
    )
    filming_type = models.CharField(
        max_length=20,
        choices=FILMING_TYPE_CHOICES,
        help_text="Tipo filmación"
    )
    last_photo_request_timestamp = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Último timestamp solicitud foto cámara"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-timestamp_plc']
        verbose_name = 'Evento PLC de Inspección'
        verbose_name_plural = 'Eventos PLC de Inspección'
    
    def __str__(self):
        return f"PLC Event - {self.id_inspection.title} - {self.control_point_id} - {self.timestamp_plc}"