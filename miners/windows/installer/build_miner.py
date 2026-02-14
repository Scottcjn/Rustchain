#!/usr/bin/env python3
"""
RustChain Miner — PyInstaller Build Script
Produces a single .exe with all dependencies bundled.

Usage:
    python build_miner.py

Output:
    dist/RustChainMiner.exe
"""

import subprocess
import sys
import os
from pathlib import Path

# Paths
PROJECT_DIR = Path(__file__).parent
SRC_DIR = PROJECT_DIR / "src"
ENTRY_POINT = SRC_DIR / "rustchain_windows_miner.py"
ICON_FILE = PROJECT_DIR / "assets" / "rustchain.ico"
DIST_DIR = PROJECT_DIR / "dist"


def build():
    print("=" * 60)
    print("  RustChain Miner — PyInstaller Build")
    print("=" * 60)

    if not ENTRY_POINT.exists():
        print(f"ERROR: Entry point not found: {ENTRY_POINT}")
        sys.exit(1)

    # Base PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",                          # Single .exe
        "--windowed",                         # No console window
        "--name", "RustChainMiner",           # Output name
        "--distpath", str(DIST_DIR),          # Output directory
        "--workpath", str(PROJECT_DIR / "build"),
        "--specpath", str(PROJECT_DIR),
        "--clean",                            # Clean cache

        # Exclude heavy modules often found in Anaconda
        "--exclude-module", "numpy",
        "--exclude-module", "matplotlib",
        "--exclude-module", "pandas",
        "--exclude-module", "scipy",
        "--exclude-module", "cryptography",
        "--exclude-module", "tcl",
        "--exclude-module", "tk",

        # Hidden imports (modules not detected by static analysis)
        "--hidden-import", "requests",
        "--hidden-import", "urllib3",
        "--hidden-import", "pystray",
        "--hidden-import", "PIL",
        "--hidden-import", "PIL.Image",
        "--hidden-import", "PIL.ImageDraw",
        "--hidden-import", "PIL.ImageFont",
        "--hidden-import", "pystray._win32",
        "--hidden-import", "config_manager",
        "--hidden-import", "tray_icon",

        # Add the src directory to the Python path
        "--paths", str(SRC_DIR),

        # Add additional data files
        "--add-data", f"{SRC_DIR / 'config_manager.py'};.",
        "--add-data", f"{SRC_DIR / 'tray_icon.py'};.",
    ]

    # Add icon if it exists
    if ICON_FILE.exists():
        cmd.extend(["--icon", str(ICON_FILE)])
        cmd.extend(["--add-data", f"{ICON_FILE};assets"])
        print(f"  Icon: {ICON_FILE}")
    else:
        print(f"  Icon: Not found (skipping) — place rustchain.ico in assets/")

    # Entry point
    cmd.append(str(ENTRY_POINT))

    print(f"  Entry: {ENTRY_POINT}")
    print(f"  Output: {DIST_DIR / 'RustChainMiner.exe'}")
    print("-" * 60)

    # Run PyInstaller
    result = subprocess.run(cmd, cwd=str(PROJECT_DIR))

    if result.returncode == 0:
        exe_path = DIST_DIR / "RustChainMiner.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print("-" * 60)
            print(f"  BUILD SUCCESSFUL!")
            print(f"  Output: {exe_path}")
            print(f"  Size:   {size_mb:.1f} MB")
            if size_mb > 50:
                print(f"  WARNING: Exceeds 50 MB target!")
            print("=" * 60)
        else:
            print("  ERROR: Build completed but .exe not found!")
            sys.exit(1)
    else:
        print("  ERROR: PyInstaller build failed!")
        sys.exit(1)


if __name__ == "__main__":
    build()
