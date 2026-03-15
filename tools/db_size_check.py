#!/usr/bin/env python3
"""RustChain Database Size Checker."""
import os, glob
PATHS = {"Main DB": "~/.rustchain/data/*.db", "Bridge DB": "~/.rustchain/data/bridge*.db",
         "Uptime DB": "~/.rustchain/uptime.db", "Price DB": "~/.rustchain/price_history.db",
         "Epoch DB": "~/.rustchain/epoch_analytics.db", "Fee DB": "~/.rustchain/fee_history.db"}
def check():
    print("Database Sizes")
    total = 0
    for name, pattern in PATHS.items():
        path = os.path.expanduser(pattern)
        files = glob.glob(path)
        size = sum(os.path.getsize(f) for f in files if os.path.exists(f))
        total += size
        if size > 0:
            print(f"  {name:<15} {size/1024/1024:.1f} MB ({len(files)} files)")
    print(f"  {'TOTAL':<15} {total/1024/1024:.1f} MB")
if __name__ == "__main__":
    check()
