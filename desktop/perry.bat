@echo off
REM Global launcher for Perry - lets you type "perry" from any terminal/folder.
REM Runs the same silent launch path as the Startup shortcut (launch_perry.vbs),
REM using an absolute path so it works no matter where you run it from.
wscript.exe "%~dp0launch_perry.vbs"
