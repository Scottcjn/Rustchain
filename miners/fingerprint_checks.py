#!/usr/bin/env python3
"""
Platform-aware fingerprint checks wrapper.

Automatically detects the current platform and delegates to the
platform-specific fingerprint_checks module (miners/<platform>/).

Usage:
    python3 miners/fingerprint_checks.py
"""

import importlib.util
import os
import platform
import sys

_script_dir = os.path.dirname(os.path.abspath(__file__))
_platform = platform.system().lower()

_subdir = {"linux": "linux", "windows": "windows", "darwin": "macos"}.get(_platform, "linux")
_fp_path = os.path.join(_script_dir, _subdir, "fingerprint_checks.py")

if not os.path.exists(_fp_path):
    print(f"Error: no fingerprint_checks.py found for platform '{_platform}'", file=sys.stderr)
    print(f"Expected at: {_fp_path}", file=sys.stderr)
    sys.exit(1)

_spec = importlib.util.spec_from_file_location(f"fingerprint_checks_{_subdir}", _fp_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# Re-export all public symbols for backward compatibility
for _attr in dir(_mod):
    if not _attr.startswith("_"):
        globals()[_attr] = getattr(_mod, _attr)

if __name__ == "__main__":
    # If the module has a main-like entry point, run it
    if hasattr(_mod, "main"):
        _mod.main()
    else:
        print(f"fingerprint_checks ({_platform}) loaded successfully.")
        print(f"Available functions: {[a for a in dir(_mod) if not a.startswith('_')]}")