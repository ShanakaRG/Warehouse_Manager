@echo off
rem ============================================================================
rem  Warehouse Manager - Windows runner
rem  Double-click for the menu, or use:  runner.bat start ^| check ^| selftest ^|
rem                                      install ^| test ^| build ^| shortcut
rem  Developer: Shanaka Ramesh - Infinite_engineering solution
rem ============================================================================
setlocal EnableExtensions
cd /d "%~dp0"
title Warehouse Manager - Runner

rem ---- Find a working Python: the "py" launcher first, then "python" on PATH ----
rem      (the Microsoft Store "python" placeholder fails --version, so it is skipped)
set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY python --version >nul 2>&1 && set "PY=python"
if not defined PY goto no_python
for /f "delims=" %%v in ('%PY% --version 2^>^&1') do set "PYVER=%%v"

if not "%~1"=="" goto direct

:menu
cls
echo.
echo   ==========================================================
echo     WAREHOUSE MANAGER  -  Runner
echo   ==========================================================
echo     Using %PYVER%  (%PY%)
echo.
echo     1   Start Warehouse Manager
echo     2   Check system   (Python, Tkinter, Excel library, database)
echo     3   Self-test      (tests stock rules on a temporary database)
echo     4   Install / update libraries
echo     5   Developer tests (pytest)
echo     6   Build Windows program (.exe)
echo     7   Open data folder
echo     8   Create desktop shortcut
echo     0   Exit
echo.
set "choice="
set /p "choice=    Type a number and press Enter: "

if "%choice%"=="1" goto menu_start
if "%choice%"=="2" set "ARG=--check"    & goto menu_run
if "%choice%"=="3" set "ARG=--selftest" & goto menu_run
if "%choice%"=="4" set "ARG=--install"  & goto menu_run
if "%choice%"=="5" set "ARG=--test"     & goto menu_run
if "%choice%"=="6" set "ARG=--build"    & goto menu_run
if "%choice%"=="7" goto open_data
if "%choice%"=="8" goto shortcut_menu
if "%choice%"=="0" exit /b 0
echo.
echo     "%choice%" is not an option. Type a number from 0 to 8.
timeout /t 2 >nul
goto menu

:menu_start
echo.
%PY% run.py
if errorlevel 1 (
    echo.
    echo   The program reported a problem. Read the messages above,
    echo   then try option 2 ^(Check system^).
    pause
)
goto menu

:menu_run
echo.
%PY% run.py %ARG%
echo.
pause
goto menu

:open_data
if not exist "%APPDATA%\WarehouseManager" mkdir "%APPDATA%\WarehouseManager"
start "" "%APPDATA%\WarehouseManager"
goto menu

:shortcut_menu
call :make_shortcut
pause
goto menu

rem ---- Command-line use: runner.bat <command> ---------------------------------
:direct
set "ARG="
if /i "%~1"=="start"    goto direct_start
if /i "%~1"=="check"    set "ARG=--check"
if /i "%~1"=="selftest" set "ARG=--selftest"
if /i "%~1"=="install"  set "ARG=--install"
if /i "%~1"=="test"     set "ARG=--test"
if /i "%~1"=="build"    set "ARG=--build"
if /i "%~1"=="shortcut" goto make_shortcut
if not defined ARG goto usage
%PY% run.py %ARG%
exit /b

:direct_start
%PY% run.py
if errorlevel 1 pause
exit /b

:make_shortcut
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s = (New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Warehouse Manager.lnk');" ^
  "$s.TargetPath = '%~dp0runner.bat'; $s.Arguments = 'start'; $s.WorkingDirectory = '%~dp0';" ^
  "$s.IconLocation = '%~dp0assets\app.ico'; $s.WindowStyle = 7; $s.Save()"
if errorlevel 1 (
    echo   [FAIL] Could not create the shortcut.
) else (
    echo   [ OK ] "Warehouse Manager" shortcut created on the desktop.
)
exit /b

:usage
echo Usage: runner.bat [start ^| check ^| selftest ^| install ^| test ^| build ^| shortcut]
echo        Run without a command to open the menu.
exit /b 1

:no_python
echo.
echo   [FAIL] Python was not found on this computer.
echo.
echo   1. Download Python 3.9 or newer from https://www.python.org/downloads/
echo   2. In the installer, tick "Add python.exe to PATH"
echo      and keep "tcl/tk and IDLE" ticked (needed for the windows).
echo   3. Run this file again.
echo.
pause
exit /b 1
