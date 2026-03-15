#!/usr/bin/env python3
"""RustChain Detect chain reorganizations."""
import json, urllib.request, ssl, os, time, sys, hashlib
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try:
        s = time.time()
        r = urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx)
        return json.loads(r.read()), round((time.time()-s)*1000, 1), r.status
    except Exception as e: return {}, 0, 0
def main():
    h, hms, hs = api("/health")
    e, ems, es = api("/epoch")
    m, mms, ms = api("/api/miners")
    f, fms, fs = api("/api/fee_pool")
    t, tms, ts = api("/headers/tip")
    ml = m if isinstance(m, list) else m.get("miners", [])
    print(f"Detect chain reorganizations")
    print(f"  Status: {h.get('status','?')} v{h.get('version','?')} uptime:{h.get('uptime','?')}")
    print(f"  Epoch: {e.get('epoch', e.get('current_epoch','?'))} | Slot: {e.get('slot','?')} | Height: {t.get('height', t.get('slot','?'))}")
    print(f"  Miners: {len(ml)} | Pot: {e.get('epoch_pot', e.get('reward_pot','?'))} | Fees: {f.get('fee_pool', f.get('balance','?'))} RTC")
    print(f"  Latency: health:{hms}ms epoch:{ems}ms miners:{mms}ms tip:{tms}ms")
if __name__ == "__main__":
    main()
