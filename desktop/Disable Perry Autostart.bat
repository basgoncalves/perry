@echo off
REM Stops Perry from starting automatically at login.
REM (Any Perry that's already running keeps running until you quit it
REM  with the power icon on the HUD.)

cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_autostart.ps1" -Remove
pause
