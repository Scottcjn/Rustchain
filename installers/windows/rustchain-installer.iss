; RustChain Windows Installer Script
; Requires Inno Setup 6.x: https://jrsoftware.org/isdl.php

#define MyAppName "RustChain Miner"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "RustChain"
#define MyAppURL "https://github.com/Scottcjn/Rustchain"
#define MyAppExeName "RustChainMiner.exe"

[Setup]
AppId={{8F9C3A2D-1B4E-4C5D-9A3F-7E6B2C1D8A4E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\RustChain
DefaultGroupName=RustChain
DisableProgramGroupPage=yes
LicenseFile=..\..\LICENSE
OutputDir=output
OutputBaseFilename=rustchain-miner-setup
SetupIconFile=assets\rustchain.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startminer"; Description: "Start miner after installation"; GroupDescription: "Startup Options:"; Flags: unchecked

[Files]
; Python embeddable package (download separately and place in build/)
Source: "build\python-3.11.9-embed-amd64.zip"; DestDir: "{app}\python"; Flags: ignoreversion
; Miner scripts
Source: "..\..\miners\windows\rustchain_windows_miner.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\miners\windows\windows_miner_simple.py"; DestDir: "{app}"; Flags: ignoreversion
; Launcher scripts
Source: "scripts\start-miner.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "scripts\stop-miner.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "scripts\view-logs.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "scripts\miner-service.ps1"; DestDir: "{app}"; Flags: ignoreversion
; Python dependencies
Source: "scripts\get-pip.py"; DestDir: "{app}"; Flags: ignoreversion
; Assets
Source: "assets\rustchain.ico"; DestDir: "{app}"; Flags: ignoreversion
; Documentation
Source: "README-Windows.md"; DestDir: "{app}"; Flags: ignoreversion isreadme

[Dirs]
Name: "{app}\logs"; Permissions: users-modify

[Icons]
Name: "{group}\RustChain Miner"; Filename: "{app}\start-miner.bat"; IconFilename: "{app}\rustchain.ico"
Name: "{group}\Stop Miner"; Filename: "{app}\stop-miner.bat"; IconFilename: "{app}\rustchain.ico"
Name: "{group}\View Logs"; Filename: "{app}\view-logs.bat"; IconFilename: "{app}\rustchain.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\RustChain Miner"; Filename: "{app}\start-miner.bat"; IconFilename: "{app}\rustchain.ico"; Tasks: desktopicon

[Run]
; Extract Python
Filename: "{cmd}"; Parameters: "/c tar -xf ""{app}\python\python-3.11.9-embed-amd64.zip"" -C ""{app}\python"""; StatusMsg: "Extracting Python..."; Flags: runhidden
; Install pip
Filename: "{app}\python\python.exe"; Parameters: """{app}\get-pip.py"""; StatusMsg: "Installing pip..."; Flags: runhidden waituntilterminated
; Install requests
Filename: "{app}\python\python.exe"; Parameters: "-m pip install requests --target ""{app}\python\Lib\site-packages"""; StatusMsg: "Installing dependencies..."; Flags: runhidden waituntilterminated
; Prompt for wallet name
Filename: "{app}\start-miner.bat"; Description: "Launch RustChain Miner"; Flags: postinstall nowait skipifsilent; Tasks: startminer

[UninstallRun]
Filename: "{app}\stop-miner.bat"; Flags: runhidden waituntilterminated

[Code]
var
  WalletNamePage: TInputQueryWizardPage;

procedure InitializeWizard;
begin
  WalletNamePage := CreateInputQueryPage(wpSelectDir,
    'Wallet Configuration', 'Enter your miner wallet name',
    'Please enter a unique name for your miner wallet (e.g., "my-desktop-miner"):');
  WalletNamePage.Add('Wallet name:', False);
  WalletNamePage.Values[0] := GetComputerNameString + '-miner';
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  ConfigFile: String;
  ConfigContent: TArrayOfString;
begin
  Result := True;
  
  if CurPageID = WalletNamePage.ID then
  begin
    if Trim(WalletNamePage.Values[0]) = '' then
    begin
      MsgBox('Please enter a wallet name.', mbError, MB_OK);
      Result := False;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigFile: String;
  ConfigContent: String;
begin
  if CurStep = ssPostInstall then
  begin
    { Save wallet name to config file }
    ConfigFile := ExpandConstant('{app}\wallet-config.txt');
    ConfigContent := WalletNamePage.Values[0];
    SaveStringToFile(ConfigFile, ConfigContent, False);
  end;
end;
