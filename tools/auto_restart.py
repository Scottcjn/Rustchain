#!/usr/bin/env python3
"""RustChain Auto-Restart — Monitor node health and restart on failure."""
import urllib.request, ssl, os, time, subprocess, json

NODE = os.environ.get("RUSTCHAIN_NODE", "http://localhost:8088")
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "60"))
MAX_FAILURES = int(os.environ.get("MAX_FAILURES", "3"))
RESTART_CMD = os.environ.get("RESTART_CMD", "sudo systemctl restart rustchain-node")

def is_healthy():
    try:
        ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        r = urllib.request.urlopen(f"{NODE}/health", timeout=10, context=ctx)
        data = json.loads(r.read())
        return data.get("status") == "ok"
    except: return False

def main():
    failures = 0
    print(f"Auto-restart monitor: checking {NODE} every {CHECK_INTERVAL}s")
    while True:
        if is_healthy():
            if failures > 0:
                print(f"[{time.strftime('%H:%M:%S')}] Node recovered after {failures} failures")
            failures = 0
        else:
            failures += 1
            print(f"[{time.strftime('%H:%M:%S')}] Health check failed ({failures}/{MAX_FAILURES})")
            if failures >= MAX_FAILURES:
                print(f"[{time.strftime('%H:%M:%S')}] Restarting node...")
                subprocess.run(RESTART_CMD, shell=True)
                failures = 0
                time.sleep(30)
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: print("\nStopped")
