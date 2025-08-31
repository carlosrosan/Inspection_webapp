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
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    INSPECTION_TYPE_CHOICES = [
        ('quality', 'Quality Control'),
        ('safety', 'Safety Inspection'),
        ('compliance', 'Compliance Check'),
        ('performance', 'Performance Test'),
        ('visual', 'Visual Inspection'),
    ]
    
    # Basic Information
    title = models.CharField(max_length=200, blank=True, null=True, help_text="Inspection title or name")
    description = models.TextField(blank=True, null=True, help_text="Detailed description of the inspection")
    inspection_type = models.CharField(
        max_length=20, 
        choices=INSPECTION_TYPE_CHOICES,
        default='quality',
        help_text="Type of inspection being performed"
    )
    status = models.CharField(
        max_length=20,
        choices=INSPECTION_STATUS_CHOICES,
        default='pending',
        help_text="Current status of the inspection"
    )
    
    # Product Information
    product_name = models.CharField(max_length=200, blank=True, null=True, help_text="Name of the product being inspected")
    product_code = models.CharField(max_length=100, blank=True, help_text="Product code or SKU")
    batch_number = models.CharField(max_length=100, blank=True, help_text="Batch or lot number")
    serial_number = models.CharField(max_length=100, blank=True, help_text="Serial number if applicable")
    
    # Location and Dates
    location = models.CharField(max_length=200, blank=True, help_text="Location where inspection was performed")
    inspection_date = models.DateTimeField(default=timezone.now, help_text="Date and time of inspection")
    completed_date = models.DateTimeField(null=True, blank=True, help_text="Date when inspection was completed")
    
    # Inspector Information
    inspector = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='inspections_conducted',
        help_text="User who performed the inspection"
    )
    supervisor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inspections_supervised',
        help_text="Supervisor who reviewed the inspection"
    )
    
    # Results and Notes
    result = models.TextField(blank=True, help_text="Inspection results and findings")
    notes = models.TextField(blank=True, help_text="Additional notes or comments")
    recommendations = models.TextField(blank=True, help_text="Recommendations based on inspection")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-inspection_date']
        verbose_name = 'Inspection'
        verbose_name_plural = 'Inspections'
    
    def __str__(self):
        return f"{self.title or 'Untitled'} - {self.product_name or 'No Product'} ({self.get_status_display()})"
    
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
    photo_type = models.CharField(max_length=50, blank=True, help_text="Type of photo (e.g., 'before', 'after', 'defect', 'overview')")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['uploaded_at']
        verbose_name = 'Inspection Photo'
        verbose_name_plural = 'Inspection Photos'
    
    def __str__(self):
        return f"Photo for {self.inspection.title or 'Untitled'} - {self.caption or 'No caption'}"
    
    @property
    def filename(self):
        return self.photo.name.split('/')[-1]
