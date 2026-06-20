@echo off
setlocal EnableDelayedExpansion
title Conuar Watchdog
set "CHECK_INTERVAL=5"

:: ============================================================
::  STARTUP
::  Change to this file's directory so relative paths work
::  even when launched from a shortcut or Task Scheduler.
::  Guard: start each service ONLY if its titled window is
::  not already open (window title is set by the start command
::  below and persists for the lifetime of the process).
:: ============================================================
pushd "%~dp0"
echo Conuar Watchdog iniciando...
echo.

powershell -NoProfile -Command "if (Get-Process cmd -EA SilentlyContinue | Where-Object { $_.MainWindowTitle -eq 'Django Server' }) { exit 1 } else { exit 0 }"
if errorlevel 1 (
    echo   [SKIP ]  Django Server ya en ejecucion.
) else (
    echo   [START]  Iniciando start_django.bat...
    start "Django Server" cmd /c "start_django.bat"
)

powershell -NoProfile -Command "if (Get-Process cmd -EA SilentlyContinue | Where-Object { $_.MainWindowTitle -eq 'Node-RED' }) { exit 1 } else { exit 0 }"
if errorlevel 1 (
    echo   [SKIP ]  Node-RED ya en ejecucion.
) else (
    echo   [START]  Iniciando start_nodered.bat...
    start "Node-RED" cmd /c "start_nodered.bat"
)

popd
echo.

:: Flags: show each alert only once per downtime episode
set "DJANGO_ALERT=0"
set "NODERED_ALERT=0"

:: ============================================================
::  MAIN WATCHDOG LOOP
::
::  Detection uses window title, NOT CommandLine text.
::  This avoids false positives from the PowerShell process
::  that runs the query (which itself contains "start_django"
::  in its own command line and would inflate the count).
::
::  PowerShell exit codes:
::    0 = 0 windows found  -> service is down, show alert
::    1 = 1 window found   -> OK
::    2 = 2+ windows found -> killed the newest, show alert
::
::  taskkill /F /T kills the cmd.exe AND all its children
::  (python / node-red processes).
:: ============================================================
:CHECK_LOOP
cls
echo ============================================================
echo   Conuar Watchdog  ^|  %date%   %time:~0,8%
echo ============================================================
echo.

:: ---------- Django ----------
powershell -NoProfile -Command "$p = Get-Process cmd -EA SilentlyContinue | Where-Object { $_.MainWindowTitle -eq 'Django Server' }; if ($p.Count -eq 0) { exit 0 }; if ($p.Count -eq 1) { exit 1 }; $n = ($p | Sort-Object StartTime -Descending | Select-Object -First 1).Id; [void](& taskkill /F /T /PID $n 2>&1); exit 2"
set "DS=!errorlevel!"

if "!DS!"=="0" (
    echo   [ DOWN ]  Django Server    NO en ejecucion
    if "!DJANGO_ALERT!"=="0" (
        set "DJANGO_ALERT=1"
        start /B "" powershell -NoProfile -WindowStyle Hidden -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('ALERTA: Django Server no est' + [char]225 + ' en ejecuci' + [char]243 + 'n.`n`nEl servidor se ha detenido inesperadamente.', 'Conuar Watchdog', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Warning)"
    )
)
if "!DS!"=="1" (
    echo   [  OK  ]  Django Server    En ejecucion
    set "DJANGO_ALERT=0"
)
if "!DS!"=="2" (
    echo   [ WARN ]  Django Server    Duplicado detectado y eliminado
    set "DJANGO_ALERT=0"
    start /B "" powershell -NoProfile -WindowStyle Hidden -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('Se detect' + [char]243 + ' y cerr' + [char]243 + ' una instancia duplicada de Django Server.`nSolo se permite una instancia.', 'Conuar Watchdog - Duplicado', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Warning)"
)

:: ---------- Node-RED ----------
powershell -NoProfile -Command "$p = Get-Process cmd -EA SilentlyContinue | Where-Object { $_.MainWindowTitle -eq 'Node-RED' }; if ($p.Count -eq 0) { exit 0 }; if ($p.Count -eq 1) { exit 1 }; $n = ($p | Sort-Object StartTime -Descending | Select-Object -First 1).Id; [void](& taskkill /F /T /PID $n 2>&1); exit 2"
set "NS=!errorlevel!"

if "!NS!"=="0" (
    echo   [ DOWN ]  Node-RED         NO en ejecucion
    if "!NODERED_ALERT!"=="0" (
        set "NODERED_ALERT=1"
        start /B "" powershell -NoProfile -WindowStyle Hidden -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('ALERTA: Node-RED no est' + [char]225 + ' en ejecuci' + [char]243 + 'n.`n`nEl servicio se ha detenido inesperadamente.', 'Conuar Watchdog', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Warning)"
    )
)
if "!NS!"=="1" (
    echo   [  OK  ]  Node-RED         En ejecucion
    set "NODERED_ALERT=0"
)
if "!NS!"=="2" (
    echo   [ WARN ]  Node-RED         Duplicado detectado y eliminado
    set "NODERED_ALERT=0"
    start /B "" powershell -NoProfile -WindowStyle Hidden -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('Se detect' + [char]243 + ' y cerr' + [char]243 + ' una instancia duplicada de Node-RED.`nSolo se permite una instancia.', 'Conuar Watchdog - Duplicado', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Warning)"
)

echo.
echo   Proximo chequeo en %CHECK_INTERVAL% seg.  Ctrl+C para detener.
timeout /t %CHECK_INTERVAL% /nobreak >nul
goto CHECK_LOOP
