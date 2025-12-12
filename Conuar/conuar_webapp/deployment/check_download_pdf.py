#!/usr/bin/env python
"""
Troubleshooting script for PDF generation issues.
This script checks:
1. Logo file existence and path resolution
2. Photo file existence and path resolution
3. xhtml2pdf installation and functionality
4. Path format compatibility for file:// URLs
"""

import os
import sys
from pathlib import Path

# Add the parent directory to the path to import Django settings
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.conf import settings
from main.models import Inspection, InspectionPhoto
from xhtml2pdf import pisa
from io import BytesIO

def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def check_logo():
    """Check if logo file exists and can be resolved"""
    print_section("LOGO FILE CHECK")
    
    possible_paths = []
    
    # Try STATICFILES_DIRS first
    if settings.STATICFILES_DIRS:
        static_dir = settings.STATICFILES_DIRS[0]
        if hasattr(static_dir, '__fspath__'):
            static_dir = str(static_dir)
        elif isinstance(static_dir, (str, bytes)):
            static_dir = str(static_dir)
        possible_paths.append(('STATICFILES_DIRS', os.path.join(static_dir, 'assets', 'logo_conuar1.jpeg')))
    
    # Try BASE_DIR/static
    base_dir = settings.BASE_DIR
    if hasattr(base_dir, '__fspath__'):
        base_dir = str(base_dir)
    elif isinstance(base_dir, (str, bytes)):
        base_dir = str(base_dir)
    possible_paths.append(('BASE_DIR/static', os.path.join(base_dir, 'static', 'assets', 'logo_conuar1.jpeg')))
    
    # Try STATIC_ROOT
    if settings.STATIC_ROOT:
        static_root = settings.STATIC_ROOT
        if hasattr(static_root, '__fspath__'):
            static_root = str(static_root)
        elif isinstance(static_root, (str, bytes)):
            static_root = str(static_root)
        possible_paths.append(('STATIC_ROOT', os.path.join(static_root, 'assets', 'logo_conuar1.jpeg')))
    
    print(f"Checking {len(possible_paths)} possible logo locations...")
    logo_found = False
    
    for source, path in possible_paths:
        abs_path = os.path.abspath(path)
        exists = os.path.exists(abs_path)
        print(f"\n  [{source}]")
        print(f"    Path: {abs_path}")
        print(f"    Exists: {exists}")
        
        if exists:
            # Check file size
            size = os.path.getsize(abs_path)
            print(f"    Size: {size} bytes")
            
            # Test file:// URL format
            file_url_2 = f"file://{abs_path.replace(chr(92), '/')}"
            file_url_3 = f"file:///{abs_path.replace(chr(92), '/')}"
            print(f"    file:// URL (2 slashes): {file_url_2}")
            print(f"    file:// URL (3 slashes): {file_url_3}")
            
            if not logo_found:
                logo_found = True
                print(f"    ✓ LOGO FOUND at this location!")
    
    if not logo_found:
        print("\n  ✗ LOGO NOT FOUND in any location!")
    
    return logo_found

def check_photos():
    """Check photo files for inspections"""
    print_section("PHOTO FILES CHECK")
    
    inspections = Inspection.objects.all()[:5]  # Check first 5 inspections
    print(f"Checking photos for {inspections.count()} inspection(s)...")
    
    total_photos = 0
    found_photos = 0
    missing_photos = 0
    
    for inspection in inspections:
        photos = inspection.photos.all()
        print(f"\n  Inspection ID {inspection.id}: {photos.count()} photo(s)")
        
        for photo in photos:
            total_photos += 1
            photo_path = None
            
            # Try to get photo path
            try:
                if hasattr(photo.photo, 'path'):
                    photo_path = os.path.abspath(photo.photo.path)
                else:
                    media_root = settings.MEDIA_ROOT
                    if hasattr(media_root, '__fspath__'):
                        media_root = str(media_root)
                    elif isinstance(media_root, (str, bytes)):
                        media_root = str(media_root)
                    photo_path = os.path.abspath(os.path.join(media_root, photo.photo.name))
            except Exception as e:
                print(f"    ✗ Error getting path for photo {photo.id}: {e}")
                missing_photos += 1
                continue
            
            if photo_path and os.path.exists(photo_path):
                found_photos += 1
                size = os.path.getsize(photo_path)
                file_url = f"file://{photo_path.replace(chr(92), '/')}"
                print(f"    ✓ Photo {photo.id}: {os.path.basename(photo_path)} ({size} bytes)")
                print(f"      URL: {file_url}")
            else:
                missing_photos += 1
                print(f"    ✗ Photo {photo.id}: NOT FOUND")
                if photo_path:
                    print(f"      Expected at: {photo_path}")
                else:
                    print(f"      Photo name: {photo.photo.name if photo.photo else 'None'}")
    
    print(f"\n  Summary:")
    print(f"    Total photos: {total_photos}")
    print(f"    Found: {found_photos}")
    print(f"    Missing: {missing_photos}")
    
    return found_photos, missing_photos

def test_xhtml2pdf():
    """Test xhtml2pdf with a simple HTML containing an image"""
    print_section("XHTML2PDF FUNCTIONALITY TEST")
    
    # Find logo for test
    logo_path = None
    if settings.STATICFILES_DIRS:
        static_dir = settings.STATICFILES_DIRS[0]
        if hasattr(static_dir, '__fspath__'):
            static_dir = str(static_dir)
        test_logo = os.path.join(static_dir, 'assets', 'logo_conuar1.jpeg')
        if os.path.exists(test_logo):
            logo_path = os.path.abspath(test_logo)
    
    if not logo_path:
        print("  ✗ Cannot test - logo not found")
        return False
    
    # Convert logo to base64 data URI
    import base64
    try:
        with open(logo_path, 'rb') as img_file:
            img_data = img_file.read()
            img_base64 = base64.b64encode(img_data).decode('utf-8')
            logo_data_uri = f"data:image/jpeg;base64,{img_base64}"
        print(f"  Logo loaded and encoded as base64 data URI")
    except Exception as e:
        print(f"  ✗ Failed to load logo: {e}")
        return False
    
    # Test with base64 data URI (most reliable method)
    print(f"\n  Test: Using base64 data URI format")
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial; }}
            img {{ max-width: 200px; }}
        </style>
    </head>
    <body>
        <h1>PDF Generation Test</h1>
        <p>Testing image with base64 data URI format</p>
        <img src="{logo_data_uri}" alt="Test Logo" />
        <p>If you see the logo above, this format works!</p>
    </body>
    </html>
    """
    
    try:
        buffer = BytesIO()
        pisa_status = pisa.CreatePDF(html, dest=buffer)
        
        if pisa_status.err:
            print(f"    ✗ Error: {pisa_status.err}")
            return False
        else:
            pdf_size = len(buffer.getvalue())
            print(f"    ✓ PDF generated successfully ({pdf_size} bytes)")
            # Save test PDF
            test_pdf_path = os.path.join(settings.BASE_DIR, 'deployment', 'test_pdf_base64.pdf')
            with open(test_pdf_path, 'wb') as f:
                f.write(buffer.getvalue())
            print(f"    ✓ Test PDF saved to: {test_pdf_path}")
            return True
    except Exception as e:
        print(f"    ✗ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_settings():
    """Check Django settings relevant to PDF generation"""
    print_section("DJANGO SETTINGS CHECK")
    
    print(f"  BASE_DIR: {settings.BASE_DIR}")
    print(f"  MEDIA_ROOT: {settings.MEDIA_ROOT}")
    print(f"  STATIC_URL: {settings.STATIC_URL}")
    print(f"  STATIC_ROOT: {settings.STATIC_ROOT}")
    print(f"  STATICFILES_DIRS: {settings.STATICFILES_DIRS}")
    
    # Check if directories exist
    print(f"\n  Directory existence:")
    print(f"    MEDIA_ROOT exists: {os.path.exists(str(settings.MEDIA_ROOT))}")
    if settings.STATICFILES_DIRS:
        for static_dir in settings.STATICFILES_DIRS:
            print(f"    STATICFILES_DIRS[{static_dir}] exists: {os.path.exists(str(static_dir))}")
    if settings.STATIC_ROOT:
        print(f"    STATIC_ROOT exists: {os.path.exists(str(settings.STATIC_ROOT))}")

def main():
    """Run all checks"""
    print("\n" + "=" * 70)
    print("  PDF GENERATION TROUBLESHOOTING SCRIPT")
    print("=" * 70)
    
    # Check settings
    check_settings()
    
    # Check logo
    logo_found = check_logo()
    
    # Check photos
    found_photos, missing_photos = check_photos()
    
    # Test xhtml2pdf
    pdf_works = test_xhtml2pdf()
    
    # Summary
    print_section("SUMMARY")
    print(f"  Logo found: {'✓ YES' if logo_found else '✗ NO'}")
    print(f"  Photos found: {found_photos} / {found_photos + missing_photos}")
    print(f"  PDF generation: {'✓ WORKS' if pdf_works else '✗ FAILED'}")
    
    if not logo_found:
        print("\n  ⚠ WARNING: Logo file not found. PDFs will not include logo.")
    if missing_photos > 0:
        print(f"\n  ⚠ WARNING: {missing_photos} photo(s) not found. They won't appear in PDFs.")
    if not pdf_works:
        print("\n  ⚠ WARNING: PDF generation test failed. Check xhtml2pdf installation.")
    
    print("\n" + "=" * 70)
    print("  Troubleshooting complete!")
    print("=" * 70 + "\n")

if __name__ == '__main__':
    main()

