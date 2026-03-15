#!/usr/bin/env python3
"""RustChain Network Snapshot — Capture complete network state at a point in time."""
import json, urllib.request, ssl, os, time
from datetime import datetime

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
ENDPOINTS = {
    "health": "/health", "epoch": "/epoch", "miners": "/api/miners",
    "stats": "/api/stats", "tip": "/headers/tip", "fee_pool": "/api/fee_pool",
    "beacon": "/beacon/digest", "genesis": "/genesis/export"
}

def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {"error": "unreachable"}

def snapshot():
    ts = datetime.utcnow().isoformat()
    snap = {"timestamp": ts, "node": NODE, "data": {}}
    for name, path in ENDPOINTS.items():
        snap["data"][name] = api(path)
    fname = f"snapshot_{ts[:10].replace('-','')}_{ts[11:16].replace(':','')}.json"
    with open(fname, "w") as f:
        json.dump(snap, f, indent=2)
    print(f"Snapshot saved: {fname} ({len(snap['data'])} endpoints)")

if __name__ == "__main__":
    snapshot()
