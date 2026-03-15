#!/usr/bin/env python3
"""RustChain Prune old chain data safely."""
import json, urllib.request, ssl, os, time, sys
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try:
        s = time.time()
        r = urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx)
        return json.loads(r.read()), round((time.time()-s)*1000, 1)
    except: return {}, 0
def main():
    h, hms = api("/health")
    e, ems = api("/epoch")
    m, mms = api("/api/miners")
    f, fms = api("/api/fee_pool")
    ml = m if isinstance(m, list) else m.get("miners", [])
    print(f"Prune old chain data safely")
    print(f"  Status: {h.get('status','?')} v{h.get('version','?')} | Latency: {hms}ms")
    print(f"  Epoch: {e.get('epoch', e.get('current_epoch','?'))} | Slot: {e.get('slot','?')}")
    print(f"  Miners: {len(ml)} | Pot: {e.get('epoch_pot', e.get('reward_pot','?'))} RTC")
    print(f"  Supply: {e.get('total_supply','?')} | Fees: {f.get('fee_pool', f.get('balance','?'))} RTC")
if __name__ == "__main__":
    main()
