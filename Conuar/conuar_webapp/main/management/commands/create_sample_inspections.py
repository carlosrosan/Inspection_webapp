from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from main.models import Inspection, InspectionPhoto
from datetime import timedelta
import random

User = get_user_model()

class Command(BaseCommand):
    help = 'Create sample inspection data for testing'

    def handle(self, *args, **options):
        self.stdout.write('Creating sample inspection data...')
        
        # Get or create a test user
        user, created = User.objects.get_or_create(
            username='test_inspector',
            defaults={
                'email': 'inspector@conuar.com',
                'first_name': 'Test',
                'last_name': 'Inspector',
                'is_inspector': True,
                'is_staff': True,
            }
        )
        
        if created:
            user.set_password('testpass123')
            user.save()
            self.stdout.write(f'Created user: {user.username}')
        else:
            self.stdout.write(f'Using existing user: {user.username}')
        
        # Create sample inspections
        inspection_data = [
            {
                'title': 'Quality Control Check - Product A',
                'description': 'Comprehensive quality control inspection for Product A batch #2024-001',
                'inspection_type': 'quality',
                'product_name': 'Product A',
                'product_code': 'PROD-A-001',
                'batch_number': 'B2024-001',
                'serial_number': 'SN001-2024',
                'location': 'Production Line 1',
                'status': 'completed',
                'result': 'All quality parameters within acceptable limits. Product approved for shipment.',
                'notes': 'Minor surface finish variations noted but within tolerance.',
                'recommendations': 'Continue current production parameters. Monitor surface finish quality.',
            },
            {
                'title': 'Safety Inspection - Equipment B',
                'description': 'Annual safety inspection for critical production equipment',
                'inspection_type': 'safety',
                'product_name': 'Equipment B',
                'product_code': 'EQP-B-002',
                'batch_number': 'N/A',
                'serial_number': 'SN002-2023',
                'location': 'Production Floor',
                'status': 'in_progress',
                'result': '',
                'notes': 'Safety guards properly installed. Emergency stops functional.',
                'recommendations': 'Schedule maintenance for hydraulic system next month.',
            },
            {
                'title': 'Compliance Audit - Process C',
                'description': 'ISO 9001 compliance audit for manufacturing process C',
                'inspection_type': 'compliance',
                'product_name': 'Process C',
                'product_code': 'PROC-C-003',
                'batch_number': 'N/A',
                'serial_number': 'N/A',
                'location': 'Manufacturing Department',
                'status': 'pending',
                'result': '',
                'notes': 'Documentation review completed. Process mapping verified.',
                'recommendations': 'Implement additional quality checkpoints.',
            },
            {
                'title': 'Performance Test - Component D',
                'description': 'Performance testing for new component design',
                'inspection_type': 'performance',
                'product_name': 'Component D',
                'product_code': 'COMP-D-004',
                'batch_number': 'TEST-001',
                'serial_number': 'SN003-2024',
                'location': 'Testing Laboratory',
                'status': 'completed',
                'result': 'Component meets all performance specifications. Efficiency improved by 15%.',
                'notes': 'Test completed successfully under various load conditions.',
                'recommendations': 'Proceed with production. Consider design optimization for cost reduction.',
            },
            {
                'title': 'Visual Inspection - Assembly E',
                'description': 'Final visual inspection before packaging',
                'inspection_type': 'visual',
                'product_name': 'Assembly E',
                'product_code': 'ASSY-E-005',
                'batch_number': 'B2024-002',
                'serial_number': 'SN004-2024',
                'location': 'Packaging Area',
                'status': 'failed',
                'result': 'Assembly rejected due to visible defects.',
                'notes': 'Surface scratches and minor dents detected. Paint finish inconsistent.',
                'recommendations': 'Review handling procedures. Implement additional quality gates.',
            },
        ]
        
        created_inspections = []
        for data in inspection_data:
            # Set appropriate dates
            if data['status'] == 'completed':
                inspection_date = timezone.now() - timedelta(days=random.randint(1, 30))
                completed_date = inspection_date + timedelta(hours=random.randint(2, 8))
            elif data['status'] == 'in_progress':
                inspection_date = timezone.now() - timedelta(hours=random.randint(1, 6))
                completed_date = None
            else:
                inspection_date = timezone.now() + timedelta(days=random.randint(1, 7))
                completed_date = None
            
            inspection = Inspection.objects.create(
                title=data['title'],
                description=data['description'],
                inspection_type=data['inspection_type'],
                product_name=data['product_name'],
                product_code=data['product_code'],
                batch_number=data['batch_number'],
                serial_number=data['serial_number'],
                location=data['location'],
                inspection_date=inspection_date,
                completed_date=completed_date,
                status=data['status'],
                inspector=user,
                result=data['result'],
                notes=data['notes'],
                recommendations=data['recommendations'],
            )
            created_inspections.append(inspection)
            self.stdout.write(f'Created inspection: {inspection.title}')
        
        self.stdout.write(f'\nSuccessfully created {len(created_inspections)} sample inspections!')
        self.stdout.write('\nYou can now:')
        self.stdout.write('1. Visit http://127.0.0.1:8000/inspections/ to see the inspection list')
        self.stdout.write('2. Click on any inspection to view details')
        self.stdout.write('3. Test the filtering and search functionality')
        self.stdout.write('\nNote: Photos will need to be uploaded manually through the admin interface')
