#!/usr/bin/env python3
"""RustChain Cache Warmer — Pre-fetch all API endpoints to warm caches."""
import urllib.request, ssl, os, time
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
ENDPOINTS = ["/health","/epoch","/api/miners","/api/stats","/headers/tip","/api/fee_pool","/beacon/digest"]
def warm():
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    print("Warming API caches...")
    for ep in ENDPOINTS:
        s = time.time()
        try:
            urllib.request.urlopen(f"{NODE}{ep}", timeout=10, context=ctx)
            print(f"  OK {ep} ({(time.time()-s)*1000:.0f}ms)")
        except:
            print(f"  FAIL {ep}")
    print("Cache warm complete!")
if __name__ == "__main__":
    warm()
