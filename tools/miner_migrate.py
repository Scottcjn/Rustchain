#!/usr/bin/env python3
"""RustChain Miner Migration Assistant — Move wallet and config to a new machine."""
import json, os, shutil, tarfile, sys
from datetime import datetime

RUSTCHAIN_HOME = os.path.expanduser("~/.rustchain")
CLAWRTC_HOME = os.path.expanduser("~/.clawrtc")

def export_bundle(output=None):
    output = output or f"rustchain_migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.tar.gz"
    files = []
    for d in [RUSTCHAIN_HOME, CLAWRTC_HOME]:
        if os.path.exists(d):
            for root, _, fnames in os.walk(d):
                for f in fnames:
                    if f.endswith(('.json', '.key', '.pem', '.yaml', '.yml', '.env', '.cfg')):
                        files.append(os.path.join(root, f))
    
    with tarfile.open(output, "w:gz") as tar:
        for f in files:
            tar.add(f)
    print(f"Migration bundle: {output} ({len(files)} files)")
    print("Transfer to new machine and run: python miner_migrate.py import <file>")

def import_bundle(archive):
    print(f"Importing from {archive}...")
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall("/")
    print("Migration complete! Restart your miner.")

if __name__ == "__main__":
    if len(sys.argv) < 2: print("Usage: python miner_migrate.py export|import [file]")
    elif sys.argv[1] == "export": export_bundle(sys.argv[2] if len(sys.argv) > 2 else None)
    elif sys.argv[1] == "import": import_bundle(sys.argv[2])
