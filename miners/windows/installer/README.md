# RustChain Miner — Build & Install Guide

## Quick Start

### 1. Install Dependencies
```cmd
cd miners\windows\installer
pip install -r requirements.txt
```

### 2. Build the .exe
```cmd
python build_miner.py
```
→ Produces `dist\RustChainMiner.exe`

### 3. Build the Installer (requires Inno Setup 6)
```cmd
iscc rustchain_setup.iss
```
→ Produces `output\RustChainSetup_v1.0.0.exe`

---

## Project Structure

```
rustchain-installer/
├── src/
│   ├── rustchain_windows_miner.py   ← Main miner (GUI + engine)
│   ├── config_manager.py            ← Config bridge (installer ↔ miner)
│   └── tray_icon.py                 ← System tray icon (pystray)
├── scripts/
│   ├── start_miner.bat              ← Start miner (minimized)
│   ├── stop_miner.bat               ← Stop miner process
│   └── open_logs.bat                ← Open log directory
├── assets/
│   └── rustchain.ico                ← App icon (user-provided)
├── build_miner.py                   ← PyInstaller build script
├── rustchain_setup.iss              ← Inno Setup installer script
├── requirements.txt                 ← Python dependencies
└── README.md                        ← This file
```

## Expected Runtime Behavior

- **Config Storage:** Settings (wallet name, node URL) are stored in `%APPDATA%\RustChain\config.json`.
- **Logs:** Miner logs and error reports are saved in `%APPDATA%\RustChain\logs\`.
- **Auto-Start:** If enabled, a shortcut is added to the Windows Registry (`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`) to launch the miner on login.
- **Tray Icon:** The miner runs in the background. Right-click the RustChain icon in the system tray to Start/Stop the engine, open the Dashboard, or View Logs.
- **Uninstallation:** Can be removed cleanly via the "Uninstall RustChain Miner" shortcut in the Start Menu or through Windows "Add or Remove Programs". This removes the executable, registry keys, and shortcuts.

---

## 🛠️ Operator Runbook

### Start / Stop
- **Method A:** Use the **Start Menu** shortcuts.
- **Method B:** Right-click the **System Tray icon** and select "Start Engine" or "Stop Engine".
- **Method C:** Use the provided `.bat` scripts in the install directory.

### Updating the Miner
1. Download the latest `RustChainSetup.exe`.
2. Run the installer. It will overwrite the existing executable while preserving your `config.json` (wallet name).
3. Restart the miner from the Start Menu.

### Failure Recovery
1. **Miner won't start:** Check `%APPDATA%\RustChain\logs\miner.log` for error messages.
2. **"Node unreachable":** Verify your internet connection and ensure `node_url` in `config.json` is set to `https://rustchain.org`.
3. **Hardware Fingerprint Failed:** Ensure you are running on real hardware. Virtual machines and emulators are restricted.

---

## Technical Notes

- **Network:** Default node is `https://rustchain.org`.
- **Security:** Keep TLS verification enabled for the default `https://rustchain.org` node; only use a custom CA or explicit local override for private test nodes.
- **Builds:** Automated Windows builds are handled via GitHub Actions (see `.github/workflows/windows-build.yml`).

