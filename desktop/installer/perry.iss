; Inno Setup script: builds PerrySetup.exe from the PyInstaller output in dist\Perry.
; Per-user install (no admin prompt) into %LOCALAPPDATA%\Programs\Perry.
#define AppVersion GetEnv("PERRY_VERSION")
#if AppVersion == ""
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{6E2B0F2A-7D1C-4C8E-9A51-5F0D3B9C7A11}
AppName=Perry
AppVersion={#AppVersion}
AppPublisher=Basilio Goncalves
AppPublisherURL=https://basgoncalves.github.io/perry/
DefaultDirName={localappdata}\Programs\Perry
DefaultGroupName=Perry
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=PerrySetup
SetupIconFile=..\perry.ico
UninstallDisplayIcon={app}\Perry.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Shortcuts:"
Name: "autostart"; Description: "Start Perry quietly when I sign in to Windows"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
Source: "..\dist\Perry\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; keep the user's settings and balloons on upgrade
Source: "..\config.json"; DestDir: "{app}\_internal"; Flags: onlyifdoesntexist uninsneveruninstall

[Icons]
Name: "{autoprograms}\Perry"; Filename: "{app}\Perry.exe"; IconFilename: "{app}\Perry.exe"
Name: "{autodesktop}\Perry"; Filename: "{app}\Perry.exe"; IconFilename: "{app}\Perry.exe"; Tasks: desktopicon
Name: "{userstartup}\Perry"; Filename: "{app}\Perry.exe"; Parameters: "--hidden"; Tasks: autostart

[Run]
Filename: "{app}\Perry.exe"; Description: "Launch Perry now"; Flags: nowait postinstall skipifsilent
