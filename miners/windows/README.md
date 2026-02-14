# RustChain Miner (Windows)

This directory contains the Windows miner and a buildable installer.

## Contents

- `rustchain_windows_miner.py`: legacy Windows GUI miner (run from source).
- `fingerprint_checks.py`: hardware fingerprint helpers used by miners.
- `installer/`: packaged build pipeline for a Windows `.exe` plus an Inno Setup installer.
  - `installer/src/rustchain_windows_miner.py`: packaged miner (GUI + PoA loop).
  - `installer/build_miner.py` and `installer/RustChainMiner.spec`: PyInstaller build.
  - `installer/rustchain_setup.iss`: Inno Setup script (produces `RustChainSetup_vX.Y.Z.exe`).
  - `installer/scripts/*.bat`: Start/Stop/Open Logs helpers.

## Build (Windows)

Follow `installer/README.md`.
