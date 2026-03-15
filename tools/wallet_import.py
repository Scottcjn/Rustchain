#!/usr/bin/env python3
"""RustChain Wallet Import."""
import json, os, sys, hashlib
DIR = os.path.expanduser("~/.clawrtc/wallets")
def import_file(path):
    with open(path) as f: data = json.load(f)
    os.makedirs(DIR, exist_ok=True)
    dest = os.path.join(DIR, os.path.basename(path))
    with open(dest, "w") as f: json.dump(data, f, indent=2)
    print(f"Imported to {dest}")
if __name__ == "__main__":
    if len(sys.argv) < 2: print("Usage: python wallet_import.py <file.json>")
    else: import_file(sys.argv[1])
