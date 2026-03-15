#!/usr/bin/env python3
"""RustChain Disk Usage Monitor — Track database and log growth."""
import os, json, sys

PATHS = {
    "Database": os.path.expanduser("~/.rustchain/data"),
    "Logs": os.path.expanduser("~/.rustchain/logs"),
    "Wallets": os.path.expanduser("~/.clawrtc/wallets"),
    "Cache": os.path.expanduser("~/.rustchain/api-cache"),
}

def get_size(path):
    total = 0
    if os.path.isfile(path): return os.path.getsize(path)
    if not os.path.exists(path): return 0
    for root, dirs, files in os.walk(path):
        for f in files:
            try: total += os.path.getsize(os.path.join(root, f))
            except: pass
    return total

def human(b):
    for u in ['B','KB','MB','GB']:
        if b < 1024: return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} TB"

def main():
    print("RustChain Disk Usage")
    print("=" * 40)
    total = 0
    for name, path in PATHS.items():
        size = get_size(path)
        total += size
        exists = "OK" if os.path.exists(path) else "N/A"
        print(f"  {name:<12} {human(size):>10}  {exists}")
    print(f"  {'TOTAL':<12} {human(total):>10}")
    
    import shutil
    disk = shutil.disk_usage("/")
    pct = disk.used / disk.total * 100
    print(f"\n  Disk: {human(disk.used)}/{human(disk.total)} ({pct:.0f}%)")
    if pct > 90:
        print("  WARNING: Disk usage above 90%!")

if __name__ == "__main__":
    main()
