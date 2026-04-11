#!/usr/bin/env python3
"""
Photo Unificator - Sistema Conuar

Este script toma una foto .bmp y su correspondiente archivo .svg con el mismo nombre,
superpone los vectores del SVG sobre la imagen BMP y crea una nueva imagen .png
en el mismo directorio.

Sistema de inspección de combustible Conuar
"""

import os
import logging
from pathlib import Path
from typing import Optional
from PIL import Image
from reportlab.graphics import renderPM

# Try to import svglib, handle gracefully if not available
try:
    from svglib.svglib import svg2rlg
    SVG_SUPPORT = True
except ImportError:
    SVG_SUPPORT = False
    logging.warning("svglib no disponible. SVG processing deshabilitado.")

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def overlay_svg_on_bmp(bmp_path: Path, svg_path: Optional[Path] = None, output_path: Optional[Path] = None) -> Optional[Path]:
    """
    Superpone un archivo SVG sobre una imagen BMP y guarda el resultado como PNG.
    
    Args:
        bmp_path: Ruta al archivo BMP
        svg_path: Ruta al archivo SVG (opcional, se busca automáticamente si no se proporciona)
        output_path: Ruta de salida para el PNG (opcional, se genera automáticamente si no se proporciona)
    
    Returns:
        Path al archivo PNG creado, o None si falla
    """
    if not SVG_SUPPORT:
        logger.error("svglib no disponible. No se puede procesar SVG.")
        return None
    
    try:
        # Validar que el BMP existe
        if not bmp_path.exists():
            logger.error(f"Archivo BMP no encontrado: {bmp_path}")
            return None
        
        # Buscar SVG si no se proporciona
        if svg_path is None:
            svg_path = bmp_path.with_suffix('.svg')
        
        # Validar que el SVG existe
        if not svg_path.exists():
            logger.warning(f"Archivo SVG no encontrado: {svg_path}. Se creará solo la copia BMP como PNG.")
            # Si no hay SVG, solo convertir BMP a PNG
            return _convert_bmp_to_png(bmp_path, output_path)
        
        # Generar ruta de salida si no se proporciona
        if output_path is None:
            output_path = bmp_path.with_suffix('.png')
        
        # Cargar imagen BMP
        logger.info(f"Cargando BMP: {bmp_path}")
        bmp_image = Image.open(bmp_path)
        
        # Convertir a RGBA si es necesario para permitir composición
        if bmp_image.mode != 'RGBA':
            bmp_image = bmp_image.convert('RGBA')
        
        # Convertir SVG a ReportLab Drawing
        logger.info(f"Convirtiendo SVG a imagen: {svg_path}")
        try:
            drawing = svg2rlg(str(svg_path))
            if drawing is None:
                logger.error(f"No se pudo convertir SVG: {svg_path}")
                return None
        except Exception as e:
            logger.error(f"Error al convertir SVG: {e}")
            return None
        
        # Renderizar SVG a PIL Image al tamaño del BMP
        # Guardar dimensiones originales del drawing
        original_width = getattr(drawing, 'width', bmp_image.width)
        original_height = getattr(drawing, 'height', bmp_image.height)
        
        # Establecer tamaño objetivo igual al BMP
        drawing.width = bmp_image.width
        drawing.height = bmp_image.height
        
        # Renderizar SVG a PIL Image
        try:
            # Renderizar con fondo transparente
            svg_image = renderPM.drawToPIL(
                drawing,
                dpi=96,
                bg=0x00000000,  # Fondo transparente
            )
        except Exception as e:
            logger.warning(f"Error al renderizar SVG directamente: {e}, intentando método alternativo")
            # Método alternativo: renderizar a archivo temporal
            try:
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                    tmp_path = tmp_file.name
                
                renderPM.drawToFile(drawing, tmp_path, fmt='PNG', bg=0x00000000)
                svg_image = Image.open(tmp_path)
                os.unlink(tmp_path)  # Eliminar temporal
            except Exception as e2:
                logger.error(f"Error alternativo al renderizar SVG: {e2}")
                # Restaurar dimensiones originales antes de retornar
                drawing.width = original_width
                drawing.height = original_height
                return None
        
        # Restaurar dimensiones originales del drawing (buena práctica)
        drawing.width = original_width
        drawing.height = original_height
        
        # Asegurar que SVG tiene exactamente el mismo tamaño que BMP (redimensionar si es necesario)
        if svg_image.size != bmp_image.size:
            logger.info(f"Redimensionando SVG de {svg_image.size} a {bmp_image.size}")
            svg_image = svg_image.resize(bmp_image.size, Image.Resampling.LANCZOS)
        
        # Convertir SVG a RGBA si es necesario
        if svg_image.mode != 'RGBA':
            svg_image = svg_image.convert('RGBA')
        
        # Superponer SVG sobre BMP
        logger.info(f"Superponiendo SVG sobre BMP...")
        # Crear una imagen compuesta: BMP como base, SVG encima
        result_image = Image.alpha_composite(bmp_image, svg_image)
        
        # Guardar resultado como PNG
        logger.info(f"Guardando imagen compuesta: {output_path}")
        result_image.save(output_path, 'PNG')
        
        logger.info(f"Imagen unificada creada exitosamente: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error al unificar foto: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def _convert_bmp_to_png(bmp_path: Path, output_path: Optional[Path] = None) -> Optional[Path]:
    """
    Convierte un BMP a PNG sin SVG (fallback cuando no hay SVG disponible).
    
    Args:
        bmp_path: Ruta al archivo BMP
        output_path: Ruta de salida (opcional)
    
    Returns:
        Path al archivo PNG creado, o None si falla
    """
    try:
        if output_path is None:
            output_path = bmp_path.with_suffix('.png')
        
        logger.info(f"Convirtiendo BMP a PNG: {bmp_path} -> {output_path}")
        bmp_image = Image.open(bmp_path)
        
        # Convertir a RGB para PNG (PNG puede no soportar todos los modos de BMP)
        if bmp_image.mode not in ('RGB', 'RGBA'):
            bmp_image = bmp_image.convert('RGB')
        
        bmp_image.save(output_path, 'PNG')
        logger.info(f"BMP convertido a PNG: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error al convertir BMP a PNG: {e}")
        return None


def unify_photo(bmp_path: Path) -> Optional[Path]:
    """
    Función principal para unificar una foto.
    Busca automáticamente el SVG correspondiente y crea el PNG.
    
    Args:
        bmp_path: Ruta al archivo BMP
    
    Returns:
        Path al archivo PNG creado, o None si falla
    """
    return overlay_svg_on_bmp(bmp_path)


if __name__ == "__main__":
    """Prueba del script"""
    import sys
    
    if len(sys.argv) < 2:
        print("Uso: python photo_unificator.py <ruta_bmp>")
        sys.exit(1)
    
    bmp_path = Path(sys.argv[1])
    result = unify_photo(bmp_path)
    
    if result:
        print(f"✓ Imagen unificada creada: {result}")
    else:
        print(f"✗ Error al crear imagen unificada")
        sys.exit(1)

