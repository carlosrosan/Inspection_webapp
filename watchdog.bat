@echo off
setlocal EnableDelayedExpansion
title Conuar Watchdog

:: ============================================================
::  CONFIGURATION
::  All paths are resolved relative to this file's directory.
:: ============================================================
set "DJANGO_BAT=%~dp0start_django.bat"
set "NODERED_BAT=%~dp0start_nodered.bat"
set "CHECK_INTERVAL=5"

:: ============================================================
::  SINGLE-INSTANCE GUARD
::  Count cmd.exe windows already titled "Conuar Watchdog".
::  If > 1, this run is a duplicate — popup and exit.
:: ============================================================
powershell -NoProfile -Command "$w = Get-Process cmd -EA SilentlyContinue | Where-Object { $_.MainWindowTitle -eq 'Conuar Watchdog' }; if ($w.Count -gt 1) { exit 1 } else { exit 0 }"
if errorlevel 1 (
    powershell -NoProfile -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('Conuar Watchdog ya est' + [char]225 + ' en ejecuci' + [char]243 + 'n.`n`nCierre la ventana existente primero.', 'Instancia duplicada', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Information)"
    exit /b 0
)

:: ============================================================
::  STARTUP
::  Launch each service only if it is not already running.
::  Detection: look for cmd.exe whose CommandLine contains
::  the bat file name. Filter Name='cmd.exe' to exclude the
::  PowerShell process running this very query.
:: ============================================================
echo Iniciando Conuar Watchdog...
echo.

powershell -NoProfile -Command "if ((Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'cmd.exe' -and $_.CommandLine -like '*start_django*' }).Count -gt 0) { exit 1 } else { exit 0 }"
if errorlevel 1 (
    echo   [SKIP ]  start_django.bat  ya en ejecucion.
) else (
    echo   [START]  Iniciando start_django.bat...
    start "" "%DJANGO_BAT%"
)

powershell -NoProfile -Command "if ((Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'cmd.exe' -and $_.CommandLine -like '*start_nodered*' }).Count -gt 0) { exit 1 } else { exit 0 }"
if errorlevel 1 (
    echo   [SKIP ]  start_nodered.bat ya en ejecucion.
) else (
    echo   [START]  Iniciando start_nodered.bat...
    start "" "%NODERED_BAT%"
)

echo.

:: Flags — avoid showing the same alert popup repeatedly while a service is down
set "DJANGO_ALERT=0"
set "NODERED_ALERT=0"

:: ============================================================
::  MAIN WATCHDOG LOOP
::
::  PowerShell exit codes used as process-count signals:
::    0 = zero instances running   -> show popup alert
::    1 = exactly one running      -> OK, do nothing
::    2 = had duplicates, killed newest -> show popup + log
::
::  "Kill newest" = sort by CreationDate descending, take [0].
::  taskkill /F /T kills the whole process tree (cmd + children).
:: ============================================================
:CHECK_LOOP
cls
echo ============================================================
echo   Conuar Watchdog  ^|  %date%   %time:~0,8%
echo ============================================================
echo.

:: ---------- Django ----------
powershell -NoProfile -Command "$p = Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'cmd.exe' -and $_.CommandLine -like '*start_django*' } | Sort-Object CreationDate -Descending; if ($p.Count -eq 0) { exit 0 }; if ($p.Count -eq 1) { exit 1 }; [void](& taskkill /F /T /PID $p[0].ProcessId 2>&1); exit 2"
set "DS=!errorlevel!"

if "!DS!"=="0" (
    echo   [ DOWN ]  start_django.bat    NO en ejecucion
    if "!DJANGO_ALERT!"=="0" (
        set "DJANGO_ALERT=1"
        start /B "" powershell -NoProfile -WindowStyle Hidden -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('ALERTA: start_django.bat no est' + [char]225 + ' en ejecuci' + [char]243 + 'n.`n`nEl servidor Django se ha detenido inesperadamente.', 'Conuar Watchdog', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Warning)"
    )
)
if "!DS!"=="1" (
    echo   [  OK  ]  start_django.bat    En ejecucion
    set "DJANGO_ALERT=0"
)
if "!DS!"=="2" (
    echo   [ WARN ]  start_django.bat    Duplicado eliminado
    set "DJANGO_ALERT=0"
    start /B "" powershell -NoProfile -WindowStyle Hidden -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('Se detect' + [char]243 + ' y cerr' + [char]243 + ' una instancia duplicada de start_django.bat.`nSolo se permite una instancia a la vez.', 'Conuar Watchdog - Duplicado', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Warning)"
)

:: ---------- Node-RED ----------
powershell -NoProfile -Command "$p = Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'cmd.exe' -and $_.CommandLine -like '*start_nodered*' } | Sort-Object CreationDate -Descending; if ($p.Count -eq 0) { exit 0 }; if ($p.Count -eq 1) { exit 1 }; [void](& taskkill /F /T /PID $p[0].ProcessId 2>&1); exit 2"
set "NS=!errorlevel!"

if "!NS!"=="0" (
    echo   [ DOWN ]  start_nodered.bat   NO en ejecucion
    if "!NODERED_ALERT!"=="0" (
        set "NODERED_ALERT=1"
        start /B "" powershell -NoProfile -WindowStyle Hidden -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('ALERTA: start_nodered.bat no est' + [char]225 + ' en ejecuci' + [char]243 + 'n.`n`nNode-RED se ha detenido inesperadamente.', 'Conuar Watchdog', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Warning)"
    )
)
if "!NS!"=="1" (
    echo   [  OK  ]  start_nodered.bat   En ejecucion
    set "NODERED_ALERT=0"
)
if "!NS!"=="2" (
    echo   [ WARN ]  start_nodered.bat   Duplicado eliminado
    set "NODERED_ALERT=0"
    start /B "" powershell -NoProfile -WindowStyle Hidden -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('Se detect' + [char]243 + ' y cerr' + [char]243 + ' una instancia duplicada de start_nodered.bat.`nSolo se permite una instancia a la vez.', 'Conuar Watchdog - Duplicado', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Warning)"
)

echo.
echo   Proximo chequeo en %CHECK_INTERVAL% seg.  Ctrl+C para detener.
timeout /t %CHECK_INTERVAL% /nobreak >nul
goto CHECK_LOOP
