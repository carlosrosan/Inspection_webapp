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
# Using the transfer-learning model fine-tuned on real metal-plaque digit crops.
MODEL_DIR = Path(__file__).parent / 'digit_prediction_models'
MODEL_PATH = MODEL_DIR / 'mnist_with_transfer_learning.keras'

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
        'canny_low': 50,    # tighter edge threshold for deep knife carvings
        'canny_high': 150,
        'gaussian_blur': 11,
        'negative': True,   # invert: carved grooves become white on black (matches training data)
    },
    '48F': {
        'brightness': 20,
        'contrast': 1.5,
        'canny_low': 50,
        'canny_high': 150,
        'gaussian_blur': 11,
        'negative': True,
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

def segment_digits(image, is_preprocessed=False):
    """
    Segment individual digits from an edge-detected image using contour detection.
    Uses absolute pixel thresholds calibrated from 90 hand-labeled digit crops:
        Width:  60–109 px  (avg 83 px)
        Height: 70–186 px  (avg 138 px)

    Returns:
        List of (digit_image, bounding_box) tuples sorted left to right.
    """
    if image is None:
        return []

    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    if not is_preprocessed:
        gray = preprocess_for_edge_detection(gray)

    # Morphological operations to connect nearby edge pixels
    kernel_dilate = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(gray, kernel_dilate, iterations=2)
    kernel_close = np.ones((5, 5), np.uint8)
    closed = cv2.morphologyEx(dilated, cv2.MORPH_CLOSE, kernel_close)

    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # ── Absolute pixel thresholds (calibrated from labeled crops) ─────────────
    MIN_DIGIT_W    = 50    # px  (measured min 60, −10 margin)
    MAX_DIGIT_W    = 130   # px  (measured max 109, +21 margin)
    MIN_DIGIT_H    = 60    # px  (measured min 70, −10 margin)
    MAX_DIGIT_H    = 210   # px  (measured max 186, +24 margin)
    MIN_DIGIT_AREA = 3000  # px² (measured min 60×70 = 4200, −1200 margin)
    MAX_DIGIT_AREA = 30000 # px² (measured max 109×186 = 20274, +9726 margin)

    image_h, image_w = gray.shape
    max_area = min(MAX_DIGIT_AREA, image_h * image_w * 0.35)

    digit_regions = []

    for contour in contours:
        area = cv2.contourArea(contour)
        if not (MIN_DIGIT_AREA < area < max_area):
            continue

        # Complexity filters — reject noise and merged blobs
        perimeter = cv2.arcLength(contour, True)
        if perimeter > 0:
            circularity = 4 * np.pi * area / (perimeter * perimeter)
            if circularity < 0.05:
                continue
            if perimeter / np.sqrt(area) > 20:
                continue

        x, y, w, h = cv2.boundingRect(contour)

        if not (MIN_DIGIT_W <= w <= MAX_DIGIT_W):
            continue
        if not (MIN_DIGIT_H <= h <= MAX_DIGIT_H):
            continue

        aspect_ratio = h / w if w > 0 else 0
        if not (0.5 < aspect_ratio < 4.0):
            continue

        # Pad the extracted region
        padding_x = int(w * 0.15)
        padding_y = int(h * 0.15)
        x1 = max(0, x - padding_x)
        y1 = max(0, y - padding_y)
        x2 = min(image_w, x + w + padding_x)
        y2 = min(image_h, y + h + padding_y)

        digit_img = gray[y1:y2, x1:x2]
        if digit_img.size > 0:
            digit_regions.append((digit_img, (x1, y1, x2, y2)))

    # Remove overlapping regions (keep larger)
    digit_regions.sort(key=lambda r: (r[1][2]-r[1][0]) * (r[1][3]-r[1][1]), reverse=True)
    kept = []
    for region, bbox in digit_regions:
        x1, y1, x2, y2 = bbox
        overlapping = False
        for _, (kx1, ky1, kx2, ky2) in kept:
            ix1, iy1 = max(x1, kx1), max(y1, ky1)
            ix2, iy2 = min(x2, kx2), min(y2, ky2)
            if ix1 < ix2 and iy1 < iy2:
                inter = (ix2-ix1) * (iy2-iy1)
                smaller = min((x2-x1)*(y2-y1), (kx2-kx1)*(ky2-ky1))
                if inter / smaller > 0.3:
                    overlapping = True
                    break
        if not overlapping:
            kept.append((region, bbox))

    # Sort left to right
    kept.sort(key=lambda r: r[1][0])
    return kept


# =============================================================================
# ADAPTIVE PIPELINE HELPERS
# =============================================================================

def _find_digit_band(edge_image, padding_frac=0.20,
                     peak_threshold=0.10, drop_threshold=0.30):
    """
    Find the vertical band with the highest edge density (the digit zone) and
    return (y1, y2) row indices that strip the noisy metallic-grain region.

    Applied to the edge-detected image AFTER preprocess_for_edge_detection()
    and BEFORE segment_digits(), so the segmenter only sees the digit zone.
    Falls back to (0, H) when no clear signal is found.
    """
    if edge_image is None:
        return 0, 0
    H, W = edge_image.shape[:2]
    if H == 0 or W == 0:
        return 0, H

    row_density = np.sum(edge_image > 0, axis=1).astype(np.float32)
    win = max(3, H // 20)
    kernel = np.ones(win, dtype=np.float32) / win
    smoothed = np.convolve(row_density, kernel, mode='same')

    peak_val = float(smoothed.max())
    if peak_val == 0:
        return 0, H

    peak_row = int(np.argmax(smoothed))
    y1 = 0
    for r in range(peak_row, -1, -1):
        if smoothed[r] < peak_val * peak_threshold:
            y1 = max(0, r - 2)
            break
    y2 = H
    for r in range(peak_row, H):
        if smoothed[r] < peak_val * drop_threshold:
            y2 = r
            break

    digit_height = max(1, y2 - y1)
    y2_padded = min(H, y2 + int(digit_height * padding_frac))
    return y1, y2_padded


def _auto_crop_between_rails(img, dark_thresh=80, bright_thresh=220,
                              dark_frac=0.08, bright_frac=0.10,
                              min_height=30):
    """
    Trim structural horizontal lines from the cropped inspection image:
      - Rows with many dark pixels  (metal rail)   removed at TOP
      - Rows with many bright pixels (computer text) removed at BOTTOM

    Applied to the RAW cropped image BEFORE edge detection, so the edge
    detector only sees the digit-engraving surface.

    Returns (trimmed_image, y1, y2) or (original, 0, H) if no lines found.
    """
    if img is None or img.size == 0:
        H = img.shape[0] if img is not None else 0
        return img, 0, H

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    H, W = gray.shape

    row_dark   = np.mean(gray < dark_thresh,   axis=1).astype(float)
    row_bright = np.mean(gray > bright_thresh, axis=1).astype(float)

    # 1a. skip dark rows at the TOP (top rail) — scan top 30 % without break
    y1 = 0
    top_limit = max(1, H * 3 // 10)
    for r in range(top_limit):
        if row_dark[r] >= dark_frac:
            y1 = r + 1

    # 1b. skip bright rows right after the dark zone (transition strip)
    window = max(1, H // 10)
    for r in range(y1, min(y1 + window, H)):
        if row_bright[r] >= bright_frac:
            y1 = r + 1
        else:
            break

    # 2. find first dark row below y1 (bottom rail)
    y2 = H
    for r in range(y1, H):
        if row_dark[r] >= dark_frac:
            y2 = r
            break

    height = y2 - y1
    if height < min_height or height < H * 0.15:
        return img, 0, H   # no usable lines found

    result = img[y1:y2, :] if img.ndim == 2 else img[y1:y2, :, :]
    return result, y1, y2


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

def _log_dependency_status() -> None:
    """Log which optional dependencies are missing so errors are visible at startup."""
    missing = []
    if cv2 is None:
        missing.append("opencv-python  →  pip install opencv-python")
    if np is None:
        missing.append("numpy          →  pip install numpy")
    if keras is None:
        missing.append("tensorflow     →  pip install tensorflow")
    if not MODEL_PATH.exists():
        missing.append(f"model file not found: {MODEL_PATH}")
    if missing:
        logger.warning(
            "[digit_prediction_service] Predicciones deshabilitadas — dependencias faltantes:\n  "
            + "\n  ".join(missing)
        )
    else:
        logger.info("[digit_prediction_service] Todas las dependencias disponibles.")


class DigitPredictionService:
    """Service for running MNIST digit prediction on inspection photos"""

    def __init__(self):
        self.model: Optional[MNISTModel] = None
        self._model_loaded = False
        _log_dependency_status()

    def _ensure_model_loaded(self) -> bool:
        """Load the MNIST model if not already loaded"""
        if self._model_loaded and self.model is not None:
            return True

        if cv2 is None or np is None or keras is None:
            missing = [
                lib for lib, mod in [("opencv-python", cv2), ("numpy", np), ("tensorflow", keras)]
                if mod is None
            ]
            logger.error(
                f"Predicción deshabilitada — librerías no instaladas: {', '.join(missing)}"
            )
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
        
        # ── Step 1: rotate 90° CW ────────────────────────────────────────────
        rotated = rotate_image_clockwise_90(image)

        # ── Step 2: standard crop to digit region ────────────────────────────
        crop    = DEFAULT_CROP
        cropped = crop_image(rotated, crop['x1'], crop['y1'], crop['x2'], crop['y2'])

        if cropped is None or cropped.size == 0:
            return {
                'detected_numbers': 'ERROR',
                'letter': '',
                'digits': ['', '', '', '', ''],
                'details': 'Crop failed',
                'error': 'Crop failed'
            }

        # ── Step 3: auto-crop rails (raw image) ──────────────────────────────
        # Removes dark metal-rail rows (top) and bright computer-text rows
        # (bottom) before edge detection so the edge detector sees only the
        # digit-engraving surface.
        rail_cropped, rc_y1, rc_y2 = _auto_crop_between_rails(cropped)
        if rc_y2 - rc_y1 > 30:
            logger.debug(f"Rail-crop: rows {rc_y1}–{rc_y2} kept "
                         f"({rc_y2-rc_y1}/{cropped.shape[0]} px)")
            cropped = rail_cropped

        # ── Step 4: edge detection ────────────────────────────────────────────
        edges = preprocess_for_edge_detection(
            cropped,
            brightness=params['brightness'],
            contrast=params['contrast'],
            canny_low=params['canny_low'],
            canny_high=params['canny_high'],
            gaussian_blur=params.get('gaussian_blur', 5),
            negative=params.get('negative', False)
        )

        # ── Step 5: adaptive digit-zone crop (edge image) ─────────────────────
        # Finds the row-band with the highest edge density and strips the noisy
        # metallic-grain region below the digits.
        orig_h = edges.shape[0]
        dy1, dy2 = _find_digit_band(edges)
        if dy2 - dy1 < orig_h:
            logger.debug(f"Digit-band crop: rows {dy1}–{dy2} "
                         f"(kept {dy2-dy1}/{orig_h} px)")
            edges   = edges[dy1:dy2, :]
            cropped = (cropped[dy1:dy2, :] if cropped.ndim == 2
                       else cropped[dy1:dy2, :, :])

        # ── Step 6: segment contours ──────────────────────────────────────────
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

        # ── Step 7: predict all regions, keep top-5 by confidence ────────────
        all_preds = []
        for digit_img, bbox in digit_regions:
            predicted_class, confidence = self.model.predict_digit_raw(digit_img)
            all_preds.append((bbox, str(predicted_class) if predicted_class >= 0 else '',
                              float(confidence)))

        # Select top-5 most confident, then re-sort left → right for reading order
        top5 = sorted(all_preds, key=lambda r: r[2], reverse=True)[:5]
        top5 = sorted(top5, key=lambda r: r[0][0])   # sort by x1

        predictions = [r[1] for r in top5]
        confidences = [r[2] for r in top5]
        details     = [f"Digit {i}: {r[1]} (conf: {r[2]:.2f})"
                       for i, r in enumerate(top5)]

        detected_numbers = ''.join(predictions)

        if save_digit_preview:
            # Pass the top-5 regions for preview (aligned with predictions)
            top5_regions = [(None, r[0]) for r in top5]
            self._save_digit_preview(image_path, edges, top5_regions,
                                     predictions, confidences, detected_numbers)

        # ── Step 8: build output ──────────────────────────────────────────────
        digits_for_output = (predictions + ['', '', '', '', ''])[:5]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return {
            'detected_numbers': detected_numbers,
            'letter': '',
            'digits': digits_for_output,
            'details': ' | '.join(details),
            'average_confidence': avg_confidence,
            'error': None
        }
    
    def predict_for_photo(self, photo, photo_id: str):
        """
        Run digit prediction for a single InspectionPhoto and save to database.

        Existing predictions are returned as-is only when detected_numbers is
        already ≤ 5 characters (i.e. produced by the current top-5 pipeline).
        Stale records with > 5 digits (created by an older version of the
        service that joined all detected regions without the top-5 filter) are
        re-predicted and updated via update_or_create.

        Args:
            photo: InspectionPhoto instance
            photo_id: Extracted photo ID from filename

        Returns:
            DigitPrediction instance or None
        """
        from main.models import DigitPrediction

        # Return existing prediction only when it is valid:
        #   - detected_numbers is ≤ 5 chars (current pipeline limit), AND
        #   - processing_error is empty (not a stale error record).
        # Stale error records are retried so that fixing a missing dependency
        # (e.g. installing TensorFlow) automatically re-runs prediction.
        existing = None
        try:
            existing = photo.digit_prediction
            if existing:
                if existing.processing_error:
                    logger.info(
                        f"Re-intentando predicción para foto {photo.id} "
                        f"(error previo: {existing.processing_error!r})"
                    )
                    # fall through to re-run
                elif len(existing.detected_numbers) <= 5:
                    logger.debug(f"Predicción válida ya existe para foto {photo.id}")
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
            error_msg = f"Archivo de foto no encontrado: {photo_full_path}"
            logger.warning(
                f"[PREDICTION ERROR] foto {photo.id} (ID={photo_id}, "
                f"inspección={photo.inspection_id}): {error_msg}"
            )
            if existing:
                return existing  # cannot re-process; keep whatever we have
            prediction, _ = DigitPrediction.objects.update_or_create(
                inspection_photo=photo,
                defaults={'photo_id': photo_id, 'processing_error': error_msg},
            )
            return prediction

        # Run detection (digit preview saved by default; set env DIGIT_PREVIEW_SAVE=0 to disable)
        save_preview = os.environ.get('DIGIT_PREVIEW_SAVE', '1').strip().lower() not in ('0', 'false', 'no')
        logger.info(f"Ejecutando predicción para foto: {photo_full_path.name} (ID: {photo_id})")
        result = self.detect_numbers_in_image(photo_full_path, save_digit_preview=save_preview)

        if result.get('error'):
            error_msg = result['error']
            logger.warning(
                f"[PREDICTION ERROR] foto {photo.id} (ID={photo_id}, "
                f"inspección={photo.inspection_id}): {error_msg}"
            )
            if existing and not existing.processing_error:
                return existing  # keep valid stale record rather than overwrite with an error
            prediction, _ = DigitPrediction.objects.update_or_create(
                inspection_photo=photo,
                defaults={'photo_id': photo_id, 'processing_error': error_msg},
            )
            return prediction

        # Extract digits from result — top-5 by confidence, left-to-right order
        digits = result.get('digits', ['', '', '', '', ''])
        detected_numbers = result.get('detected_numbers', '')

        # update_or_create writes fresh top-5 results and overwrites stale records
        prediction, created = DigitPrediction.objects.update_or_create(
            inspection_photo=photo,
            defaults={
                'photo_id': photo_id,
                'detected_numbers': detected_numbers,
                'letter': result.get('letter', ''),
                'digit_1': digits[0] if len(digits) > 0 else '',
                'digit_2': digits[1] if len(digits) > 1 else '',
                'digit_3': digits[2] if len(digits) > 2 else '',
                'digit_4': digits[3] if len(digits) > 3 else '',
                'digit_5': digits[4] if len(digits) > 4 else '',
                'average_confidence': result.get('average_confidence'),
                'prediction_details': result.get('details', ''),
                'processing_error': '',
            },
        )

        action = "created" if created else "updated"
        logger.info(
            f"Digit prediction {action} for photo {photo.id} (ID={photo_id}): "
            f"{detected_numbers}"
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
        
        target_found = False
        for photo in inspection.photos.all():
            filename = Path(photo.photo.name).name
            should_process, photo_id = self.should_process_photo(filename)

            if should_process:
                target_found = True
                try:
                    prediction = self.predict_for_photo(photo, photo_id)
                    if prediction:
                        predictions_made += 1
                except Exception as e:
                    logger.error(
                        f"Error procesando predicción foto {photo.id} "
                        f"(inspección={inspection_id}): {e}"
                    )
                    import traceback
                    logger.error(traceback.format_exc())
            else:
                logger.debug(
                    f"Foto {photo.id} omitida para predicción "
                    f"(ID='{photo_id}' no está en {TARGET_PHOTO_IDS}): {filename}"
                )

        if not target_found:
            logger.info(
                f"Inspección {inspection_id}: ninguna foto coincide con los IDs objetivo "
                f"{TARGET_PHOTO_IDS}. Sin predicciones generadas."
            )
        elif predictions_made > 0:
            logger.info(
                f"Inspección {inspection_id}: {predictions_made} predicción(es) generadas."
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
