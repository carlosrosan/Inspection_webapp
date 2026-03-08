#!/usr/bin/env python3
"""
Reads "Numero de SE y barra.xlsx" (columns "ID" = ID_Control, "Medicion" = Control Name)
and outputs SQL INSERT statements for the control_names table.
Run from the same folder as the Excel file, or set EXCEL_PATH.

Usage:
  python load_control_names_from_excel.py                    # print INSERTs to stdout
  python load_control_names_from_excel.py --output out.sql   # write to file
  python load_control_names_from_excel.py --django            # insert via Django DB
"""

import argparse
import os
import sys

EXCEL_FILENAME = "Numero de SE y barra.xlsx"
ID_COL = "ID"
MEDICION_COL = "Medicion"


def read_excel(excel_path):
    """Return list of (id_control, control_name) from Excel."""
    try:
        import openpyxl
    except ImportError:
        try:
            import pandas as pd
            df = pd.read_excel(excel_path)
            # Normalize column names (strip spaces)
            df.columns = [str(c).strip() for c in df.columns]
            if ID_COL not in df.columns or MEDICION_COL not in df.columns:
                print("Expected columns 'ID' and 'Medicion'. Found:", list(df.columns), file=sys.stderr)
                return []
            rows = []
            for _, r in df.iterrows():
                id_val = r.get(ID_COL)
                med_val = r.get(MEDICION_COL)
                if id_val is not None and str(id_val).strip():
                    rows.append((str(id_val).strip(), str(med_val).strip() if med_val is not None else ""))
            return rows
        except ImportError:
            print("Install openpyxl or pandas: pip install openpyxl pandas", file=sys.stderr)
            return []

    wb = openpyxl.load_workbook(excel_path, read_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    header = next(rows_iter, None)
    if not header:
        wb.close()
        return []
    header = [str(h).strip() if h is not None else "" for h in header]
    try:
        idx_id = header.index(ID_COL)
    except ValueError:
        idx_id = next((i for i, h in enumerate(header) if h and "id" in h.lower() and "control" in h.lower()), 0)
    try:
        idx_med = header.index(MEDICION_COL)
    except ValueError:
        idx_med = next((i for i, h in enumerate(header) if h and "medicion" in h.lower()), 1)
    rows = []
    for row in rows_iter:
        if not row:
            continue
        id_val = row[idx_id] if idx_id < len(row) else None
        if id_val is None or str(id_val).strip() == "":
            continue
        med_val = row[idx_med] if idx_med < len(row) else None
        rows.append((str(id_val).strip(), str(med_val).strip() if med_val is not None else ""))
    wb.close()
    return rows


def escape_sql(s):
    return s.replace("'", "''")


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_path = os.path.join(script_dir, EXCEL_FILENAME)
    parser = argparse.ArgumentParser(description="Load control_names from Excel into SQL or Django DB.")
    parser.add_argument("--excel", default=default_path, help=f"Path to Excel file (default: {EXCEL_FILENAME})")
    parser.add_argument("--output", "-o", help="Write INSERTs to this file instead of stdout")
    parser.add_argument("--django", action="store_true", help="Insert into DB using Django (run from project root)")
    args = parser.parse_args()

    if not os.path.isfile(args.excel):
        print(f"File not found: {args.excel}", file=sys.stderr)
        return 1

    data = read_excel(args.excel)
    if not data:
        print("No rows found in Excel.", file=sys.stderr)
        return 1

    if args.django:
        try:
            parent = os.path.dirname(script_dir)
            if parent not in sys.path:
                sys.path.insert(0, parent)
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
            import django
            django.setup()
            from django.db import connection
            vendor = connection.vendor  # 'sqlite3' or 'postgresql'
            with connection.cursor() as c:
                for id_control, control_name in data:
                    if vendor == "sqlite3":
                        c.execute(
                            "INSERT OR REPLACE INTO control_names (id_control, control_name) VALUES (?, ?)",
                            [id_control, control_name],
                        )
                    else:
                        c.execute(
                            "INSERT INTO control_names (id_control, control_name) VALUES (%s, %s) "
                            "ON CONFLICT (id_control) DO UPDATE SET control_name = EXCLUDED.control_name",
                            [id_control, control_name],
                        )
            print(f"Inserted {len(data)} rows into control_names.", file=sys.stderr)
        except Exception as e:
            print(f"Django insert failed: {e}", file=sys.stderr)
            return 1
        return 0

    lines = []
    for id_control, control_name in data:
        lines.append(
            f"INSERT INTO control_names (id_control, control_name) VALUES "
            f"('{escape_sql(id_control)}', '{escape_sql(control_name)}');"
        )
    out = "\n".join(lines)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"Wrote {len(lines)} INSERTs to {args.output}", file=sys.stderr)
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
