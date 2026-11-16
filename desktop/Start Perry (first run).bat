@echo off
REM Visible first-run launcher. Shows setup progress while Perry builds its
REM environment and installs dependencies. After the first run you can just
REM use the Perry shortcut / icon.

cd /d "%~dp0"
title Perry - setup and launch
echo Setting up Perry. This may take a couple of minutes the first time...
echo.
python bootstrap.py
echo.
echo If Perry didn't appear, check the messages above.
timeout /t 6 >nul
