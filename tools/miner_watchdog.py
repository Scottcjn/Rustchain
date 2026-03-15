#!/usr/bin/env python3
"""RustChain Miner Watchdog — Ensure miner process stays running."""
import subprocess, time, os, sys
MINER_CMD = os.environ.get("MINER_CMD", "clawrtc start")
CHECK_INTERVAL = int(os.environ.get("WATCHDOG_INTERVAL", "60"))
def is_mining():
    try:
        result = subprocess.run(["clawrtc", "status"], capture_output=True, text=True, timeout=10)
        return "running" in result.stdout.lower() or "mining" in result.stdout.lower()
    except: return False
def watchdog():
    restarts = 0
    print(f"Watchdog active. Checking every {CHECK_INTERVAL}s")
    while True:
        if not is_mining():
            restarts += 1
            print(f"[{time.strftime('%H:%M:%S')}] Miner not running! Restart #{restarts}")
            subprocess.Popen(MINER_CMD, shell=True)
            time.sleep(30)
        time.sleep(CHECK_INTERVAL)
if __name__ == "__main__":
    try: watchdog()
    except KeyboardInterrupt: print("\nWatchdog stopped")
