#ifndef AppName
#define AppName "PVT Simulator"
#endif
#ifndef AppVersion
#define AppVersion "0.1.0"
#endif
#ifndef AppPublisher
#define AppPublisher "Ole"
#endif
#ifndef AppExeName
#define AppExeName "pvtsim.exe"
#endif
#ifndef DistDir
#define DistDir "dist\\pvtsim"
#endif
#ifndef OutputDir
#define OutputDir "dist_installer"
#endif

[Setup]
AppId={{C1E0D2C7-1B88-4F4A-9B3A-8B5A3E4C2F11}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\\{#AppName}
DefaultGroupName={#AppName}
OutputDir={#OutputDir}
OutputBaseFilename=PVTSimulatorSetup-{#AppVersion}
Compression=lzma
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\\{#AppExeName}

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; Flags: unchecked

[Files]
Source: "{#DistDir}\\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\\{#AppName}"; Filename: "{app}\\{#AppExeName}"
Name: "{commondesktop}\\{#AppName}"; Filename: "{app}\\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
