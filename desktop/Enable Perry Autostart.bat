@echo off
REM Makes Perry start listening automatically every time you log in to Windows.
REM Double-click this file once. To undo it, run "Disable Perry Autostart.bat".

cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_autostart.ps1"
echo.
echo Starting Perry now so you don't have to log out and back in...
wscript "%~dp0launch_perry.vbs"
echo.
echo Done. Clap twice, then say "Perry wake up".
pause
