# create_shortcut.ps1
# Builds "Perry.lnk" in this folder. Clicking it launches Perry silently,
# and the shortcut wears the BioScout icon (perry.ico).

$here    = Split-Path -Parent $MyInvocation.MyCommand.Definition
$vbs     = Join-Path $here "launch_perry.vbs"
$ico     = Join-Path $here "perry.ico"
$lnkPath = Join-Path $here "Perry.lnk"

if (-not (Test-Path $ico)) {
    Write-Host "perry.ico not found — the shortcut will use a default icon."
    Write-Host "Run 'python make_icon.py' first to generate it from your image."
}

$shell = New-Object -ComObject WScript.Shell
$lnk   = $shell.CreateShortcut($lnkPath)
$lnk.TargetPath       = "wscript.exe"
$lnk.Arguments        = '"' + $vbs + '"'
$lnk.WorkingDirectory = $here
$lnk.Description       = "Launch Perry — self-checks its environment, then starts"
if (Test-Path $ico) { $lnk.IconLocation = $ico }
$lnk.Save()

Write-Host "Created $lnkPath"

# Optional: also drop a copy on the Desktop.
$desktop = [Environment]::GetFolderPath("Desktop")
$deskLnk = Join-Path $desktop "Perry.lnk"
$lnk2 = $shell.CreateShortcut($deskLnk)
$lnk2.TargetPath       = "wscript.exe"
$lnk2.Arguments        = '"' + $vbs + '"'
$lnk2.WorkingDirectory = $here
$lnk2.Description       = "Launch Perry — your Jarvis assistant"
if (Test-Path $ico) { $lnk2.IconLocation = $ico }
$lnk2.Save()
Write-Host "Created $deskLnk"
