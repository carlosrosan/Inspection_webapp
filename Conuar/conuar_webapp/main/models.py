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
    """Model for product inspections"""
    
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
    title = models.CharField(max_length=200, blank=True, null=True, help_text="Título o nombre de la inspección")
    description = models.TextField(blank=True, null=True, help_text="Descripción detallada de la inspección")
    inspection_type = models.CharField(
        max_length=20, 
        choices=INSPECTION_TYPE_CHOICES,
        default='quality',
        help_text="Tipo de inspección que se está realizando"
    )
    status = models.CharField(
        max_length=20,
        choices=INSPECTION_STATUS_CHOICES,
        default='pending',
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
