#!/usr/bin/env python3
"""RustChain Status Badge — Generate shields.io compatible badge URLs."""
import json, urllib.request, ssl, os
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}
def badges():
    h = api("/health"); e = api("/epoch"); m = api("/api/miners")
    ml = m if isinstance(m, list) else m.get("miners", [])
    status = "up" if h.get("status") == "ok" else "down"
    color = "brightgreen" if status == "up" else "red"
    print("Shields.io Badge URLs:")
    print(f"  Status: https://img.shields.io/badge/RustChain-{status}-{color}")
    print(f"  Epoch:  https://img.shields.io/badge/epoch-{e.get('epoch','?')}-blue")
    print(f"  Miners: https://img.shields.io/badge/miners-{len(ml)}-purple")
    print(f"\nMarkdown:")
    print(f"  ![Status](https://img.shields.io/badge/RustChain-{status}-{color})")
if __name__ == "__main__":
    badges()
