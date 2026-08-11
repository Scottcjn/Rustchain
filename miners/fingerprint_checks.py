#!/usr/bin/env python3
"""
RIP-PoA Hardware Fingerprint Validation — Platform Auto-Detect Wrapper
======================================================================

Auto-detects the current OS and delegates to the correct platform-specific
implementation (linux/, windows/, macos/).  This allows running

    python3 miners/fingerprint_checks.py

from the repository root on any supported platform.

The platform-specific files are byte-for-byte identical; the subdirectory
layout exists for discoverability and to keep each platform miner
self-contained (each miner lives in its own directory with its own
fingerprint_checks.py, requirements, etc.).
"""

import importlib.util
import os
import platform
import sys

# ── Determine the platform-specific module path ────────────────────────────

_platform = platform.system().lower()
_script_dir = os.path.dirname(os.path.abspath(__file__))

if _platform == "linux":
    _subdir = "linux"
elif _platform == "windows":
    _subdir = "windows"
elif _platform == "darwin":
    _subdir = "macos"
else:
    # Fallback: try linux first (most generic), then windows
    for _candidate in ("linux", "windows"):
        _path = os.path.join(_script_dir, _candidate, "fingerprint_checks.py")
        if os.path.exists(_path):
            _subdir = _candidate
            break
    else:
        raise ImportError(
            f"Unsupported platform {_platform!r} and no platform-specific "
            f"fingerprint_checks module found under miners/"
        )

_fp_path = os.path.join(_script_dir, _subdir, "fingerprint_checks.py")

# ── Load the platform-specific module ──────────────────────────────────────

_spec = importlib.util.spec_from_file_location(
    f"fingerprint_checks_{_subdir}", _fp_path
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# ── Re-export every public name ────────────────────────────────────────────
# This makes "from fingerprint_checks import validate_all_checks" work
# regardless of whether the import resolved through the wrapper or directly.

for _attr in dir(_mod):
    if not _attr.startswith("_"):
        globals()[_attr] = getattr(_mod, _attr)

# ── Allow running directly ─────────────────────────────────────────────────

if __name__ == "__main__":
    passed, results = validate_all_checks()
    print("\n\nDetailed Results:")
    import json
    print(json.dumps(results, indent=2, default=str))
    sys.exit(0 if passed else 1)