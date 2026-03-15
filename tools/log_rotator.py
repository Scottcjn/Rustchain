#!/usr/bin/env python3
"""RustChain Log Rotator — Compress and rotate old log files."""
import os, gzip, shutil, glob, time
LOG_DIR = os.path.expanduser("~/.rustchain/logs")
MAX_AGE_DAYS = int(os.environ.get("LOG_MAX_AGE", "7"))
def rotate():
    if not os.path.exists(LOG_DIR): print("No logs directory"); return
    now = time.time()
    rotated = deleted = 0
    for f in glob.glob(os.path.join(LOG_DIR, "*.log")):
        age = (now - os.path.getmtime(f)) / 86400
        if age > MAX_AGE_DAYS:
            with open(f, "rb") as src, gzip.open(f + ".gz", "wb") as dst:
                shutil.copyfileobj(src, dst)
            os.remove(f)
            rotated += 1
    for f in glob.glob(os.path.join(LOG_DIR, "*.gz")):
        age = (now - os.path.getmtime(f)) / 86400
        if age > MAX_AGE_DAYS * 4:
            os.remove(f)
            deleted += 1
    print(f"Rotated: {rotated} | Deleted: {deleted}")
if __name__ == "__main__":
    rotate()
