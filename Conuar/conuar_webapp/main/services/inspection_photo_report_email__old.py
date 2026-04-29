"""
Email HTML report after an inspection is processed by the PLC pipeline.

Compares DB photo counts with files remaining in STAGING and saved under PROCESSED.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Tuple

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from main.models import Inspection

logger = logging.getLogger(__name__)

_IMAGE_EXTENSIONS = (".png", ".bmp", ".jpg", ".jpeg")


def _processed_subdir_name(inspection: Inspection) -> str:
    return inspection.product_code.replace(":", "-").replace("/", "-")


def _count_staging_images_for_inspection(inspection: Inspection) -> Tuple[int, List[str]]:
    """
    Count image files in STAGING whose names match this inspection's cycle/element prefix
    (NombreCiclo-ID_EC-), excluding generated *_comb files — same spirit as PlcDataProcessor.
    """
    staging = Path(getattr(settings, "INSPECTION_PHOTOS_STAGING_DIR", ""))
    if not staging.exists():
        return 0, []

    batch = (inspection.batch_number or "").strip()
    serial = (inspection.serial_number or "").strip()
    if not batch or not serial:
        return 0, []

    prefix = f"{batch}-{serial}-"
    names: List[str] = []
    seen = set()

    for ext in _IMAGE_EXTENSIONS:
        for p in staging.glob(f"{prefix}*{ext}"):
            if not p.is_file():
                continue
            if p.stem.endswith("_comb"):
                continue
            if p.name in seen:
                continue
            seen.add(p.name)
            names.append(p.name)

    names.sort()
    return len(names), names


def _count_processed_images_for_inspection(inspection: Inspection) -> Tuple[int, List[str]]:
    """Count image files under PROCESSED/<product_code_folder>/."""
    processed_root = Path(getattr(settings, "INSPECTION_PHOTOS_PROCESSED_DIR", ""))
    folder = processed_root / _processed_subdir_name(inspection)
    if not folder.exists():
        return 0, []

    names: List[str] = []
    for ext in _IMAGE_EXTENSIONS:
        for p in folder.glob(f"*{ext}"):
            if p.is_file():
                names.append(p.name)
    names.sort()
    return len(names), names


def build_inspection_report_context(inspection: Inspection) -> dict:
    """Context for the HTML email template."""
    inspection.refresh_from_db()
    db_photo_count = inspection.photos.count()
    defect_photo_count = inspection.photos.filter(defecto_encontrado=True).count()
    staging_count, staging_files = _count_staging_images_for_inspection(inspection)
    processed_count, processed_files = _count_processed_images_for_inspection(inspection)

    when = inspection.completed_date or inspection.inspection_date
    if when is not None:
        when_local = timezone.localtime(when)
        inspection_datetime_display = when_local.strftime("%d/%m/%Y %H:%M")
    else:
        inspection_datetime_display = "—"

    return {
        "inspection": inspection,
        "inspection_datetime_display": inspection_datetime_display,
        "db_photo_count": db_photo_count,
        "defect_photo_count": defect_photo_count,
        "inspection_defect_flag": bool(inspection.defecto_encontrado),
        "processed_folder_count": processed_count,
        "staging_remaining_count": staging_count,
        "staging_files": staging_files[:50],
        "staging_files_truncated": len(staging_files) > 50,
        "processed_files": processed_files[:50],
        "processed_files_truncated": len(processed_files) > 50,
        "processed_subdir": _processed_subdir_name(inspection),
    }


def render_inspection_processed_report_html(inspection: Inspection) -> str:
    ctx = build_inspection_report_context(inspection)
    return render_to_string("main/email/inspection_processed_report.html", ctx)


def send_inspection_processed_report_email(inspection_id: int) -> bool:
    """
    Send the inspection photo report email if enabled and recipients are configured.
    Returns True if an email was sent.
    """
    if not getattr(settings, "INSPECTION_PROCESSED_EMAIL_ENABLED", False):
        logger.debug("Inspection processed email disabled (INSPECTION_PROCESSED_EMAIL_ENABLED).")
        return False

    recipients = [e.strip() for e in getattr(settings, "INSPECTION_PROCESSED_EMAIL_RECIPIENTS", []) if e.strip()]
    if not recipients:
        logger.warning("Inspection processed email enabled but INSPECTION_PROCESSED_EMAIL_RECIPIENTS is empty.")
        return False

    try:
        inspection = Inspection.objects.prefetch_related("photos").get(pk=inspection_id)
    except Inspection.DoesNotExist:
        logger.error("send_inspection_processed_report_email: inspection id=%s not found", inspection_id)
        return False

    ctx = build_inspection_report_context(inspection)
    html_body = render_to_string("main/email/inspection_processed_report.html", ctx)
    subject = getattr(settings, "INSPECTION_PROCESSED_EMAIL_SUBJECT_PREFIX", "[Conuar] ")
    subject = f'{subject.rstrip()} Inspección #{inspection.id} — {inspection.product_code or "sin código"}'

    plain = (
        f"Inspección #{inspection.id}\n"
        f"Código producto: {inspection.product_code}\n"
        f"Fecha/hora: {ctx['inspection_datetime_display']}\n"
        f"Fotos en BD (main_inspectionphoto): {ctx['db_photo_count']}\n"
        f"Fotos con defecto: {ctx['defect_photo_count']}\n"
        f"Defecto a nivel inspección: {'Sí' if ctx['inspection_defect_flag'] else 'No'}\n"
        f"Archivos imagen en PROCESSED: {ctx['processed_folder_count']}\n"
        f"Archivos imagen restantes en STAGING: {ctx['staging_remaining_count']}\n"
        f"\nAdjunto: informe HTML detallado.\n"
    )

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or getattr(settings, "EMAIL_HOST_USER", "")
    email = EmailMultiAlternatives(
        subject=subject,
        body=plain,
        from_email=from_email,
        to=recipients,
    )
    email.attach_alternative(html_body, "text/html")
    filename = f"inspeccion_{inspection.id}_reporte_fotos.html"
    email.attach(filename, html_body.encode("utf-8"), "text/html")

    email.send(fail_silently=False)
    logger.info("Inspection processed report email sent for inspection id=%s to %s", inspection_id, recipients)
    return True
