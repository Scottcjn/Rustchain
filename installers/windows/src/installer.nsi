!define APPNAME "RustChain Miner"
!define COMPANYNAME "Scottcjn"
!define DESCRIPTION "Proof-of-Antiquity Miner for RustChain"
!define VERSIONMAJOR 3
!define VERSIONMINOR 2
!define VERSIONBUILD 0

!include "MUI2.nsh"
!include "nsDialogs.nsh"

Name "${APPNAME}"
OutFile "RustChainMinerInstaller.exe"
InstallDir "$PROFILE\.rustchain"
RequestExecutionLevel user

Var Dialog
Var Label
Var WalletNameInput
Var WalletName

!define MUI_ABORTWARNING

!insertmacro MUI_PAGE_WELCOME
Page custom WalletPageShow WalletPageLeave
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_LANGUAGE "English"

Function WalletPageShow
    nsDialogs::Create 1018
    Pop $Dialog

    ${If} $Dialog == error
        Abort
    ${EndIf}

    ${NSD_CreateLabel} 0 0 100% 12u "Enter your RustChain wallet name:"
    Pop $Label

    ${NSD_CreateText} 0 13u 100% 12u "my-desktop-miner"
    Pop $WalletNameInput

    nsDialogs::Show
FunctionEnd

Function WalletPageLeave
    ${NSD_GetText} $WalletNameInput $WalletName
    ${If} $WalletName == ""
        MessageBox MB_OK "Please enter a wallet name."
        Abort
    ${EndIf}
FunctionEnd

Section "Install"
    SetOutPath "$INSTDIR"
    
    # Save wallet name to file
    FileOpen $0 "$INSTDIR\wallet.txt" w
    FileWrite $0 $WalletName
    FileClose $0

    # These files are expected to be in the same directory as the .nsi during build
    File "tray_app.exe"
    File "rustchain_miner.py"
    File "fingerprint_checks.py"

    # Create shortcuts
    CreateDirectory "$SMPROGRAMS\${APPNAME}"
    CreateShortcut "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk" "$INSTDIR\tray_app.exe"
    CreateShortcut "$SMPROGRAMS\${APPNAME}\Uninstall ${APPNAME}.lnk" "$INSTDIR\uninstall.exe"
    
    # Add to startup
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "${APPNAME}" '"$INSTDIR\tray_app.exe"'
    
    WriteUninstaller "$INSTDIR\uninstall.exe"
    
    # Launch app after install
    Exec '"$INSTDIR\tray_app.exe"'
SectionEnd

Section "Uninstall"
    # Stop processes
    nsExec::Exec 'taskkill /F /IM tray_app.exe'
    
    DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "${APPNAME}"
    
    RMDir /r "$SMPROGRAMS\${APPNAME}"
    RMDir /r "$INSTDIR"
SectionEnd
