# install_autostart.ps1
#
# Puts Perry in the Windows Startup folder so he's listening for your claps
# from the moment you log in — no window, no console, no taskbar entry.
#
#   Enable :  powershell -ExecutionPolicy Bypass -File .\install_autostart.ps1
#   Disable:  powershell -ExecutionPolicy Bypass -File .\install_autostart.ps1 -Remove
#
# The shortcut points at launch_perry.vbs, which runs bootstrap.py hidden.
# bootstrap.py verifies the venv and dependencies, then starts Perry.

param([switch]$Remove)

$here    = Split-Path -Parent $MyInvocation.MyCommand.Definition
$vbs     = Join-Path $here "launch_perry.vbs"
$ico     = Join-Path $here "perry.ico"
$startup = [Environment]::GetFolderPath("Startup")
$lnkPath = Join-Path $startup "Perry.lnk"

if ($Remove) {
    if (Test-Path $lnkPath) {
        Remove-Item $lnkPath -Force
        Write-Host "Autostart disabled - removed $lnkPath"
    } else {
        Write-Host "Autostart was not enabled (nothing to remove)."
    }
    return
}

if (-not (Test-Path $vbs)) {
    Write-Error "launch_perry.vbs not found in $here - run this from the Perry folder."
    return
}

$shell = New-Object -ComObject WScript.Shell
$lnk   = $shell.CreateShortcut($lnkPath)
$lnk.TargetPath       = "wscript.exe"
$lnk.Arguments        = '"' + $vbs + '"'
$lnk.WorkingDirectory = $here
$lnk.WindowStyle      = 7          # minimised; the VBS itself runs fully hidden
$lnk.Description      = "Perry - starts listening at login (clap twice to wake)"
if (Test-Path $ico) { $lnk.IconLocation = $ico }
$lnk.Save()

Write-Host "Autostart enabled."
Write-Host "  Shortcut: $lnkPath"
Write-Host "  Perry will start hidden at login and listen for two claps."
Write-Host ""
Write-Host "To turn it off later, run this script again with -Remove."
