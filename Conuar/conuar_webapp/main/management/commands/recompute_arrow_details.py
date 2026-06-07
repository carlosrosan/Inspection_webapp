import csv
from pathlib import Path

from django.core.management.base import BaseCommand
from main.models import Inspection, ArrowDetail, PlcArrowReadingRaw

RAW_FIELDS  = [(f'f{i}_xc', f'f{i}_yc') for i in range(14)]
ARROW_COLS  = [(f'F{i}-Xc', f'F{i}-Yc') for i in range(14)]
ARROW_CSV   = (Path(__file__).resolve().parents[4]
               / 'etl' / 'NodeRed' / 'plc_reads' / 'plc_arrow_nodered.csv')


def _f(val):
    """Safe string → float conversion (same helper as plc_data_processor)."""
    v = str(val).strip().replace(',', '.')
    try:
        return float(v) if v else None
    except ValueError:
        return None


def _load_csv_diametro(nombre_ciclo: str, id_ec: str) -> float | None:
    """
    Read plc_arrow_nodered.csv and return the averaged diametro for the given
    NombreCiclo + ID_EC.  Returns None when the CSV cannot be read or no
    matching rows are found.  This is the fallback for PlcArrowReadingRaw rows
    that were created before the diametro column was added to the model.
    """
    if not ARROW_CSV.exists():
        return None
    vals = []
    try:
        with open(ARROW_CSV, newline='', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                csv_nombre = row.get('NombreCiclo', row.get(' NombreCiclo', '')).strip()
                csv_id_ec  = row.get('ID_EC',       row.get(' ID_EC',       '')).strip()
                if csv_nombre != nombre_ciclo or csv_id_ec != id_ec:
                    continue
                d = _f(row.get('diametro', row.get(' diametro', '')))
                if d is not None:
                    vals.append(d)
    except Exception:
        pass
    return sum(vals) / len(vals) if vals else None


class Command(BaseCommand):
    help = (
        'Re-average ArrowDetail rows from PlcArrowReadingRaw '
        '(fixes duplicate rows; backfills diametro from DB or CSV fallback).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--inspection-id',
            type=int,
            default=None,
            help='Only recompute for this inspection ID (default: all)',
        )

    def handle(self, *args, **options):
        inspection_id = options['inspection_id']
        qs = Inspection.objects.all()
        if inspection_id:
            qs = qs.filter(id=inspection_id)

        total_fixed = 0
        for inspection in qs:
            raw_rows = list(PlcArrowReadingRaw.objects.filter(inspection=inspection))
            if not raw_rows:
                continue

            position_xc  = {i: [] for i in range(len(RAW_FIELDS))}
            position_yc  = {i: [] for i in range(len(RAW_FIELDS))}
            diametro_vals = []

            for raw in raw_rows:
                for i, (xc_field, yc_field) in enumerate(RAW_FIELDS):
                    xc_val = getattr(raw, xc_field, None)
                    yc_val = getattr(raw, yc_field, None)
                    if xc_val is not None:
                        position_xc[i].append(xc_val)
                    if yc_val is not None:
                        position_yc[i].append(yc_val)
                d = getattr(raw, 'diametro', None)
                if d is not None:
                    diametro_vals.append(d)

            diametro_avg = (
                sum(diametro_vals) / len(diametro_vals) if diametro_vals else None
            )

            # ── Fallback: read diametro from CSV when DB rows have NULL ──────
            # PlcArrowReadingRaw rows created before the diametro field was
            # added to the model have diametro=NULL.  Read from the source CSV
            # so existing inspections are correctly backfilled.
            if diametro_avg is None:
                nombre_ciclo = (inspection.batch_number  or '').strip()
                id_ec        = (inspection.serial_number or '').strip()
                if nombre_ciclo and id_ec:
                    diametro_avg = _load_csv_diametro(nombre_ciclo, id_ec)
                    if diametro_avg is not None:
                        # Persist the value back to PlcArrowReadingRaw so
                        # future recompute calls don't need the CSV fallback.
                        PlcArrowReadingRaw.objects.filter(
                            inspection=inspection
                        ).update(diametro=diametro_avg)
                        self.stdout.write(
                            f'  Inspection {inspection.id}: diametro backfilled '
                            f'from CSV → {diametro_avg}'
                        )

            detail_rows = []
            for i in range(len(RAW_FIELDS)):
                xc_avg = (
                    sum(position_xc[i]) / len(position_xc[i])
                    if position_xc[i] else None
                )
                yc_avg = (
                    sum(position_yc[i]) / len(position_yc[i])
                    if position_yc[i] else None
                )
                if xc_avg is not None or yc_avg is not None:
                    detail_rows.append(ArrowDetail(
                        inspection=inspection,
                        xc=xc_avg,
                        yc=yc_avg,
                        diametro=diametro_avg,
                    ))

            ArrowDetail.objects.filter(inspection=inspection).delete()
            if detail_rows:
                ArrowDetail.objects.bulk_create(detail_rows)

            self.stdout.write(
                f'Inspection {inspection.id}: {len(raw_rows)} raw rows → '
                f'{len(detail_rows)} positions, diametro={diametro_avg}'
            )
            total_fixed += 1

        self.stdout.write(self.style.SUCCESS(f'Done. Fixed {total_fixed} inspection(s).'))