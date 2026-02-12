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

## What the Installer Does

1. **Wallet Name** — Asks during setup, saves to `%APPDATA%\RustChain\config.json`
2. **Shortcuts** — Start Menu: Start / Dashboard / Stop / Logs / Uninstall
3. **Desktop Icon** — Optional
4. **Auto-Start** — Optional: adds to `HKCU\...\Run` registry key
5. **Tray Icon** — Right-click for Start/Stop/Show/Logs/Exit
6. **Logging** — Writes to `%APPDATA%\RustChain\logs\`
7. **No Admin Required** — Installs to `%LOCALAPPDATA%\RustChain`

## Notes

- **SSL:** All connections use `verify=False` (self-signed cert on node `50.28.86.131`)
- **Icon:** Place your `.ico` file at `assets/rustchain.ico` before building
- **Size Target:** < 50 MB for the final `.exe`
