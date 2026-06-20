@echo off
:: ── Conuar Watchdog launcher ──────────────────────────────────────────────────
:: Tries the project's virtual-environment Python first, falls back to system Python.
set "VENV_PY=%~dp0conuar_env\Scripts\python.exe"
set "SCRIPT=%~dp0watchdog.py"

if exist "%VENV_PY%" (
    "%VENV_PY%" "%SCRIPT%"
) else (
    python "%SCRIPT%"
)
pause
