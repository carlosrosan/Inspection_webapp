from django.core.management.base import BaseCommand
from django.conf import settings
import os
from main.models import Inspection, InspectionPhoto

class Command(BaseCommand):
    help = 'Populate the database with existing photos from the media folder'

    def handle(self, *args, **options):
        # Get or create the single inspection
        inspection = Inspection.get_inspection()
        self.stdout.write(f'Using inspection ID: {inspection.id}')
        
        # Get the media folder path
        media_path = os.path.join(settings.MEDIA_ROOT, 'inspection_photos')
        
        if not os.path.exists(media_path):
            self.stdout.write(
                self.style.ERROR(f'Media folder not found: {media_path}')
            )
            return
        
        # Get all photo files
        photo_files = [f for f in os.listdir(media_path) if f.lower().endswith(('.bmp', '.jpg', '.jpeg', '.png', '.gif'))]
        
        if not photo_files:
            self.stdout.write(
                self.style.WARNING('No photo files found in the media folder')
            )
            return
        
        # Clear existing photos for this inspection
        InspectionPhoto.objects.filter(inspection=inspection).delete()
        
        # Create photo records for each file
        created_count = 0
        for photo_file in photo_files:
            # Create a relative path for the ImageField
            relative_path = f'inspection_photos/{photo_file}'
            
            # Determine photo type based on filename
            photo_type = self.get_photo_type(photo_file)
            caption = self.get_photo_caption(photo_file)
            
            # Create the photo record
            photo = InspectionPhoto.objects.create(
                inspection=inspection,
                photo=relative_path,
                caption=caption,
                photo_type=photo_type
            )
            
            created_count += 1
            self.stdout.write(f'Created photo record: {photo_file}')
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {created_count} photo records for inspection: {inspection.title}')
        )
    
    def get_photo_type(self, filename):
        """Determine photo type based on filename"""
        filename_lower = filename.lower()
        
        if 'ocr' in filename_lower:
            return 'ocr'
        elif 'angulo' in filename_lower:
            return 'angulo'
        elif 'deformacion' in filename_lower:
            return 'deformacion'
        elif 'zr' in filename_lower:
            return 'zr'
        elif 'pp' in filename_lower:
            return 'pp'
        elif 'tvs' in filename_lower:
            return 'tvs'
        elif 'topes' in filename_lower:
            return 'topes'
        else:
            return 'general'
    
    def get_photo_caption(self, filename):
        """Generate caption based on filename"""
        # Remove file extension
        name = os.path.splitext(filename)[0]
        
        # Replace underscores and hyphens with spaces
        caption = name.replace('_', ' ').replace('-', ' ')
        
        # Capitalize first letter of each word
        caption = ' '.join(word.capitalize() for word in caption.split())
        
        return caption
