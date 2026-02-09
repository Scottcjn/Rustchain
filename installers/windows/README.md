# RustChain Windows Installer Source

This repository contains the source code for the RustChain Proof-of-Antiquity Miner Windows Installer (.exe).

## Features
- **Bundled Python**: Uses PyInstaller to bundle the miner with its own Python environment.
- **System Tray Icon**: Provides a persistent tray icon for status monitoring (Gray=Stopped, Green=Mining, Red=Error) and control.
- **Custom Installer**: NSIS script that prompts for a wallet name, sets up Start Menu shortcuts, and configures auto-start.
- **Non-Admin Install**: Installs to the user's profile directory by default.

## Contents
- `src/tray_app.py`: Python script for the system tray application.
- `src/installer.nsi`: NSIS script for creating the installer executable.
- `build_windows.py`: Helper script to download the latest miner components and build the binary.

## Build Instructions (on Windows)

### 1. Prerequisites
- Python 3.8+
- [NSIS](https://nsis.sourceforge.io/Download) installed and added to PATH.

### 2. Setup Environment
```bash
pip install pyinstaller pystray Pillow requests
```

### 3. Prepare Miner Files
Run the build script to fetch the latest Windows-specific miner scripts:
```bash
python build_windows.py
```

### 4. Build Tray App
Compile the Python tray app into a standalone executable:
```bash
pyinstaller --onefile --noconsole --add-data "rustchain_miner.py;." --add-data "fingerprint_checks.py;." src/tray_app.py
```
This will create `dist/tray_app.exe`.

### 5. Create Installer
Copy `dist/tray_app.exe` to the `src` directory (or update the `.nsi` path) and run:
```bash
makensis src/installer.nsi
```
The final `RustChainMinerInstaller.exe` will be created in the root directory.

## Testing
1. Run `RustChainMinerInstaller.exe`.
2. Follow the prompts to set your wallet name.
3. Verify the miner appears in the system tray and starts mining.
4. Check the logs at `%USERPROFILE%\.rustchain\miner.log`.
