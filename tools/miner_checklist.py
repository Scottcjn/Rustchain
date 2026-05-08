#!/usr/bin/env python3
"""RustChain Miner Pre-Flight Checklist."""
import os, shutil, urllib.request, ssl, json
def check(name, condition):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}")
    return condition
def preflight():
    print("Miner Pre-Flight Checklist")
    ok = True
    ok &= check("Python 3.8+", __import__("sys").version_info >= (3, 8))
    ok &= check("clawrtc installed", shutil.which("clawrtc") is not None)
    ok &= check("Wallet exists", os.path.exists(os.path.expanduser("~/.clawrtc/wallets")))
    ok &= check("Disk > 1GB free", shutil.disk_usage("/").free > 1e9)
    try:
        ctx = ssl.create_default_context(); ctx.check_hostname = True; ctx.verify_mode = ssl.CERT_REQUIRED
        urllib.request.urlopen("https://rustchain.org/health", timeout=5, context=ctx)
        ok &= check("Node reachable", True)
    except:
        ok &= check("Node reachable", False)
    print(f"\n{'Ready to mine!' if ok else 'Fix issues above first.'}")
if __name__ == "__main__":
    preflight()
