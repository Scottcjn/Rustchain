#!/usr/bin/env python3
"""RustChain Crash Reporter — Capture and report node crashes."""
import json, os, sys, traceback, time, urllib.request, platform
from datetime import datetime

REPORT_URL = os.environ.get("CRASH_REPORT_URL", "")
LOG_DIR = os.path.expanduser("~/.rustchain/crash-reports")

def capture_crash(exc_type, exc_value, exc_tb):
    os.makedirs(LOG_DIR, exist_ok=True)
    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "error": str(exc_value),
        "type": exc_type.__name__,
        "traceback": traceback.format_exception(exc_type, exc_value, exc_tb),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "node_version": os.environ.get("RUSTCHAIN_VERSION", "unknown"),
    }
    fname = f"crash_{int(time.time())}.json"
    with open(os.path.join(LOG_DIR, fname), "w") as f:
        json.dump(report, f, indent=2)
    print(f"Crash report saved: {LOG_DIR}/{fname}", file=sys.stderr)
    if REPORT_URL:
        try:
            req = urllib.request.Request(REPORT_URL, json.dumps(report).encode(), {"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5)
        except: pass

def install():
    sys.excepthook = capture_crash
    print("Crash reporter installed")

if __name__ == "__main__":
    install()
    print("Test crash in 2 seconds...")
    time.sleep(2)
    raise RuntimeError("Test crash — this is intentional")
