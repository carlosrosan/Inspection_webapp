"""
Email HTML report after an inspection is processed by the PLC pipeline.

Compares DB photo counts with files remaining in STAGING and saved under PROCESSED.
Also surfaces:
  - Orphaned STAGING photos (matched this inspection's prefix but not linked in DB)
  - PlcDataRaw rows whose photos are still sitting in STAGING
"""
from __future__ import annotations

import json as _json
import logging
from pathlib import Path
from typing import Dict, List, Tuple

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


def _stem_key(name: str) -> str:
    """Filename stem without the _comb suffix, lowercased — used for deduplication."""
    stem = Path(name).stem
    if stem.endswith("_comb"):
        stem = stem[:-5]
    return stem.lower()


def _get_orphaned_staging_photos(inspection: Inspection) -> Tuple[int, List[str]]:
    """
    STAGING images matching this inspection's cycle prefix that are NOT linked
    in main_inspectionphoto.  These were missed during processing or are
    being recovered by the final-sweep / recovery scanner.
    """
    _, staging_files = _count_staging_images_for_inspection(inspection)
    if not staging_files:
        return 0, []

    linked_keys = {
        _stem_key(Path(p).name)
        for p in inspection.photos.values_list("photo", flat=True)
        if p
    }
    orphaned = [f for f in staging_files if _stem_key(f) not in linked_keys]
    return len(orphaned), sorted(orphaned)


def _get_plc_raw_staging_matches(inspection: Inspection) -> Tuple[int, List[dict]]:
    """
    PlcDataRaw rows whose NombreCiclo/ID_EC match this inspection AND that have
    at least one photo still in STAGING.  One entry per unique ID_Control.
    `processed` flag indicates whether the cycle row was already consumed.
    """
    from main.models import PlcDataRaw

    batch = (inspection.batch_number or "").strip()
    serial = (inspection.serial_number or "").strip()
    if not batch or not serial:
        return 0, []

    staging = Path(getattr(settings, "INSPECTION_PHOTOS_STAGING_DIR", ""))
    if not staging.exists():
        return 0, []

    # Index STAGING files by ID_Control (3rd dash-segment of filename)
    staging_by_idc: dict = {}
    prefix = f"{batch}-{serial}-"
    for ext in _IMAGE_EXTENSIONS:
        for p in staging.glob(f"{prefix}*{ext}"):
            if not p.is_file() or p.stem.endswith("_comb"):
                continue
            parts = p.stem.split("-")
            if len(parts) >= 3:
                staging_by_idc.setdefault(parts[2], []).append(p.name)

    if not staging_by_idc:
        return 0, []

    def _fv(data: dict, key: str) -> str:
        v = data.get(key) or data.get(f" {key}") or ""
        return str(v).strip() if not isinstance(v, bool) else ""

    matched: list = []
    seen_idc: set = set()

    for raw in PlcDataRaw.objects.order_by("-timestamp")[:2000]:
        try:
            data = _json.loads(raw.json_data)
        except Exception:
            continue
        if _fv(data, "NombreCiclo") != batch or _fv(data, "ID_EC") != serial:
            continue
        idc = _fv(data, "ID_Control")
        if not idc or idc in seen_idc or idc not in staging_by_idc:
            continue
        seen_idc.add(idc)
        matched.append({
            "raw_id": raw.id,
            "timestamp": raw.timestamp.strftime("%d/%m/%Y %H:%M:%S") if raw.timestamp else "—",
            "id_control": idc,
            "processed": raw.processed,
            "staging_photos": sorted(staging_by_idc[idc]),
        })

    matched.sort(key=lambda r: r["id_control"])
    return len(matched), matched


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

    orphaned_count, orphaned_files = _get_orphaned_staging_photos(inspection)
    plc_raw_count, plc_raw_rows = _get_plc_raw_staging_matches(inspection)

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
        # Orphaned / recovery
        "orphaned_staging_count": orphaned_count,
        "orphaned_staging_files": orphaned_files[:50],
        "orphaned_staging_truncated": len(orphaned_files) > 50,
        # PlcDataRaw rows with photos still in STAGING
        "plc_raw_staging_count": plc_raw_count,
        "plc_raw_staging_rows": plc_raw_rows[:30],
        "plc_raw_staging_truncated": len(plc_raw_rows) > 30,
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
        f"Fotos huérfanas (STAGING sin registro DB): {ctx['orphaned_staging_count']}\n"
        f"Filas PlcDataRaw con fotos aún en STAGING: {ctx['plc_raw_staging_count']}\n"
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
