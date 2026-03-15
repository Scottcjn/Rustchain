#!/usr/bin/env python3
"""RustChain Environment Checker — Verify system requirements for mining."""
import platform, shutil, sys, os, subprocess

REQUIREMENTS = {
    "Python": ("3.8", platform.python_version()),
    "OS": ("any", platform.system()),
    "Architecture": ("any", platform.machine()),
    "Git": ("any", shutil.which("git")),
    "Pip": ("any", shutil.which("pip") or shutil.which("pip3")),
    "Curl": ("any", shutil.which("curl")),
}

def check():
    print("RustChain Environment Check")
    print("=" * 45)
    all_ok = True
    for name, (req, val) in REQUIREMENTS.items():
        ok = val is not None and val != ""
        print(f"  {'OK' if ok else 'FAIL':>4}  {name:<15} {val or 'NOT FOUND'}")
        if not ok: all_ok = False
    
    # Check disk space
    disk = shutil.disk_usage("/")
    free_gb = disk.free / (1024**3)
    ok = free_gb > 5
    print(f"  {'OK' if ok else 'WARN':>4}  {'Disk Free':<15} {free_gb:.1f} GB")
    
    # Check internet
    try:
        import urllib.request
        urllib.request.urlopen("https://rustchain.org/health", timeout=5)
        print(f"  {'OK':>4}  {'Internet':<15} Connected")
    except:
        print(f"  {'FAIL':>4}  {'Internet':<15} No connection")
        all_ok = False
    
    print(f"\n{'Ready to mine!' if all_ok else 'Fix issues above before mining.'}")

if __name__ == "__main__":
    check()
