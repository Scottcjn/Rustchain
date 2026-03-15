#!/usr/bin/env python3
"""RustChain Mining Statistics."""
import json, urllib.request, ssl, os
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}
def report():
    e = api("/epoch"); m = api("/api/miners"); f = api("/api/fee_pool")
    ml = m if isinstance(m, list) else m.get("miners", [])
    hw = {}
    for miner in ml:
        h = miner.get("hardware", "unknown")
        hw[h] = hw.get(h, 0) + 1
    print(f"Miners: {len(ml)} | Pot: {e.get('epoch_pot', '?')} RTC | Fees: {f.get('fee_pool', '?')} RTC")
    for h, c in sorted(hw.items(), key=lambda x: -x[1]):
        print(f"  {h}: {c}")
if __name__ == "__main__":
    report()
