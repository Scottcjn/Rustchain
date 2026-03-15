#!/usr/bin/env python3
"""RustChain JSON Health Check."""
import json, urllib.request, ssl, os, time, sys
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
def check():
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    results = {}
    for ep in ["/health", "/epoch", "/headers/tip"]:
        s = time.time()
        try:
            urllib.request.urlopen(f"{NODE}{ep}", timeout=10, context=ctx)
            results[ep] = {"ok": True, "ms": round((time.time()-s)*1000,1)}
        except:
            results[ep] = {"ok": False}
    out = {"healthy": all(r["ok"] for r in results.values()), "checks": results}
    print(json.dumps(out, indent=2))
    sys.exit(0 if out["healthy"] else 1)
if __name__ == "__main__":
    check()
