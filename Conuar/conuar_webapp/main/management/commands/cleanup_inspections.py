from django.core.management.base import BaseCommand
from main.models import Inspection, InspectionPhoto

class Command(BaseCommand):
    help = 'Clean up inspections to keep only one inspection with id=1'

    def handle(self, *args, **options):
        # Get all inspections
        all_inspections = Inspection.objects.all()
        
        self.stdout.write(f'Found {all_inspections.count()} inspections in the database')
        
        # Delete all inspections except id=1
        inspections_to_delete = Inspection.objects.exclude(id=1)
        deleted_count = inspections_to_delete.count()
        
        if deleted_count > 0:
            self.stdout.write(f'Deleting {deleted_count} inspections (keeping only id=1)')
            
            # Delete associated photos first
            for inspection in inspections_to_delete:
                photo_count = inspection.photos.count()
                if photo_count > 0:
                    self.stdout.write(f'Deleting {photo_count} photos from inspection id={inspection.id}')
                    inspection.photos.all().delete()
            
            # Delete the inspections
            inspections_to_delete.delete()
            self.stdout.write(self.style.SUCCESS(f'Successfully deleted {deleted_count} inspections'))
        else:
            self.stdout.write('No inspections to delete')
        
        # Ensure inspection with id=1 exists
        inspection, created = Inspection.objects.get_or_create(
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
        
        if created:
            self.stdout.write(self.style.SUCCESS('Created inspection with id=1'))
        else:
            self.stdout.write('Inspection with id=1 already exists')
        
        # Show final count
        final_count = Inspection.objects.count()
        self.stdout.write(self.style.SUCCESS(f'Final inspection count: {final_count}'))
        
        # Show inspection details
        inspection = Inspection.objects.get(id=1)
        self.stdout.write(f'Inspection details:')
        self.stdout.write(f'  - ID: {inspection.id}')
        self.stdout.write(f'  - Title: {inspection.title}')
        self.stdout.write(f'  - Status: {inspection.get_status_display()}')
        self.stdout.write(f'  - Photos: {inspection.photos.count()}')
