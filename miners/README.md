# RustChain Miners

## Directory Structure
- `linux/` - Linux miner with auto-detection for all architectures
- `macos/` - macOS miners for Apple Silicon and Intel
- `windows/` - Windows miners
- `ppc/` - PowerPC miners for G4/G5 Macs (legacy hardware bonus)

## Supported Architectures
The Linux miner auto-detects your hardware via `platform.machine()` and reports honestly:

| Architecture | `platform.machine()` | Multiplier Range | Examples |
|---|---|---|---|
| x86_64 | `x86_64` | 0.8-2.5x | Intel/AMD, vintage Pentium to modern Zen |
| PowerPC | `ppc`, `ppc64`, `ppc64le` | 1.5-2.5x | G3, G4, G5, POWER8, POWER9 |
| SPARC | `sparc`, `sparc64`, `sun4u` | 1.8-2.9x | SPARCstation, UltraSPARC |
| MIPS | `mips`, `mips64` | 2.3-3.0x | SGI workstations, Loongson |
| Motorola 68K | `m68k` | 2.2-3.0x | Amiga, Atari ST, classic Mac |
| SuperH | `sh4` | 2.3-2.7x | Dreamcast (SH-4), Saturn (SH-2) |
| RISC-V | `riscv64`, `riscv32` | 1.4-1.5x | SiFive, StarFive boards |
| Itanium | `ia64` | 2.5x | IA-64 servers |
| IBM S/390 | `s390`, `s390x` | 2.5x | Mainframes |
| ARM (vintage) | `arm` | 2.0-4.0x | ARM2, StrongARM, XScale |
| ARM (modern) | `aarch64`, `armv7l` | 0.0005x | NAS boxes, SBCs, phones |
| Apple Silicon | via brand detection | 1.05-1.2x | M1, M2, M3, M4 |

**Ultra-rare CPUs** (VAX, Transputer, Clipper, i860) get 3.0-3.5x via claimed arch — if you have one running, you've earned it.

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
python rustchain_windows_miner.py --headless --wallet YOUR_WALLET_ID --node https://rustchain.org
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
