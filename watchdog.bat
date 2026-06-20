@echo off
setlocal EnableDelayedExpansion
title Conuar Watchdog

:: ============================================================
::  CONFIGURATION
:: ============================================================
set "BASE_DIR=C:\Users\usuario\Documents\GitHub\Inspection_webapp"
set "DJANGO_BAT=%BASE_DIR%\start_django.bat"
set "NODERED_BAT=%BASE_DIR%\start_nodered.bat"
set "DJANGO_PORT=8000"
set "NODERED_PORT=1880"
set "CHECK_INTERVAL=5"

:: ============================================================
::  SINGLE-INSTANCE GUARD (window title detection)
::  Counts cmd.exe processes whose title is "Conuar Watchdog".
::  If more than one exists this is a duplicate — exit.
:: ============================================================
powershell -NoProfile -Command "$w = Get-Process cmd -EA SilentlyContinue | Where-Object { $_.MainWindowTitle -eq 'Conuar Watchdog' }; if ($w.Count -gt 1) { exit 1 } else { exit 0 }"
if errorlevel 1 (
    powershell -NoProfile -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('Conuar Watchdog is already running.`n`nClose the existing watchdog window first.', 'Already Running', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Information)"
    exit /b 0
)

:: Alert-shown flags: prevents alert spam while a service is starting up
set "DJANGO_ALERT_SHOWN=0"
set "NODERED_ALERT_SHOWN=0"

:: ============================================================
::  MAIN WATCHDOG LOOP
:: ============================================================
:CHECK_LOOP
cls
echo ============================================================
echo   Conuar Watchdog  ^|  %date%   %time:~0,8%
echo ============================================================
echo.

:: -- Port checks --
powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort %DJANGO_PORT% -State Listen -EA SilentlyContinue) { exit 0 } else { exit 1 }"
if errorlevel 1 (set "DJANGO_OK=0") else (set "DJANGO_OK=1")

powershell -NoProfile -Command "if (Get-NetTCPConnection -LocalPort %NODERED_PORT% -State Listen -EA SilentlyContinue) { exit 0 } else { exit 1 }"
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

:: ============================================================
::  DJANGO: auto-start if down, then kill any duplicates
:: ============================================================
if "!DJANGO_OK!"=="0" (
    if "!DJANGO_ALERT_SHOWN!"=="0" (
        set "DJANGO_ALERT_SHOWN=1"
        :: Non-blocking alert — watchdog does NOT wait for user to click OK
        start /B "" powershell -NoProfile -WindowStyle Hidden -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('Django server (port %DJANGO_PORT%) is NOT running.`nStarting start_django.bat automatically...', 'Conuar Watchdog — Django Down', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Warning)"
        start "" "%DJANGO_BAT%"
        echo   [ AUTO ]  Starting start_django.bat...
    ) else (
        echo   [ WAIT ]  Django is starting, waiting for port %DJANGO_PORT%...
    )
) else (
    set "DJANGO_ALERT_SHOWN=0"
)

:: Kill any duplicate start_django.bat processes (keep only the oldest PID)
powershell -NoProfile -Command "$procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*start_django*' } | Sort-Object ProcessId; if ($procs.Count -gt 1) { $procs | Select-Object -Skip 1 | ForEach-Object { [void](& taskkill /F /T /PID $_.ProcessId 2>&1) }; exit 1 }; exit 0"
if errorlevel 1 (
    start /B "" powershell -NoProfile -WindowStyle Hidden -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('A duplicate Django instance was detected and stopped!`nOnly one start_django.bat is allowed while the watchdog is running.', 'Conuar Watchdog — Duplicate Blocked', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Warning)"
    echo   [ STOP ]  Duplicate start_django.bat detected and terminated.
)

:: ============================================================
::  NODE-RED: auto-start if down, then kill any duplicates
:: ============================================================
if "!NODERED_OK!"=="0" (
    if "!NODERED_ALERT_SHOWN!"=="0" (
        set "NODERED_ALERT_SHOWN=1"
        start /B "" powershell -NoProfile -WindowStyle Hidden -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('Node-RED (port %NODERED_PORT%) is NOT running.`nStarting start_nodered.bat automatically...', 'Conuar Watchdog — Node-RED Down', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Warning)"
        start "" "%NODERED_BAT%"
        echo   [ AUTO ]  Starting start_nodered.bat...
    ) else (
        echo   [ WAIT ]  Node-RED is starting, waiting for port %NODERED_PORT%...
    )
) else (
    set "NODERED_ALERT_SHOWN=0"
)

:: Kill any duplicate start_nodered.bat processes (keep only the oldest PID)
powershell -NoProfile -Command "$procs = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*start_nodered*' } | Sort-Object ProcessId; if ($procs.Count -gt 1) { $procs | Select-Object -Skip 1 | ForEach-Object { [void](& taskkill /F /T /PID $_.ProcessId 2>&1) }; exit 1 }; exit 0"
if errorlevel 1 (
    start /B "" powershell -NoProfile -WindowStyle Hidden -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('A duplicate Node-RED instance was detected and stopped!`nOnly one start_nodered.bat is allowed while the watchdog is running.', 'Conuar Watchdog — Duplicate Blocked', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Warning)"
    echo   [ STOP ]  Duplicate start_nodered.bat detected and terminated.
)

echo   Next check in %CHECK_INTERVAL% seconds.  Press Ctrl+C to stop.
timeout /t %CHECK_INTERVAL% /nobreak >nul

goto CHECK_LOOP
