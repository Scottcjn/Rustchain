#!/usr/bin/env python3
"""RustChain Version Checker — Compare running vs latest version."""
import json, urllib.request, ssl, os

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")

def main():
    # Get running version
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try:
        h = json.loads(urllib.request.urlopen(f"{NODE}/health", timeout=10, context=ctx).read())
        running = h.get("version", "?")
    except: running = "unreachable"
    
    # Get latest from GitHub
    try:
        r = urllib.request.urlopen("https://api.github.com/repos/Scottcjn/Rustchain/commits/main", timeout=10)
        latest = json.loads(r.read())
        latest_sha = latest.get("sha", "?")[:7]
        latest_msg = latest.get("commit", {}).get("message", "?").split("\n")[0][:60]
        latest_date = latest.get("commit", {}).get("committer", {}).get("date", "?")[:10]
    except: latest_sha = "?"; latest_msg = "?"; latest_date = "?"
    
    print(f"RustChain Version Check")
    print(f"  Running:  {running}")
    print(f"  Latest:   {latest_sha} ({latest_date})")
    print(f"  Commit:   {latest_msg}")
    print(f"  Status:   {'UP TO DATE' if running in latest_sha else 'UPDATE AVAILABLE'}")

if __name__ == "__main__":
    main()
