#!/usr/bin/env python3
"""RustChain Wallet List — List all local wallets."""
import os, json, glob
DIRS = [os.path.expanduser("~/.clawrtc/wallets"), os.path.expanduser("~/.rustchain/wallets")]
def list_wallets():
    print("Local Wallets")
    found = 0
    for d in DIRS:
        for f in glob.glob(os.path.join(d, "*.json")):
            try:
                with open(f) as fh: w = json.load(fh)
                addr = w.get("address", w.get("public_key", "?")[:20])
                print(f"  {os.path.basename(f):<20} {addr}")
                found += 1
            except: pass
    if not found: print("  No wallets found")
if __name__ == "__main__":
    list_wallets()
