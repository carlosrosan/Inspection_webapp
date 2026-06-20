#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
watchdog.py — Conuar Inspection Webapp Process Watchdog

- On startup: launches start_django.bat and start_nodered.bat if they are
  not already running.
- Every CHECK_INTERVAL seconds: counts how many cmd.exe processes are running
  each bat file.  If > 1, kills the newest duplicate.  If 0, shows a popup.

No extra packages required — only Python stdlib + PowerShell (built-in on Win 11).
"""

import os
import sys
import time
import subprocess
import threading
from datetime import datetime
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────────────
BASE_DIR       = Path(__file__).parent.resolve()   # folder that contains this file
DJANGO_BAT     = BASE_DIR / "start_django.bat"
NODERED_BAT    = BASE_DIR / "start_nodered.bat"
CHECK_INTERVAL = 5                                  # seconds between each check

# Substrings matched against cmd.exe CommandLine in Win32_Process.
# Must appear in the bat file name so detection is unambiguous.
DJANGO_KEY  = "start_django"
NODERED_KEY = "start_nodered"

# ── Popup helper ───────────────────────────────────────────────────────────────

def popup_warning(title: str, message: str) -> None:
    """Show a warning dialog in a background thread (non-blocking)."""
    def _run() -> None:
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            messagebox.showwarning(title, message, parent=root)
            root.destroy()
        except Exception:
            pass  # silent fallback if tkinter is unavailable
    threading.Thread(target=_run, daemon=True).start()


# ── Process detection ──────────────────────────────────────────────────────────

def find_bat_processes(keyword: str) -> list:
    """
    Return a list of dicts  {pid: int, ticks: int}  for every cmd.exe
    whose Win32_Process.CommandLine contains *keyword*.

    Why PowerShell instead of wmic/tasklist:
      - The PowerShell process (powershell.exe) is filtered out by
        `Name -eq 'cmd.exe'`, so it never inflates the count.
      - This Python process (python.exe) is also excluded.
      - Only the actual cmd.exe windows running the bat files are returned.

    CreationDate.Ticks is used to sort by age (higher = more recently created).
    """
    ps_cmd = (
        "Get-CimInstance Win32_Process "
        "| Where-Object { "
        "    $_.Name -eq 'cmd.exe' -and "
        "    $_.CommandLine -like '*" + keyword + "*' "
        "} "
        "| ForEach-Object { "
        "    $t = if ($_.CreationDate) { $_.CreationDate.Ticks } else { 0 }; "
        '    "$($_.ProcessId)|$t" '
        "}"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=15,
        )
        procs = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if "|" in line:
                pid_str, ticks_str = line.split("|", 1)
                try:
                    procs.append({"pid": int(pid_str), "ticks": int(ticks_str)})
                except ValueError:
                    pass
        return procs
    except Exception as exc:
        print(f"  [ERR ] find_bat_processes({keyword!r}): {exc}")
        return []


# ── Service control ────────────────────────────────────────────────────────────

def start_bat(bat_path: Path) -> None:
    """
    Launch a bat file in a new visible console window.
    - CREATE_NEW_CONSOLE gives it its own window (user can see Django/Node-RED output).
    - cwd=BASE_DIR ensures relative paths inside the bat resolve correctly,
      handling any spaces in the project directory path.
    """
    subprocess.Popen(
        ["cmd", "/c", bat_path.name],
        cwd=str(BASE_DIR),
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )


def kill_tree(pid: int) -> None:
    """Kill a process and all its child processes (cmd.exe + python/node children)."""
    subprocess.run(
        ["taskkill", "/F", "/T", "/PID", str(pid)],
        capture_output=True,
    )


# ── Per-service check ──────────────────────────────────────────────────────────

def check_service(keyword: str, display_name: str, bat_path: Path, alert: dict) -> str:
    """
    Count running instances and act:
      0  → restart immediately + popup alert (once per outage) → 'restarted'
      1  → healthy                                              → 'ok'
      N  → kill newest duplicate, popup                         → 'killed'
    """
    procs = find_bat_processes(keyword)
    count = len(procs)

    if count == 0:
        # Restart immediately before the next check cycle
        start_bat(bat_path)
        if not alert["active"]:
            alert["active"] = True
            popup_warning(
                "Conuar Watchdog – Reinicio automático",
                f"ALERTA: {display_name} se habia detenido.\n\n"
                "El proceso fue reiniciado automaticamente por el Watchdog.",
            )
        return "restarted"

    alert["active"] = False   # service is running, reset alert

    if count == 1:
        return "ok"

    # count > 1: kill the most recently started instance
    newest = max(procs, key=lambda p: p["ticks"])
    kill_tree(newest["pid"])
    popup_warning(
        "Conuar Watchdog – Duplicado detectado",
        f"Se detectó y eliminó una instancia duplicada de {display_name}.\n"
        f"Solo se permite una instancia a la vez.\n"
        f"(PID eliminado: {newest['pid']})",
    )
    return "killed"


# ── Display ────────────────────────────────────────────────────────────────────

STATUS_TAG = {"ok": "[  OK  ]", "down": "[ DOWN ]", "killed": "[ WARN ]", "restarted": "[ AUTO ]"}
STATUS_MSG = {
    "ok":        "En ejecucion",
    "down":      "NO en ejecucion",
    "killed":    "Duplicado detectado y eliminado",
    "restarted": "Detenido — reiniciando automaticamente",
}

SERVICES = [
    {"key": DJANGO_KEY,  "bat": DJANGO_BAT,  "label": "Django Server"},
    {"key": NODERED_KEY, "bat": NODERED_BAT, "label": "Node-RED    "},
]

DESCRIPTION = (
    "Este es el programa orquestador de los componentes de\n"
    "  reporteria de robot de inspeccion de elementos combustibles\n"
    "  en Conuar. Sus componentes son un Webserver Django y un\n"
    "  servicio NodeRed."
)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    os.system("cls")
    print("=" * 60)
    print("  Conuar Watchdog")
    print("=" * 60)
    print(f"  {DESCRIPTION}")
    print("=" * 60)
    print()

    # Startup guard: only start a service if it is not already running
    for svc in SERVICES:
        existing = find_bat_processes(svc["key"])
        if existing:
            print(f"  [SKIP ]  {svc['bat'].name} ya en ejecucion "
                  f"(PID {existing[0]['pid']}).")
        else:
            print(f"  [START]  Iniciando {svc['bat'].name} ...")
            start_bat(svc["bat"])

    print()
    print(f"  Monitoreando cada {CHECK_INTERVAL} segundos. Ctrl+C para detener.")
    print()

    # Per-service alert state (prevents popup spam during sustained outage)
    alert_state = {svc["key"]: {"active": False} for svc in SERVICES}

    # Main monitoring loop
    while True:
        time.sleep(CHECK_INTERVAL)

        os.system("cls")
        now = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
        print("=" * 60)
        print(f"  Conuar Watchdog  |  {now}")
        print("=" * 60)
        print()

        for svc in SERVICES:
            status = check_service(
                svc["key"], svc["label"].strip(), svc["bat"], alert_state[svc["key"]]
            )
            tag = STATUS_TAG[status]
            msg = STATUS_MSG[status]
            print(f"  {tag}  {svc['label']}   {msg}")

        print()
        print(f"  Proximo chequeo en {CHECK_INTERVAL} seg.  Ctrl+C para detener.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Watchdog detenido.")
        sys.exit(0)
