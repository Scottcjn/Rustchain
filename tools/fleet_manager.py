#!/usr/bin/env python3
"""RustChain Fleet Manager — Multi-node management."""
import json, urllib.request, ssl, os
FLEET = os.environ.get("RUSTCHAIN_FLEET", "https://rustchain.org,https://50.28.86.131").split(",")
def api(node, p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{node.strip()}{p}", timeout=10, context=ctx).read())
    except: return {}
def status():
    print("Fleet Status")
    for node in FLEET:
        h = api(node, "/health")
        ok = h.get("status") == "ok"
        print(f"  {'UP' if ok else 'DN'}  {node.strip()}")
if __name__ == "__main__":
    status()
