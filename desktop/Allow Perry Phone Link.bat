@echo off
rem Opens Windows Firewall for Perry phone link (TCP 47812, private networks only).
net session >nul 2>&1 || (powershell -Command "Start-Process '%~f0' -Verb RunAs" & exit /b)
netsh advfirewall firewall delete rule name="Perry Phone Link" >nul 2>&1
netsh advfirewall firewall add rule name="Perry Phone Link" dir=in action=allow protocol=TCP localport=47812 profile=private
echo Done. Perry's phone link is allowed on private Wi-Fi.
pause
