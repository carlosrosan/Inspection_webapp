#!/usr/bin/env python3
"""
Photo name correction - Rename inspection photos by correcting NombreCiclo and ID_EC in filenames.

Filename format: NombreCiclo-ID_EC-<rest>.<ext>
Example: PRUEBACOMP-E07831-240F-270226_162533-NOK410.bmp
         or 04-03-26-E07831-240F-270226_162533-NOK410.bmp

Output format: {nombre_ciclo_out}-{id_ec_out}-<rest>
Example: 04MAR-A2026-240F-270226_162533-NOK410.bmp (from 04-03-26, E07831 -> 04MAR, A2026)
"""

import argparse
import sys
from pathlib import Path


def build_prefix(nombre_ciclo: str, id_ec: str) -> str:
    """Build the expected filename prefix: NombreCiclo-ID_EC-"""
    return f"{nombre_ciclo}-{id_ec}-"


def new_filename(
    current_name: str,
    nombre_ciclo_in: str,
    id_ec_in: str,
    nombre_ciclo_out: str,
    id_ec_out: str,
) -> str | None:
    """
    Compute the new filename if the current one matches the input NombreCiclo and ID_EC.
    Returns the new filename (same extension) or None if no match.
    """
    prefix = build_prefix(nombre_ciclo_in, id_ec_in)
    if not current_name.startswith(prefix):
        return None
    rest = current_name[len(prefix):]
    # New format: {nombre_ciclo_out}-{id_ec_out}-<rest>
    new_base = f"{nombre_ciclo_out}-{id_ec_out}-{rest}"
    return new_base


def correct_photo_names(
    folder: Path,
    nombre_ciclo_in: str,
    id_ec_in: str,
    nombre_ciclo_out: str,
    id_ec_out: str,
    dry_run: bool = False,
) -> tuple[int, int]:
    """
    Rename all matching photos in folder.
    Returns (renamed_count, skipped_count).
    """
    if not folder.is_dir():
        raise NotADirectoryError(f"Folder does not exist or is not a directory: {folder}")

    renamed = 0
    skipped = 0

    for path in sorted(folder.iterdir()):
        if not path.is_file():
            continue
        name = path.name
        new_name = new_filename(name, nombre_ciclo_in, id_ec_in, nombre_ciclo_out, id_ec_out)
        if new_name is None:
            skipped += 1
            continue
        if new_name == name:
            skipped += 1
            continue
        dest = path.parent / new_name
        if dest.exists():
            print(f"  Skip (target exists): {name} -> {new_name}", file=sys.stderr)
            skipped += 1
            continue
        if dry_run:
            print(f"  [DRY RUN] {name} -> {new_name}")
        else:
            path.rename(dest)
            print(f"  Renamed: {name} -> {new_name}")
        renamed += 1

    return renamed, skipped


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rename inspection photos by correcting NombreCiclo and ID_EC in filenames.",
        epilog="Example: python photo_name_correction.py STAGING --nombre-ciclo-in 04-03-26 --nombre-ciclo-out 04MAR --id-ec-in E07831 --id-ec-out A2026",
    )
    parser.add_argument(
        "folder",
        type=str,
        help="Folder containing the photos to rename (e.g. STAGING)",
    )
    parser.add_argument(
        "--nombre-ciclo-in",
        required=True,
        dest="nombre_ciclo_in",
        metavar="NAME",
        help="Current NombreCiclo in filenames (e.g. 04-03-26)",
    )
    parser.add_argument(
        "--nombre-ciclo-out",
        required=True,
        dest="nombre_ciclo_out",
        metavar="NAME",
        help="New NombreCiclo for filenames (e.g. 04MAR)",
    )
    parser.add_argument(
        "--id-ec-in",
        required=True,
        dest="id_ec_in",
        metavar="ID",
        help="Current ID_EC in filenames (e.g. E07831)",
    )
    parser.add_argument(
        "--id-ec-out",
        required=True,
        dest="id_ec_out",
        metavar="ID",
        help="New ID_EC for filenames (e.g. A2026)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print renames, do not rename files",
    )
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.is_absolute():
        folder = Path.cwd() / folder

    print(
        f"Folder: {folder}\n"
        f"NombreCiclo: {args.nombre_ciclo_in} -> {args.nombre_ciclo_out}\n"
        f"ID_EC: {args.id_ec_in} -> {args.id_ec_out}\n"
    )
    if args.dry_run:
        print("DRY RUN (no files will be changed)\n")

    try:
        renamed, skipped = correct_photo_names(
            folder,
            args.nombre_ciclo_in,
            args.id_ec_in,
            args.nombre_ciclo_out,
            args.id_ec_out,
            dry_run=args.dry_run,
        )
    except NotADirectoryError as e:
        print(e, file=sys.stderr)
        return 1

    print(f"\nDone: {renamed} renamed, {skipped} skipped (no match or already correct).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
