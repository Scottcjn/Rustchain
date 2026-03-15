#!/usr/bin/env python3
"""RustChain API Version Compatibility Check."""
import json, urllib.request, ssl, os
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
REQUIRED_ENDPOINTS = ["/health", "/epoch", "/api/miners", "/headers/tip"]
OPTIONAL_ENDPOINTS = ["/api/fee_pool", "/beacon/digest", "/agent/jobs", "/api/stats"]
def check():
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    print("API Compatibility Check")
    for ep in REQUIRED_ENDPOINTS:
        try:
            urllib.request.urlopen(f"{NODE}{ep}", timeout=5, context=ctx)
            print(f"  OK   {ep} (required)")
        except:
            print(f"  MISS {ep} (required) !!!")
    for ep in OPTIONAL_ENDPOINTS:
        try:
            urllib.request.urlopen(f"{NODE}{ep}", timeout=5, context=ctx)
            print(f"  OK   {ep} (optional)")
        except:
            print(f"  MISS {ep} (optional)")
if __name__ == "__main__":
    check()
