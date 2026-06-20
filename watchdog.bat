@echo off
setlocal EnableDelayedExpansion
title Conuar Watchdog

:: ============================================================
::  CONFIGURATION — update BASE_DIR if the project moves
:: ============================================================
set "BASE_DIR=C:\Users\usuario\Documents\GitHub\Inspection_webapp"
set "DJANGO_BAT=%BASE_DIR%\start_django.bat"
set "NODERED_BAT=%BASE_DIR%\start_nodered.bat"
set "DJANGO_PORT=8000"
set "NODERED_PORT=1880"
set "CHECK_INTERVAL=5"

:: ============================================================
::  SINGLE-INSTANCE GUARD
::  Checks how many cmd.exe windows already carry the title
::  "Conuar Watchdog". If more than one exists, this instance
::  is a duplicate — show a popup and exit immediately.
::  This avoids the stale-PID bug of the dir-lock approach.
:: ============================================================
powershell -NoProfile -Command ^
    "$w = Get-Process cmd -EA SilentlyContinue | Where-Object { $_.MainWindowTitle -eq 'Conuar Watchdog' }; if ($w.Count -gt 1) { exit 1 } else { exit 0 }"
if errorlevel 1 (
    powershell -NoProfile -Command ^
        "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('Conuar Watchdog is already running.`n`nClose the existing watchdog window first.', 'Already Running', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Information)"
    exit /b 0
)

:: ============================================================
::  MAIN WATCHDOG LOOP
:: ============================================================
:CHECK_LOOP
cls
echo ============================================================
echo   Conuar Watchdog  ^|  %date%   %time:~0,8%
echo ============================================================
echo.

:: -- Check Django (port 8000) --
powershell -NoProfile -Command ^
    "if (Get-NetTCPConnection -LocalPort %DJANGO_PORT% -State Listen -EA SilentlyContinue) { exit 0 } else { exit 1 }"
if errorlevel 1 (set "DJANGO_OK=0") else (set "DJANGO_OK=1")

:: -- Check Node-RED (port 1880) --
powershell -NoProfile -Command ^
    "if (Get-NetTCPConnection -LocalPort %NODERED_PORT% -State Listen -EA SilentlyContinue) { exit 0 } else { exit 1 }"
if errorlevel 1 (set "NODERED_OK=0") else (set "NODERED_OK=1")

:: -- Status display --
if "!DJANGO_OK!"=="1" (
    echo   [  OK  ]  Django Server   port %DJANGO_PORT%   Running
) else (
    echo   [ DOWN ]  Django Server   port %DJANGO_PORT%   NOT running
)
if "!NODERED_OK!"=="1" (
    echo   [  OK  ]  Node-RED        port %NODERED_PORT%   Running
) else (
    echo   [ DOWN ]  Node-RED        port %NODERED_PORT%   NOT running
)
echo.

:: -- Alert + optional restart for Django --
if "!DJANGO_OK!"=="0" (
    powershell -NoProfile -Command ^
        "Add-Type -AssemblyName System.Windows.Forms; $r = [System.Windows.Forms.MessageBox]::Show('Django server (port %DJANGO_PORT%) is NOT running.`n`nWould you like to start start_django.bat now?', 'Conuar Watchdog — Django Down', [System.Windows.Forms.MessageBoxButtons]::YesNo, [System.Windows.Forms.MessageBoxIcon]::Warning); if ($r -eq [System.Windows.Forms.DialogResult]::Yes) { exit 0 } else { exit 1 }"
    if not errorlevel 1 (
        :: Re-check port immediately before launching to block accidental double-start
        powershell -NoProfile -Command ^
            "if (Get-NetTCPConnection -LocalPort %DJANGO_PORT% -State Listen -EA SilentlyContinue) { exit 1 } else { exit 0 }"
        if not errorlevel 1 start "" "%DJANGO_BAT%"
    )
)

:: -- Alert + optional restart for Node-RED --
if "!NODERED_OK!"=="0" (
    powershell -NoProfile -Command ^
        "Add-Type -AssemblyName System.Windows.Forms; $r = [System.Windows.Forms.MessageBox]::Show('Node-RED (port %NODERED_PORT%) is NOT running.`n`nWould you like to start start_nodered.bat now?', 'Conuar Watchdog — Node-RED Down', [System.Windows.Forms.MessageBoxButtons]::YesNo, [System.Windows.Forms.MessageBoxIcon]::Warning); if ($r -eq [System.Windows.Forms.DialogResult]::Yes) { exit 0 } else { exit 1 }"
    if not errorlevel 1 (
        powershell -NoProfile -Command ^
            "if (Get-NetTCPConnection -LocalPort %NODERED_PORT% -State Listen -EA SilentlyContinue) { exit 1 } else { exit 0 }"
        if not errorlevel 1 start "" "%NODERED_BAT%"
    )
)

echo   Next check in %CHECK_INTERVAL% seconds.  Press Ctrl+C to stop.
timeout /t %CHECK_INTERVAL% /nobreak >nul

goto CHECK_LOOP