# RustChain Miner Windows Installer

This folder contains the build scripts and source code for the RustChain Miner Windows Installer.

## Deliverables

1.  **`RustChainMinerInstaller.exe`**: A single-file executable installer (built with PyInstaller).
    - Bundles a portable Python 3.10 environment.
    - Prompts for Wallet Name during installation.
    - Installs 'requests' in the isolated environment.
    - Sets up Start Menu shortcuts.
    - Sets up Auto-start on boot via Scheduled Tasks.
2.  **`rustchain_miner.iss`**: Inno Setup script for a professional installer (alternative to the Python-based one).
3.  **`bundle_installer.py`**: Source code for the Python-based installer wrapper.
4.  **`build_installer.ps1`**: PowerShell script to rebuild the installer.

## Features

- **Portability**: Uses an embeddable Python version (3.10) so the user doesn't need to install Python manually.
- **Persistence**: Automatically creates a Scheduled Task to run the miner on logon.
- **Shortcuts**: Creates "Start Miner", "Stop Miner", and "Logs" shortcuts in the Start Menu.
- **Size**: The final installer is approximately 15-20MB, well under the 50MB requirement.

## How to Build

If you need to rebuild the installer:

1.  Ensure Python 3.8+ is installed.
2.  Install PyInstaller: `pip install pyinstaller`.
3.  Run the build script:
    ```powershell
    .\build_installer.ps1
    ```
    The output `.exe` will be in the `dist` folder.

## Manual Installation Logic (Inno Setup)

If you prefer using Inno Setup:
1.  Install [Inno Setup 6](https://jrsoftware.org/isdl.php).
2.  Open `rustchain_miner.iss`.
3.  Click "Compile".
4.  The installer will be generated in the `Output` folder.

## Repository Files Included

- `rustchain_miner.py`: The local x86 miner script.
- `fingerprint_checks.py`: RIP-PoA hardware fingerprinting.
- `python-3.10.11-embed-amd64.zip`: Bundled Python environment.
- `get-pip.py`: For installing dependencies in the portable environment.
