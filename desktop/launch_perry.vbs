' launch_perry.vbs
' Silent launcher for Perry. Runs bootstrap.py, which checks/repairs the
' virtual environment and dependencies, then starts Perry. A brief console
' may flash on first run while it installs things.

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = scriptDir

' Use system Python for bootstrap (it may need to CREATE the venv).
' 'python' must be on PATH. Window style 0 = hidden, False = don't wait.
shell.Run "python """ & scriptDir & "\bootstrap.py""", 0, False
