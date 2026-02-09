; RustChain Miner Windows Installer Script (Inno Setup)
; Requirements: Inno Setup 6+

[Setup]
AppName=RustChain Miner
AppVersion=1.1.0
AppPublisher=Scottcjn / Elyan Labs
AppPublisherURL=https://rustchain.org
DefaultDirName={localappdata}\RustChainMiner
DefaultGroupName=RustChain Miner
OutputDir=.
OutputBaseFilename=RustChainMinerInstaller
Compression=lzma
SolidCompression=yes
WizardStyle=modern
DisableWelcomePage=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Miner scripts
Source: "rustchain_miner.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "fingerprint_checks.py"; DestDir: "{app}"; Flags: ignoreversion
; We can bundle a portable python zip or download it during install.
; For a single EXE under 50MB, bundling is better if it fits.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "autostart"; Description: "Start miner automatically on Windows login"; GroupDescription: "Persistence:"; Flags: checked

[Icons]
Name: "{group}\Start RustChain Miner"; Filename: "{app}\venv\Scripts\pythonw.exe"; Parameters: "{app}\rustchain_miner.py --wallet {code:GetWalletName}"; IconFilename: "{app}\rustchain_miner.py"
Name: "{group}\Stop RustChain Miner"; Filename: "taskkill"; Parameters: "/F /IM python.exe /FI ""WINDOWTITLE eq RustChain Miner*"""; Flags: runminimized
Name: "{group}\View Logs"; Filename: "{app}"; 
Name: "{group}\{cm:UninstallProgram,RustChain Miner}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\RustChain Miner"; Filename: "{app}\venv\Scripts\pythonw.exe"; Parameters: "{app}\rustchain_miner.py --wallet {code:GetWalletName}"; Tasks: desktopicon

[Run]
; Install Python venv
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -Command ""python -m venv '{app}\venv'"""; StatusMsg: "Creating virtual environment..."; Flags: runhidden
; Install dependencies
Filename: "{app}\venv\Scripts\pip.exe"; Parameters: "install requests"; StatusMsg: "Installing dependencies (requests)..."; Flags: runhidden
; Setup Scheduled Task if auto-start is selected
Filename: "schtasks"; Parameters: "/Create /F /SC ONLOGON /TN ""RustChainMiner"" /TR ""'{app}\venv\Scripts\pythonw.exe' '{app}\rustchain_miner.py' --wallet {code:GetWalletName}"""; Tasks: autostart; StatusMsg: "Setting up auto-start task..."; Flags: runhidden

[UninstallRun]
Filename: "schtasks"; Parameters: "/Delete /TN ""RustChainMiner"" /F"; Flags: runhidden

[Code]
var
  WalletPage: TInputQueryWizardPage;

procedure InitializeWizard;
begin
  // Create a custom page to ask for Wallet Name
  WalletPage := CreateInputQueryPage(wpSelectDir,
    'Wallet Configuration', 'What is your wallet name?',
    'Please enter the wallet name you want to use for mining rewards.');
  WalletPage.Add('Wallet Name:', False);
  
  // Set default value based on computer name
  WalletPage.Values[0] := 'miner-' + GetComputerNameString;
end;

function GetWalletName(Param: String): String;
begin
  Result := WalletPage.Values[0];
  if Result = '' then
    Result := 'anonymous-miner';
end;

function GetComputerNameString: String;
begin
  Result := GetEnv('COMPUTERNAME');
end;
