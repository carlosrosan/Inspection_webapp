#!/usr/bin/env python3
"""
Elimina de la tabla PlcDataRaw (registros raw de PLC) las filas ya procesadas
que pertenecen a un nombre_ciclo dado.

Uso:
  python delete_raw_plc_processed.py --nombre_ciclo "Ciclo2"
  python delete_raw_plc_processed.py --nombre_ciclo "inspeccion_hoy" --yes

Se considera que una fila pertenece al ciclo si en json_data el campo
NombreCiclo (o nombre_ciclo) coincide exactamente con el valor indicado.
Solo se borran filas con processed=True.


python delete_raw_plc_processed.py "Ciclo2"
python delete_raw_plc_processed.py --nombre_ciclo "inspeccion_hoy"
python delete_raw_plc_processed.py --nombre_ciclo "inspeccion_hoy" --yes
"""

import argparse
import json
import os
import sys

import django

# Configurar Django si se ejecuta como script standalone
try:
    django.apps.apps.check_apps_ready()
except Exception:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if parent not in sys.path:
        sys.path.insert(0, parent)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()

from main.models import PlcDataRaw


def _json_has_nombre_ciclo(json_str: str, nombre_ciclo: str) -> bool:
    """True si el JSON tiene NombreCiclo o nombre_ciclo igual a nombre_ciclo (comparación exacta)."""
    if not json_str or not nombre_ciclo:
        return False
    try:
        data = json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return False
    for key in ("NombreCiclo", " NombreCiclo", "nombre_ciclo"):
        val = data.get(key)
        if val is not None and str(val).strip() == nombre_ciclo.strip():
            return True
    return False


def get_processed_raw_ids_for_cycle(nombre_ciclo: str):
    """Devuelve los IDs de PlcDataRaw procesados cuyo NombreCiclo coincide con nombre_ciclo."""
    qs = PlcDataRaw.objects.filter(processed=True)
    ids = []
    for raw in qs.iterator(chunk_size=500):
        if _json_has_nombre_ciclo(raw.json_data, nombre_ciclo):
            ids.append(raw.id)
    return ids


def main():
    parser = argparse.ArgumentParser(
        description="Borrar de plc_data_raw las filas procesadas de un nombre_ciclo dado."
    )
    parser.add_argument(
        "nombre_ciclo",
        nargs="?",
        default=None,
        help="Nombre del ciclo (ej: Ciclo2, inspeccion_hoy). Coincide con NombreCiclo en los datos PLC.",
    )
    parser.add_argument(
        "--nombre_ciclo",
        dest="nombre_ciclo_flag",
        metavar="NOMBRE",
        help="Mismo que el argumento posicional (alternativa).",
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="No pedir confirmación antes de borrar.",
    )
    args = parser.parse_args()
    nombre_ciclo = args.nombre_ciclo or args.nombre_ciclo_flag
    if not nombre_ciclo or not nombre_ciclo.strip():
        parser.error("Debe indicar un nombre_ciclo (posicional o --nombre_ciclo).")
    nombre_ciclo = nombre_ciclo.strip()

    ids = get_processed_raw_ids_for_cycle(nombre_ciclo)
    count = len(ids)
    if count == 0:
        print(f"No se encontraron filas procesadas con nombre_ciclo = {nombre_ciclo!r}.")
        return 0

    print(f"Se encontraron {count} filas procesadas con nombre_ciclo = {nombre_ciclo!r}.")
    if not args.yes:
        resp = input("¿Borrar estas filas? [s/N]: ").strip().lower()
        if resp not in ("s", "si", "y", "yes"):
            print("Operación cancelada.")
            return 0

    deleted, _ = PlcDataRaw.objects.filter(id__in=ids).delete()
    print(f"Eliminadas {deleted} filas de PlcDataRaw.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
