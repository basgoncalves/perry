@echo off
REM ============================================================
REM  One-time setup: turn your image into an icon and build the
REM  clickable "Perry" shortcut.
REM
REM  BEFORE running: save your BioScout image into THIS folder
REM  and name it  icon_source.png
REM ============================================================

cd /d "%~dp0"

echo.
echo [1/2] Building perry.ico from your image...
python make_icon.py
if errorlevel 1 (
    echo.
    echo Could not build the icon. Make sure Pillow is installed:
    echo     pip install pillow
    echo and that your image is saved here as  icon_source.png
    echo.
)

echo.
echo [2/2] Creating the Perry shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_shortcut.ps1"

echo.
echo Done. Double-click "Perry" (in this folder or on your Desktop) to launch.
pause
