; ============================================================
; RustChain Miner — Inno Setup Script
; Produces a professional Windows installer (Setup wizard)
; ============================================================
; Prerequisite: Inno Setup 6+ (https://jrsoftware.org/isinfo.php)
; Build command:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" rustchain_setup.iss
; ============================================================

#define MyAppName "RustChain Miner"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "RustChain"
#define MyAppURL "https://rustchain.org"
#define MyAppExeName "RustChainMiner.exe"

[Setup]
AppId={{E7A3B2C1-4D5F-6A7B-8C9D-0E1F2A3B4C5D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={localappdata}\RustChain
DefaultGroupName={#MyAppName}
OutputDir=output
OutputBaseFilename=RustChainSetup_v{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
SetupIconFile=assets\rustchain.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
; No admin required — installs to user's AppData
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

; ============================================================
; Custom Wizard Page — Wallet Name Input
; ============================================================
[Code]
var
  WalletPage: TInputQueryWizardPage;

procedure InitializeWizard;
begin
  WalletPage := CreateInputQueryPage(
    wpSelectDir,
    'Wallet Configuration',
    'Enter your RustChain wallet name',
    'This name identifies your mining wallet. You can change it later in config.json.'
  );
  WalletPage.Add('Wallet Name:', False);
  WalletPage.Values[0] := 'MyWallet';
end;

procedure WriteConfigJson;
var
  ConfigDir: String;
  ConfigFile: String;
  Lines: TStringList;
begin
  ConfigDir := ExpandConstant('{userappdata}\RustChain');
  ForceDirectories(ConfigDir);
  ForceDirectories(ConfigDir + '\logs');

  ConfigFile := ConfigDir + '\config.json';
  Lines := TStringList.Create;
  try
    Lines.Add('{');
    Lines.Add('  "wallet_name": "' + WalletPage.Values[0] + '",');
    Lines.Add('  "auto_start": false,');
    Lines.Add('  "minimize_to_tray": true,');
    Lines.Add('  "node_url": "https://rustchain.org",');
    Lines.Add('  "log_level": "INFO",');
    Lines.Add('  "version": "1.0.0"');
    Lines.Add('}');
    Lines.SaveToFile(ConfigFile);
  finally
    Lines.Free;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    WriteConfigJson;
  end;
end;

// ============================================================
// Files to Install
// ============================================================
[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "scripts\start_miner.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "scripts\stop_miner.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "scripts\open_logs.bat"; DestDir: "{app}"; Flags: ignoreversion
; Include icon if present
Source: "assets\rustchain.ico"; DestDir: "{app}\assets"; Flags: ignoreversion skipifsourcedoesntexist

; ============================================================
; Start Menu Shortcuts
; ============================================================
[Icons]
Name: "{group}\Start RustChain Miner"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--minimized"; IconFilename: "{app}\assets\rustchain.ico"; Comment: "Start mining in background"
Name: "{group}\RustChain Dashboard"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\rustchain.ico"; Comment: "Open the miner dashboard"
Name: "{group}\Stop Miner"; Filename: "{app}\stop_miner.bat"; IconFilename: "{app}\assets\rustchain.ico"; Comment: "Stop the miner"
Name: "{group}\View Logs"; Filename: "{app}\open_logs.bat"; IconFilename: "{app}\assets\rustchain.ico"; Comment: "Open log files"
Name: "{group}\Uninstall RustChain"; Filename: "{uninstallexe}"; Comment: "Remove RustChain from your computer"
Name: "{userdesktop}\RustChain Miner"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\rustchain.ico"; Tasks: desktopicon

; ============================================================
; Tasks (optional checkboxes during install)
; ============================================================
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "autostart"; Description: "Start RustChain when Windows starts"; GroupDescription: "Startup options:"

; ============================================================
; Registry — Auto-start on Windows boot (if selected)
; ============================================================
[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "RustChainMiner"; ValueData: """{app}\{#MyAppExeName}"" --minimized"; Flags: uninsdeletevalue; Tasks: autostart

; ============================================================
; Run after install — Launch option
; ============================================================
[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch RustChain Miner"; Flags: nowait postinstall skipifsilent

; ============================================================
; Uninstall — Clean up
; ============================================================
[UninstallRun]
Filename: "taskkill"; Parameters: "/IM {#MyAppExeName} /F"; Flags: runhidden; RunOnceId: "KillMiner"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
