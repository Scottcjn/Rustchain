#!/usr/bin/env python3
"""RustChain Node Info — Quick one-liner node status for scripts and monitoring."""
import json, urllib.request, ssl, os, sys

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")

def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}

def info(fmt="text"):
    h = api("/health"); e = api("/epoch")
    data = {
        "status": h.get("status", "?"), "version": h.get("version", "?"),
        "epoch": e.get("epoch", e.get("current_epoch", "?")), "slot": e.get("slot", "?"),
        "miners": e.get("enrolled_miners", "?"), "supply": e.get("total_supply", "?"),
    }
    if fmt == "json":
        print(json.dumps(data))
    elif fmt == "csv":
        print(",".join(str(v) for v in data.values()))
    else:
        print(" | ".join(f"{k}={v}" for k, v in data.items()))

if __name__ == "__main__":
    info(sys.argv[1] if len(sys.argv) > 1 else "text")
