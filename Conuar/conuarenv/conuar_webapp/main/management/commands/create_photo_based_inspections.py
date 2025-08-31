from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from main.models import Inspection, InspectionPhoto
from django.core.files import File
import os
from pathlib import Path
from datetime import timedelta
import random

User = get_user_model()

class Command(BaseCommand):
    help = 'Create inspection records based on existing photos in media/inspection_photos'

    def handle(self, *args, **options):
        self.stdout.write('Creating inspection records based on existing photos...')
        
        # Get or create test users
        inspector, created = User.objects.get_or_create(
            username='inspector',
            defaults={
                'email': 'inspector@conuar.com',
                'first_name': 'Nuclear',
                'last_name': 'Inspector',
                'is_inspector': True,
                'is_staff': True,
            }
        )
        
        if created:
            inspector.set_password('inspector123')
            inspector.save()
            self.stdout.write(f'Created inspector user: {inspector.username}')
        else:
            self.stdout.write(f'Using existing inspector user: {inspector.username}')
        
        supervisor, created = User.objects.get_or_create(
            username='supervisor',
            defaults={
                'email': 'supervisor@conuar.com',
                'first_name': 'Nuclear',
                'last_name': 'Supervisor',
                'is_supervisor': True,
                'is_staff': True,
            }
        )
        
        if created:
            supervisor.set_password('supervisor123')
            supervisor.save()
            self.stdout.write(f'Created supervisor user: {supervisor.username}')
        else:
            self.stdout.write(f'Using existing supervisor user: {supervisor.username}')
        
        # Define photo-based inspection data
        photo_inspections = [
            {
                'title': 'OCR System Inspection',
                'description': 'Optical Character Recognition system quality control inspection',
                'inspection_type': 'quality',
                'product_name': 'OCR System',
                'product_code': 'OCR-001',
                'batch_number': 'B2024-OCR-001',
                'serial_number': 'SN-OCR-2024-001',
                'location': 'Nuclear Fuel Assembly Line',
                'status': 'completed',
                'result': 'OCR system functioning within specifications. Character recognition accuracy: 99.8%',
                'notes': 'System calibrated and tested. All optical components clean and aligned.',
                'recommendations': 'Schedule next calibration in 6 months. Monitor performance metrics.',
                'photos': ['1-OCR.bmp', '7-OCR2.bmp']
            },
            {
                'title': 'Zapata Angle Measurement',
                'description': 'Critical angle measurement inspection for fuel rod support components',
                'inspection_type': 'quality',
                'product_name': 'Fuel Rod Support System',
                'product_code': 'ZAP-002',
                'batch_number': 'B2024-ZAP-002',
                'serial_number': 'SN-ZAP-2024-002',
                'location': 'Component Assembly Station',
                'status': 'completed',
                'result': 'All zapata angles within tolerance limits. Measurements verified with calibrated instruments.',
                'notes': 'Angles measured at multiple points. Statistical analysis shows consistent results.',
                'recommendations': 'Continue current manufacturing process. Document measurement procedures.',
                'photos': ['2-Angulo zapata.bmp', '6-Angulo zapatas PP.bmp', '6-Angulo zapatas PP2.bmp']
            },
            {
                'title': 'ZR Type I & II Inspection',
                'description': 'Comprehensive inspection of ZR type I and II components',
                'inspection_type': 'quality',
                'product_name': 'ZR Component System',
                'product_code': 'ZR-003',
                'batch_number': 'B2024-ZR-003',
                'serial_number': 'SN-ZR-2024-003',
                'location': 'Quality Control Lab',
                'status': 'completed',
                'result': 'Both ZR type I and II components meet all specifications. Dimensional tolerances verified.',
                'notes': 'Components inspected for surface finish, dimensional accuracy, and material integrity.',
                'recommendations': 'Approved for assembly. Monitor batch consistency.',
                'photos': ['4-ZR tipo I.bmp', '5-ZR tipo II.bmp']
            },
            {
                'title': 'ZR Pollera Angle Measurement',
                'description': 'Precision angle measurement for ZR pollera components',
                'inspection_type': 'quality',
                'product_name': 'ZR Pollera Assembly',
                'product_code': 'ZRP-004',
                'batch_number': 'B2024-ZRP-004',
                'serial_number': 'SN-ZRP-2024-004',
                'location': 'Metrology Department',
                'status': 'completed',
                'result': 'Pollera angles measured and verified. All measurements within ±0.1 degree tolerance.',
                'notes': 'High-precision measurement equipment used. Multiple measurements taken for verification.',
                'recommendations': 'Components approved. Maintain measurement calibration schedule.',
                'photos': ['3-Angulo pollera ZR.bmp', '3-Angulo pollera ZR2.bmp']
            },
            {
                'title': 'TVS System Inspection',
                'description': 'Thermal Visual System inspection and calibration verification',
                'inspection_type': 'safety',
                'product_name': 'TVS Monitoring System',
                'product_code': 'TVS-005',
                'batch_number': 'B2024-TVS-005',
                'serial_number': 'SN-TVS-2024-005',
                'location': 'Control Room',
                'status': 'completed',
                'result': 'TVS system operational and calibrated. Thermal monitoring accuracy verified.',
                'notes': 'System tested under various temperature conditions. Calibration drift within acceptable limits.',
                'recommendations': 'System approved for operation. Schedule next calibration in 3 months.',
                'photos': ['8-TVS.bmp']
            },
            {
                'title': 'BC Top Position Verification',
                'description': 'Verification of BC top positioning accuracy and alignment',
                'inspection_type': 'quality',
                'product_name': 'BC Positioning System',
                'product_code': 'BCP-006',
                'batch_number': 'B2024-BCP-006',
                'serial_number': 'SN-BCP-2024-006',
                'location': 'Assembly Line Station 3',
                'status': 'completed',
                'result': 'BC top positions verified and aligned. Positioning accuracy within ±0.5mm tolerance.',
                'notes': 'Multiple position measurements taken. Alignment verified with laser measurement system.',
                'recommendations': 'Positioning system approved. Monitor alignment during production runs.',
                'photos': ['9-Posicion topes BC.bmp']
            },
            {
                'title': 'TS Deformation Analysis',
                'description': 'Analysis of TS component deformation under load conditions',
                'inspection_type': 'performance',
                'product_name': 'TS Load Bearing Component',
                'product_code': 'TSL-007',
                'batch_number': 'B2024-TSL-007',
                'serial_number': 'SN-TSL-2024-007',
                'location': 'Testing Laboratory',
                'status': 'completed',
                'result': 'Deformation analysis completed. Components meet load-bearing specifications.',
                'notes': 'Load testing performed at 110% of design load. Deformation within acceptable limits.',
                'recommendations': 'Components approved for service. Monitor performance under operational conditions.',
                'photos': ['10-Deformacion de TS.bmp', '11- Deformacion TS 2.bmp']
            }
        ]
        
        # Get the media directory path
        media_dir = Path('media/inspection_photos')
        if not media_dir.exists():
            self.stdout.write(self.style.ERROR(f'Media directory {media_dir} does not exist!'))
            return
        
        created_inspections = []
        for inspection_data in photo_inspections:
            # Set appropriate dates
            inspection_date = timezone.now() - timedelta(days=random.randint(1, 30))
            completed_date = inspection_date + timedelta(hours=random.randint(2, 8))
            
            # Create the inspection
            inspection = Inspection.objects.create(
                title=inspection_data['title'],
                description=inspection_data['description'],
                inspection_type=inspection_data['inspection_type'],
                product_name=inspection_data['product_name'],
                product_code=inspection_data['product_code'],
                batch_number=inspection_data['batch_number'],
                serial_number=inspection_data['serial_number'],
                location=inspection_data['location'],
                inspection_date=inspection_date,
                completed_date=completed_date,
                status=inspection_data['status'],
                inspector=inspector,
                supervisor=supervisor,
                result=inspection_data['result'],
                notes=inspection_data['notes'],
                recommendations=inspection_data['recommendations'],
            )
            created_inspections.append(inspection)
            self.stdout.write(f'Created inspection: {inspection.title}')
            
            # Create photo records for this inspection
            for photo_filename in inspection_data['photos']:
                photo_path = media_dir / photo_filename
                if photo_path.exists():
                    # Determine photo type based on filename
                    if 'OCR' in photo_filename:
                        photo_type = 'overview'
                    elif 'Angulo' in photo_filename:
                        photo_type = 'measurement'
                    elif 'ZR' in photo_filename:
                        photo_type = 'component'
                    elif 'TVS' in photo_filename:
                        photo_type = 'system'
                    elif 'BC' in photo_filename:
                        photo_type = 'position'
                    elif 'Deformacion' in photo_filename:
                        photo_type = 'analysis'
                    else:
                        photo_type = 'general'
                    
                    # Create photo record
                    photo = InspectionPhoto.objects.create(
                        inspection=inspection,
                        photo=f'inspection_photos/{photo_filename}',
                        caption=f'{inspection_data["product_name"]} - {photo_filename}',
                        photo_type=photo_type
                    )
                    self.stdout.write(f'  - Linked photo: {photo_filename}')
                else:
                    self.stdout.write(self.style.WARNING(f'  - Photo not found: {photo_filename}'))
        
        self.stdout.write(self.style.SUCCESS(f'\nSuccessfully created {len(created_inspections)} inspections with photo links!'))
        self.stdout.write('\nYou can now:')
        self.stdout.write('1. Visit http://127.0.0.1:8000/login/ to log in with:')
        self.stdout.write('   - Username: inspector, Password: inspector123')
        self.stdout.write('   - Username: supervisor, Password: supervisor123')
        self.stdout.write('2. Visit http://127.0.0.1:8000/inspections/ to see the inspection list')
        self.stdout.write('3. Click on any inspection to view details and photos')
        self.stdout.write('4. Test the filtering and search functionality')
