"""
Configuration file for directory paths used across the inspection system.

This file centralizes path configuration for:
- Inspection photos directory (STAGING and PROCESSED folders)
- Inspection reports directory (PDF reports)

All paths are relative to the project root (BASE_DIR) or can be absolute paths.
"""

from pathlib import Path

# Base directory of the project (parent of config folder)
BASE_DIR = Path(__file__).resolve().parent.parent

# Inspection photos directory structure
# This is where photos are stored (STAGING and PROCESSED subdirectories)
INSPECTION_PHOTOS_DIR = BASE_DIR / "media" / "inspection_photos"

# Inspection reports directory
# This is where PDF reports are automatically saved
INSPECTION_REPORTS_DIR = BASE_DIR / "media" / "inspection_reports"

# Subdirectories for photos
INSPECTION_PHOTOS_STAGING_DIR = INSPECTION_PHOTOS_DIR / "STAGING"
INSPECTION_PHOTOS_PROCESSED_DIR = INSPECTION_PHOTOS_DIR / "PROCESSED"

# Function to get paths as strings (for compatibility with older code)
def get_inspection_photos_dir() -> str:
    """Get inspection photos directory as string"""
    return str(INSPECTION_PHOTOS_DIR)

def get_inspection_reports_dir() -> str:
    """Get inspection reports directory as string"""
    return str(INSPECTION_REPORTS_DIR)

def get_inspection_photos_staging_dir() -> str:
    """Get inspection photos STAGING directory as string"""
    return str(INSPECTION_PHOTOS_STAGING_DIR)

def get_inspection_photos_processed_dir() -> str:
    """Get inspection photos PROCESSED directory as string"""
    return str(INSPECTION_PHOTOS_PROCESSED_DIR)

# Ensure directories exist on import
def ensure_directories_exist():
    """Create directories if they don't exist"""
    INSPECTION_PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    INSPECTION_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    INSPECTION_PHOTOS_STAGING_DIR.mkdir(parents=True, exist_ok=True)
    INSPECTION_PHOTOS_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# Auto-create directories when module is imported
ensure_directories_exist()

