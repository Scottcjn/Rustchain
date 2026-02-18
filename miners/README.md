# RustChain Miners

## Directory Structure
- `linux/` - Linux x86_64 miners with fingerprint attestation
- `macos/` - macOS miners for Apple Silicon and Intel
- `windows/` - Windows miners
- `ppc/` - PowerPC miners for G4/G5 Macs (legacy hardware bonus)

## Version 2.4.0 Features
- Hardware serial binding (v2)
- 6-point fingerprint attestation
- Anti-emulation checks
- Auto-recovery via systemd/launchd

## Quick Start
```bash
# Linux
python3 rustchain_linux_miner.py

# macOS
python3 rustchain_mac_miner_v2.4.py

# Windows
python rustchain_windows_miner.py

# If your Python does not include Tcl/Tk (common on minimal/embeddable installs):
python rustchain_windows_miner.py --headless --wallet YOUR_WALLET_ID --node https://50.28.86.131
```

## Windows installer & build helpers
- Run `rustchain_miner_setup.bat` (living alongside `rustchain_windows_miner.py`) on a new Windows host to:
  1. Detect or download/install Python 3.11 (MSI) and ensure `pip` is on the path.
  2. Install the runtime requirements from `requirements-miner.txt`.
  3. Fetch the latest `rustchain_windows_miner.py` from the repository if it is not present.
  4. Print the command to launch the miner so you can create shortcuts or scheduled tasks.
- To produce a standalone binary, run `build_windows_miner.ps1` on Windows:
  1. It upgrades `pip`, installs `pyinstaller`, and removes the old `dist` folder.
  2. It calls `pyinstaller --onefile --name rustchain_windows_miner rustchain_windows_miner.py`.
  3. The resulting `dist\\rustchain_windows_miner.exe` can be bundled with the batch installer for distribution.
- If you only have Wine on this machine, run `build_windows_miner_wine.sh`; it downloads the Python embeddable ZIP, bootstraps pip, installs PyInstaller, and produces `dist/rustchain_windows_miner.exe`.
- When `dist/rustchain_windows_miner.exe` exists, execute `package_windows_miner_release.sh` to collect the EXE, installer batch, requirements list, and release README into `release/rustchain_windows_miner_release.zip`. Upload that ZIP or attach it to a GitHub release so Windows users can grab the ready-to-run bundle.
