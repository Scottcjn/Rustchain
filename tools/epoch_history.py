#!/usr/bin/env python3
"""RustChain Epoch History — Query past epoch data."""
import json, urllib.request, ssl, os, sys
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}
def history(n=5):
    e = api("/epoch")
    current = e.get("epoch", e.get("current_epoch", 0))
    print(f"Epoch History (last {n})")
    for ep in range(max(0, current-n+1), current+1):
        r = api(f"/rewards/epoch/{ep}")
        print(f"  Epoch {ep}: {json.dumps(r)[:80] if r else 'no data'}")
if __name__ == "__main__":
    history(int(sys.argv[1]) if len(sys.argv) > 1 else 5)
