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
import tempfile
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


def _strip_svg_images(svg_path: Path) -> Optional[str]:
    """
    Parse the SVG and return the path to a temp file with all <image> elements removed.

    The camera software embeds the source photo as an <image xlink:href="..."> that fills
    the entire SVG canvas.  rlPyCairo renders this reference, so if we pass the raw SVG to
    svg2rlg we get the photo rendered inside the SVG *and* the original photo as the base
    layer — two copies at slightly different scales (SVG px vs point unit mismatch).

    Removing <image> nodes before parsing leaves only the vector annotations
    (lines, crosshairs, text labels) on a transparent canvas.

    Returns the temp-file path on success, None if lxml is unavailable or parsing fails
    (caller falls back to using the original SVG).  Caller must delete the temp file.
    """
    try:
        import lxml.etree as ET

        tree = ET.parse(str(svg_path))
        root = tree.getroot()

        SVG_NS = 'http://www.w3.org/2000/svg'
        for image_el in (
            root.findall(f'.//{{{SVG_NS}}}image') +
            root.findall('.//image')
        ):
            parent = image_el.getparent()
            if parent is not None:
                parent.remove(image_el)

        with tempfile.NamedTemporaryFile(suffix='.svg', delete=False, mode='wb') as f:
            tmp_path = f.name
            tree.write(f, xml_declaration=True, encoding='utf-8')

        return tmp_path
    except Exception as e:
        logger.warning(f"No se pudo limpiar <image> del SVG ({e}), usando SVG original")
        return None


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
        
        # Strip <image> elements before parsing: the SVG embeds the source photo via
        # xlink:href. rlPyCairo renders that reference, which — when composited onto the
        # original photo — produces a double image at a slightly different scale (SVG "px"
        # units ≠ SVG user-unit/points, causing a 72/96 = 75 % scale mismatch).
        # Removing <image> nodes leaves only the vector annotations on a transparent canvas.
        logger.info(f"Convirtiendo SVG a imagen: {svg_path}")
        clean_svg = _strip_svg_images(svg_path)
        try:
            drawing = svg2rlg(clean_svg or str(svg_path))
            if drawing is None:
                logger.error(f"No se pudo convertir SVG: {svg_path}")
                return None
        except Exception as e:
            logger.error(f"Error al convertir SVG: {e}")
            return None
        finally:
            if clean_svg:
                try:
                    os.unlink(clean_svg)
                except Exception:
                    pass
        
        # Render the SVG at its natural dimensions (do NOT force drawing.width/height to
        # BMP pixel values — ReportLab uses points, not pixels, so forcing pixel values
        # expands the canvas without scaling the content, leaving empty black areas).
        # We resize the rendered output to the BMP size afterwards, which correctly
        # scales both canvas and content together.

        # dpi=72 → 1 ReportLab point = 1 pixel, avoids a spurious 4/3 scale factor.

        # Strategy: prefer transparent-background rendering (rlPyCairo supports it and
        # returns a proper RGBA image). Fall back to white-background rendering
        # (_renderPM / GDI on Windows without rlPyCairo) plus manual masking.
        svg_image = None

        # --- attempt 1: transparent background (rlPyCairo) ---
        try:
            candidate = renderPM.drawToPIL(drawing, dpi=72, bg=0x00000000)
            if candidate is not None and candidate.mode == 'RGBA':
                svg_image = candidate
                logger.debug("SVG renderizado con fondo transparente (rlPyCairo)")
        except Exception as e:
            logger.debug(f"Renderizado con fondo transparente falló: {e}")

        # --- attempt 2: white background (_renderPM / GDI fallback) ---
        if svg_image is None:
            try:
                svg_image = renderPM.drawToPIL(drawing, dpi=72, bg=0xFFFFFF)
            except Exception as e1:
                logger.warning(f"Error al renderizar SVG directamente: {e1}, intentando método alternativo")
                try:
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                        tmp_path = tmp_file.name
                    renderPM.drawToFile(drawing, tmp_path, fmt='PNG', bg=0xFFFFFF)
                    svg_image = Image.open(tmp_path).copy()
                    os.unlink(tmp_path)
                except Exception as e2:
                    logger.error(f"Error alternativo al renderizar SVG: {e2}")
                    return None

        # Scale the entire SVG image (content + canvas) to match BMP dimensions
        if svg_image.size != bmp_image.size:
            logger.info(f"Redimensionando SVG de {svg_image.size} a {bmp_image.size}")
            svg_image = svg_image.resize(bmp_image.size, Image.Resampling.LANCZOS)

        # Ensure RGBA.  If rlPyCairo already returned RGBA the alpha channel is correct;
        # if _renderPM returned RGB (white background) we derive alpha by masking near-white.
        if svg_image.mode == 'RGBA':
            pass  # proper alpha already present — no masking needed
        else:
            svg_image = svg_image.convert('RGBA')
            r, g, b, a = svg_image.split()
            mask = Image.merge('RGB', (r, g, b)).point(
                lambda v: 0 if v > 245 else 255
            ).convert('L')
            svg_image.putalpha(mask)

        # Superponer SVG sobre BMP
        logger.info(f"Superponiendo SVG sobre BMP...")
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
    Función principal para unificar una foto BMP (legacy).
    Busca automáticamente el SVG correspondiente y crea el PNG.
    
    Args:
        bmp_path: Ruta al archivo BMP
    
    Returns:
        Path al archivo PNG creado, o None si falla
    """
    return overlay_svg_on_bmp(bmp_path)


def unify_photo_png(png_path: Path) -> Optional[Path]:
    """
    Overlay SVG vectors on a PNG source image, saving as {stem}_comb.png.
    If no matching SVG exists, returns None (the original PNG is already usable).

    Args:
        png_path: Path to the source PNG file

    Returns:
        Path to the combined PNG file (_comb.png), or None if no SVG or failure
    """
    svg_path = png_path.with_suffix('.svg')
    if not svg_path.exists():
        logger.info(f"No SVG found for {png_path.name}, skipping combination")
        return None

    output_path = png_path.with_name(png_path.stem + '_comb.png')
    return overlay_svg_on_bmp(png_path, svg_path=svg_path, output_path=output_path)


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

