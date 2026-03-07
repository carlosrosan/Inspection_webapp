#!/usr/bin/env python3
"""
Digit Prediction Service - Integrates MNIST detector with Django inspections

This service runs digit prediction on inspection photos for specific photo IDs
(198F, 33F, 48F) and stores results in the DigitPrediction model.

The service uses the trained MNIST model to detect handwritten digits on
metal plaque photos from the Conuar inspection system.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional, Tuple, List, Dict

# Setup Django if needed
try:
    import django
    django.apps.apps.check_apps_ready()
except Exception:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()

# Configure logger
logger = logging.getLogger('etl.digit_prediction_service')

# Path to the MNIST model
MODEL_DIR = Path(__file__).parent / 'digit_prediction_models'
MODEL_PATH = MODEL_DIR / 'mnist_model.keras'

# Photo IDs that should have digit prediction
TARGET_PHOTO_IDS = {'198F', '33F', '48F'}

# STAGING_FOLDER for digit segmentation preview (troubleshooting)
# Workspace root = parent of conuar_webapp
_ETL_DIR = Path(__file__).resolve().parent
_WEBAPP_DIR = _ETL_DIR.parent
_WORKSPACE_ROOT = _WEBAPP_DIR.parent
STAGING_FOLDER = _WORKSPACE_ROOT / 'conuar_webapp/media/inspection_photos/STAGING'
DIGIT_PREVIEW_SUBDIR = _WORKSPACE_ROOT / 'conuar_webapp/media/inspection_photos/digit_preview'

# Import OpenCV and related libraries
try:
    import cv2
    import numpy as np
except ImportError:
    logger.error("OpenCV and NumPy not installed. Run: pip install opencv-python numpy")
    cv2 = None
    np = None

# Import TensorFlow/Keras
try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers
except ImportError:
    logger.error("TensorFlow not installed. Run: pip install tensorflow")
    keras = None


# =============================================================================
# IMAGE PROCESSING FUNCTIONS (adapted from image_cutter.py and edge_detection.py)
# =============================================================================

def rotate_image_clockwise_90(image):
    """Rotate image 90 degrees clockwise."""
    return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)


def crop_image(image, x1, y1, x2, y2):
    """
    Crop a rectangle from the image.
    
    Args:
        image: Input image (numpy array)
        x1, y1: Top-left corner coordinates
        x2, y2: Bottom-right corner coordinates
    
    Returns:
        Cropped image
    """
    height, width = image.shape[:2]
    
    # Validate and clamp coordinates
    x1 = max(0, min(x1, width - 1))
    x2 = max(0, min(x2, width))
    y1 = max(0, min(y1, height - 1))
    y2 = max(0, min(y2, height))
    
    if x2 <= x1 or y2 <= y1:
        return None
    
    return image[y1:y2, x1:x2]


def adjust_brightness_contrast(image, brightness=20, contrast=1.5):
    """Adjust brightness and contrast of an image."""
    adjusted = image.astype(np.float32)
    adjusted = adjusted * contrast + brightness
    adjusted = np.clip(adjusted, 0, 255).astype(np.uint8)
    return adjusted


def apply_gaussian_blur(image, kernel_size=5):
    """Apply Gaussian blur to reduce texture noise."""
    if kernel_size <= 0:
        return image
    if kernel_size % 2 == 0:
        kernel_size += 1
    return cv2.GaussianBlur(image, (kernel_size, kernel_size), 0)


def preprocess_for_edge_detection(image, brightness=20, contrast=1.5,
                                   canny_low=20, canny_high=100,
                                   gaussian_blur=5, negative=False):
    """
    Preprocess image to extract carved edges as white on black background.
    Optimized for knife-carved letters and numbers on metal plaques.
    """
    # Step 0: Apply negative transformation if enabled (invert colors)
    if negative:
        image = cv2.bitwise_not(image)
    
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Step 1: Adjust brightness and contrast
    adjusted = adjust_brightness_contrast(gray, brightness, contrast)
    
    # Step 2: Denoise to reduce metal texture noise (bilateral filter)
    denoised = cv2.bilateralFilter(adjusted, 9, 75, 75)
    
    # Step 3: Apply Gaussian blur to further reduce texture noise
    blurred = apply_gaussian_blur(denoised, gaussian_blur)
    
    # Step 4: Enhance contrast using CLAHE
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(blurred)
    
    # Step 5: Apply Canny edge detection
    edges = cv2.Canny(enhanced, canny_low, canny_high)
    
    # Step 6: Dilate edges slightly
    kernel = np.ones((2, 2), np.uint8)
    dilated = cv2.dilate(edges, kernel, iterations=1)
    
    # Step 7: Apply morphological closing
    kernel_close = np.ones((3, 3), np.uint8)
    closed = cv2.morphologyEx(dilated, cv2.MORPH_CLOSE, kernel_close)
    
    return closed


# =============================================================================
# PHOTO ID PARAMETERS (from config.py)
# =============================================================================

PHOTO_ID_PARAMS = {
    'default': {
        'brightness': 20,
        'contrast': 1.5,
        'canny_low': 20,
        'canny_high': 100,
        'gaussian_blur': 5,
        'negative': False,
    },
    '198F': {
        'brightness': 20,
        'contrast': 1.5,
        'canny_low': 15,
        'canny_high': 100,
        'gaussian_blur': 5,
        'negative': False,
    },
    '33F': {
        'brightness': 20,
        'contrast': 1.5,
        'canny_low': 20,
        'canny_high': 100,
        'gaussian_blur': 5,
        'negative': False,
    },
    '48F': {
        'brightness': 20,
        'contrast': 1.5,
        'canny_low': 20,
        'canny_high': 100,
        'gaussian_blur': 5,
        'negative': False,
    },
}

# Default crop region
DEFAULT_CROP = {
    'x1': 750,
    'y1': 900,
    'x2': 1400,
    'y2': 1100 #1500
}


def get_params_for_photo_id(photo_id: str) -> Dict:
    """Get preprocessing parameters for a specific photo ID."""
    if photo_id and photo_id in PHOTO_ID_PARAMS:
        return PHOTO_ID_PARAMS[photo_id].copy()
    return PHOTO_ID_PARAMS['default'].copy()


# =============================================================================
# DIGIT SEGMENTATION (from region_detection.py)
# =============================================================================

def segment_digits(image, is_preprocessed=False, min_area=100, max_area=50000):
    """
    Segment individual digits from an image using contour detection.
    
    Args:
        image: Input image (BGR or grayscale)
        is_preprocessed: If True, image is already edge-detected (white on black)
        min_area: Minimum contour area to consider
        max_area: Maximum contour area to consider
    
    Returns:
        List of (digit_image, bounding_box) tuples, sorted left to right
    """
    if image is None:
        return []
    
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # If not preprocessed, apply edge detection
    if not is_preprocessed:
        gray = preprocess_for_edge_detection(gray)
    
    # Find contours
    contours, _ = cv2.findContours(gray, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Filter and sort contours
    digit_regions = []
    
    for contour in contours:
        area = cv2.contourArea(contour)
        
        # Filter by area
        if area < min_area or area > max_area:
            continue
        
        # Get bounding box
        x, y, w, h = cv2.boundingRect(contour)
        
        # Filter by aspect ratio (digits should be taller than wide)
        aspect_ratio = h / w if w > 0 else 0
        if aspect_ratio < 0.5 or aspect_ratio > 5.0:
            continue
        
        # Extract digit region with padding
        padding = 5
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(gray.shape[1], x + w + padding)
        y2 = min(gray.shape[0], y + h + padding)
        
        digit_img = gray[y1:y2, x1:x2]
        
        if digit_img.size > 0:
            digit_regions.append((digit_img, (x1, y1, x2, y2)))
    
    # Sort by x-coordinate (left to right)
    digit_regions.sort(key=lambda x: x[1][0])
    
    return digit_regions


# =============================================================================
# MNIST MODEL CLASS
# =============================================================================

class MNISTModel:
    """MNIST digit recognition model."""
    
    MNIST_SIZE = 28
    
    def __init__(self):
        self.model = None
        self.input_shape = (self.MNIST_SIZE, self.MNIST_SIZE, 1)
        self.num_classes = 10
        self._model_loaded = False
    
    def load_model(self) -> bool:
        """Load a previously trained model."""
        if not MODEL_PATH.exists():
            logger.error(f"Model not found at {MODEL_PATH}")
            return False
        
        try:
            self.model = keras.models.load_model(str(MODEL_PATH))
            self._model_loaded = True
            logger.info(f"Model loaded from: {MODEL_PATH}")
            return True
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return False
    
    def predict_digit_raw(self, digit_image) -> Tuple[int, float]:
        """
        Predict a digit without edge detection preprocessing.
        Use this for already preprocessed images.
        
        Returns:
            Tuple of (predicted_digit, confidence)
        """
        if self.model is None:
            return -1, 0.0
        
        # Resize to MNIST size with centering
        h, w = digit_image.shape[:2]
        scale = min(20.0 / w, 20.0 / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        
        if new_w <= 0 or new_h <= 0:
            return -1, 0.0
        
        resized = cv2.resize(digit_image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        
        canvas = np.zeros((self.MNIST_SIZE, self.MNIST_SIZE), dtype=np.uint8)
        x_offset = (self.MNIST_SIZE - new_w) // 2
        y_offset = (self.MNIST_SIZE - new_h) // 2
        canvas[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = resized
        
        normalized = canvas.astype('float32') / 255.0
        preprocessed = np.expand_dims(normalized, axis=(0, -1))
        
        predictions = self.model.predict(preprocessed, verbose=0)
        predicted_class = np.argmax(predictions[0])
        confidence = float(predictions[0][predicted_class])
        
        return int(predicted_class), confidence


# =============================================================================
# DIGIT PREDICTION SERVICE
# =============================================================================

class DigitPredictionService:
    """Service for running MNIST digit prediction on inspection photos"""
    
    def __init__(self):
        self.model: Optional[MNISTModel] = None
        self._model_loaded = False
    
    def _ensure_model_loaded(self) -> bool:
        """Load the MNIST model if not already loaded"""
        if self._model_loaded and self.model is not None:
            return True
        
        if cv2 is None or np is None or keras is None:
            logger.error("Required libraries (OpenCV, NumPy, TensorFlow) not available")
            return False
        
        try:
            self.model = MNISTModel()
            if self.model.load_model():
                self._model_loaded = True
                logger.info("MNIST model loaded successfully")
                return True
            else:
                logger.error("Failed to load MNIST model")
                return False
        except Exception as e:
            logger.error(f"Error loading MNIST model: {e}")
            return False
    
    def extract_photo_id_from_filename(self, filename: str) -> str:
        """
        Extract photo ID from filename (3rd field when split by '-')
        Example: "COMPLETO-UNO-198F-231225_134953-NOK753.bmp" -> "198F"
        """
        name_without_ext = Path(filename).stem
        parts = name_without_ext.split('-')
        if len(parts) >= 3:
            return parts[2]
        return ""
    
    def should_process_photo(self, filename: str) -> Tuple[bool, str]:
        """
        Check if a photo should have digit prediction based on photo ID.
        Returns (should_process, photo_id)
        """
        photo_id = self.extract_photo_id_from_filename(filename)
        should_process = photo_id in TARGET_PHOTO_IDS
        return should_process, photo_id

    def _save_digit_preview(
        self,
        image_path: Path,
        edges,
        digit_regions: List[Tuple],
        predictions: List[str],
        confidences: List[float],
        detected_numbers: str,
    ) -> Optional[Path]:
        """
        Save digit segmentation preview to STAGING_FOLDER for troubleshooting.
        Output base name: <image_stem>_<detected_numbers> (e.g. myphoto_74025).
        Creates STAGING_FOLDER/digit_preview/<base_name>.png (composite image) and
        STAGING_FOLDER/digit_preview/<base_name>/ with edges.png and digit_00.png, ...

        Returns:
            Path to the preview directory, or None if saving failed.
        """
        if cv2 is None or np is None:
            return None
        # Sanitize detected_numbers for use in filename (no path chars)
        safe_numbers = (detected_numbers or 'none').replace('/', '_').replace('\\', '_')
        base_name = f"{image_path.stem}_{safe_numbers}"
        preview_dir = STAGING_FOLDER / DIGIT_PREVIEW_SUBDIR / base_name
        try:
            preview_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.warning(f"Could not create digit preview dir {preview_dir}: {e}")
            return None
        try:
            edges_path = preview_dir / 'edges.png'
            cv2.imwrite(str(edges_path), edges)
            for i, (digit_img, _bbox) in enumerate(digit_regions):
                pred = predictions[i] if i < len(predictions) else '?'
                conf = confidences[i] if i < len(confidences) else 0.0
                name = f"digit_{i:02d}_pred{pred}_conf{conf:.2f}.png"
                digit_path = preview_dir / name
                cv2.imwrite(str(digit_path), digit_img)
            # Output image: original name + _ + detected_numbers + .png
            composite_path = STAGING_FOLDER / DIGIT_PREVIEW_SUBDIR / f"{base_name}.png"
            composite = self._build_preview_composite(edges, digit_regions, predictions, confidences)
            if composite is None and edges is not None:
                composite = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
            if composite is not None:
                cv2.imwrite(str(composite_path), composite)
            logger.info(f"Digit preview saved to {preview_dir} and {composite_path}")
            return preview_dir
        except Exception as e:
            logger.warning(f"Could not save digit preview: {e}")
            return None

    def _build_preview_composite(self, edges, digit_regions, predictions, confidences):
        """Build a single composite image (edges + row of digits) for preview. Returns BGR image or None."""
        if cv2 is None or np is None or not digit_regions:
            return None
        try:
            # Scale for consistent display (e.g. max height 120 for digits)
            max_h = 120
            digit_imgs = []
            for i, (digit_img, _) in enumerate(digit_regions):
                h, w = digit_img.shape[:2]
                scale = max_h / max(h, 1)
                new_w = max(1, int(w * scale))
                new_h = max(1, int(h * scale))
                resized = cv2.resize(digit_img, (new_w, new_h), interpolation=cv2.INTER_AREA)
                if len(resized.shape) == 2:
                    resized = cv2.cvtColor(resized, cv2.COLOR_GRAY2BGR)
                digit_imgs.append(resized)
            row_digits = np.hstack(digit_imgs)
            # Resize edges to similar height for a compact layout
            eh, ew = edges.shape[:2]
            target_h = max(max_h, min(200, eh))
            scale_e = target_h / max(eh, 1)
            edges_resized = cv2.resize(edges, (int(ew * scale_e), target_h), interpolation=cv2.INTER_AREA)
            edges_bgr = cv2.cvtColor(edges_resized, cv2.COLOR_GRAY2BGR)
            # Stack: edges on top, digits below (pad to same width)
            w_max = max(edges_bgr.shape[1], row_digits.shape[1])
            pad_l = (w_max - edges_bgr.shape[1]) // 2
            pad_r = w_max - edges_bgr.shape[1] - pad_l
            edges_padded = cv2.copyMakeBorder(edges_bgr, 0, 0, pad_l, pad_r, cv2.BORDER_CONSTANT, value=0)
            pad_l = (w_max - row_digits.shape[1]) // 2
            pad_r = w_max - row_digits.shape[1] - pad_l
            row_padded = cv2.copyMakeBorder(row_digits, 0, 0, pad_l, pad_r, cv2.BORDER_CONSTANT, value=0)
            composite = np.vstack([edges_padded, row_padded])
            return composite
        except Exception:
            return None

    def detect_numbers_in_image(self, image_path: Path, params: Dict = None, save_digit_preview: bool = True) -> Dict:
        """
        Detect digits in an image file.
        
        Args:
            image_path: Path to the image file
            params: Preprocessing parameters (optional)
            save_digit_preview: If True (default), save preview to STAGING_FOLDER/digit_preview/
                as <image_stem>_<detected_numbers>.png and folder with edges/digit crops.
        
        Returns:
            Dictionary with detection results
        """
        if not self._ensure_model_loaded():
            return {
                'detected_numbers': 'ERROR',
                'letter': '',
                'digits': ['', '', '', '', ''],
                'details': 'Model not loaded',
                'error': 'Model not loaded'
            }
        
        # Load image
        image = cv2.imread(str(image_path))
        if image is None:
            return {
                'detected_numbers': 'ERROR',
                'letter': '',
                'digits': ['', '', '', '', ''],
                'details': f'Could not read image: {image_path}',
                'error': f'Could not read image: {image_path}'
            }
        
        # Get preprocessing parameters
        if params is None:
            photo_id = self.extract_photo_id_from_filename(image_path.name)
            params = get_params_for_photo_id(photo_id)
        
        # Rotate image 90 degrees clockwise
        rotated = rotate_image_clockwise_90(image)
        
        # Crop to digit region
        crop = DEFAULT_CROP
        cropped = crop_image(rotated, crop['x1'], crop['y1'], crop['x2'], crop['y2'])
        
        if cropped is None or cropped.size == 0:
            return {
                'detected_numbers': 'ERROR',
                'letter': '',
                'digits': ['', '', '', '', ''],
                'details': 'Crop failed',
                'error': 'Crop failed'
            }
        
        # Apply edge detection preprocessing
        edges = preprocess_for_edge_detection(
            cropped,
            brightness=params['brightness'],
            contrast=params['contrast'],
            canny_low=params['canny_low'],
            canny_high=params['canny_high'],
            gaussian_blur=params.get('gaussian_blur', 5),
            negative=params.get('negative', False)
        )
        
        # Segment digits
        digit_regions = segment_digits(edges, is_preprocessed=True)
        
        if not digit_regions:
            if save_digit_preview:
                self._save_digit_preview(image_path, edges, [], [], [], 'none')
            return {
                'detected_numbers': 'none',
                'letter': '',
                'digits': ['', '', '', '', ''],
                'details': 'No digit regions found',
                'error': None
            }
        
        # Predict each digit
        predictions = []
        confidences = []
        details = []
        
        for i, (digit_img, bbox) in enumerate(digit_regions):
            predicted_class, confidence = self.model.predict_digit_raw(digit_img)
            predictions.append(str(predicted_class) if predicted_class >= 0 else '')
            confidences.append(confidence)
            details.append(f"Digit {i}: {predicted_class} (conf: {confidence:.2f})")
        
        detected_numbers = ''.join(predictions)
        # Save digit segmentation preview (STAGING_FOLDER/digit_preview/<stem>_<detected_numbers>.png and folder)
        if save_digit_preview:
            self._save_digit_preview(image_path, edges, digit_regions, predictions, confidences, detected_numbers)
        
        # Parse into letter and digits (first is letter, rest are digits)
        letter = ''
        all_digits = predictions[:]  # All predictions as digits for digits_only mode
        
        # Limit to 5 digits for output
        digits_for_output = all_digits[:5]
        while len(digits_for_output) < 5:
            digits_for_output.append('')
        
        # Calculate average confidence
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        return {
            'detected_numbers': detected_numbers,
            'letter': letter,
            'digits': digits_for_output,
            'details': ' | '.join(details),
            'average_confidence': avg_confidence,
            'error': None
        }
    
    def predict_for_photo(self, photo, photo_id: str):
        """
        Run digit prediction for a single InspectionPhoto and save to database.
        
        Args:
            photo: InspectionPhoto instance
            photo_id: Extracted photo ID from filename
        
        Returns:
            DigitPrediction instance or None
        """
        from main.models import DigitPrediction
        
        # Check if prediction already exists
        if hasattr(photo, 'digit_prediction'):
            try:
                existing = photo.digit_prediction
                if existing:
                    logger.debug(f"Prediction already exists for photo {photo.id}")
                    return existing
            except DigitPrediction.DoesNotExist:
                pass
        
        # Get the full path to the photo
        try:
            from django.conf import settings
            photo_full_path = Path(settings.MEDIA_ROOT) / photo.photo.name
        except Exception as e:
            logger.error(f"Error getting photo path: {e}")
            return None
        
        if not photo_full_path.exists():
            # Create error record
            prediction = DigitPrediction.objects.create(
                inspection_photo=photo,
                photo_id=photo_id,
                processing_error=f"Photo file not found: {photo_full_path}"
            )
            return prediction
        
        # Run detection (digit preview saved by default; set env DIGIT_PREVIEW_SAVE=0 to disable)
        save_preview = os.environ.get('DIGIT_PREVIEW_SAVE', '1').strip().lower() not in ('0', 'false', 'no')
        logger.info(f"Running digit prediction for photo: {photo_full_path.name} (ID: {photo_id})")
        result = self.detect_numbers_in_image(photo_full_path, save_digit_preview=save_preview)
        
        if result.get('error'):
            prediction = DigitPrediction.objects.create(
                inspection_photo=photo,
                photo_id=photo_id,
                processing_error=result['error']
            )
            return prediction
        
        # Extract digits from result
        digits = result.get('digits', ['', '', '', '', ''])
        
        # Create prediction record
        prediction = DigitPrediction.objects.create(
            inspection_photo=photo,
            photo_id=photo_id,
            detected_numbers=result.get('detected_numbers', ''),
            letter=result.get('letter', ''),
            digit_1=digits[0] if len(digits) > 0 else '',
            digit_2=digits[1] if len(digits) > 1 else '',
            digit_3=digits[2] if len(digits) > 2 else '',
            digit_4=digits[3] if len(digits) > 3 else '',
            digit_5=digits[4] if len(digits) > 4 else '',
            average_confidence=result.get('average_confidence'),
            prediction_details=result.get('details', '')
        )
        
        logger.info(
            f"Digit prediction saved for photo {photo.id} (ID={photo_id}): "
            f"{result.get('detected_numbers', 'none')}"
        )
        return prediction
    
    def process_inspection_photos(self, inspection_id: int) -> int:
        """
        Process all photos for an inspection that match target photo IDs.
        
        Args:
            inspection_id: ID of the inspection to process
        
        Returns:
            Count of predictions made
        """
        from main.models import Inspection
        
        try:
            inspection = Inspection.objects.get(id=inspection_id)
        except Inspection.DoesNotExist:
            logger.warning(f"Inspection {inspection_id} not found")
            return 0
        
        predictions_made = 0
        
        for photo in inspection.photos.all():
            filename = Path(photo.photo.name).name
            should_process, photo_id = self.should_process_photo(filename)
            
            if should_process:
                try:
                    prediction = self.predict_for_photo(photo, photo_id)
                    if prediction:
                        predictions_made += 1
                except Exception as e:
                    logger.error(f"Error processing photo {photo.id}: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
        
        if predictions_made > 0:
            logger.info(
                f"Made {predictions_made} digit predictions for inspection {inspection_id}"
            )
        
        return predictions_made


# =============================================================================
# SINGLETON AND CONVENIENCE FUNCTIONS
# =============================================================================

_service_instance: Optional[DigitPredictionService] = None


def get_digit_prediction_service() -> DigitPredictionService:
    """Get or create the digit prediction service singleton"""
    global _service_instance
    if _service_instance is None:
        _service_instance = DigitPredictionService()
    return _service_instance


def predict_digits_for_inspection(inspection_id: int) -> int:
    """
    Convenience function to run digit prediction for an inspection.
    Call this after inspection photos are linked.
    
    Args:
        inspection_id: ID of the inspection
    
    Returns:
        Number of predictions made
    """
    service = get_digit_prediction_service()
    return service.process_inspection_photos(inspection_id)


if __name__ == '__main__':
    # Test the service
    import argparse
    
    parser = argparse.ArgumentParser(description='Digit Prediction Service')
    parser.add_argument('--inspection', type=int, help='Inspection ID to process')
    parser.add_argument('--image', type=str, help='Single image path to process')
    parser.add_argument('--no-preview', action='store_true', help='Do not save digit segmentation preview')
    
    args = parser.parse_args()
    
    service = DigitPredictionService()
    
    if args.image:
        # Process single image (preview saved by default unless --no-preview)
        image_path = Path(args.image)
        if image_path.exists():
            result = service.detect_numbers_in_image(image_path, save_digit_preview=not args.no_preview)
            print(f"Detection result: {result}")
        else:
            print(f"Image not found: {image_path}")
    elif args.inspection:
        # Process all photos for an inspection
        count = service.process_inspection_photos(args.inspection)
        print(f"Made {count} predictions for inspection {args.inspection}")
    else:
        print("Usage: python digit_prediction_service.py --inspection <ID> or --image <path>")
