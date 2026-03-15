#!/usr/bin/env python3
"""RustChain Track transaction nonces."""
import json, urllib.request, ssl, os, time, sys
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try:
        s = time.time()
        r = urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx)
        return json.loads(r.read()), round((time.time()-s)*1000, 1), r.status
    except: return {}, 0, 0
def main():
    h, hms, _ = api("/health")
    e, ems, _ = api("/epoch")
    m, mms, _ = api("/api/miners")
    f, fms, _ = api("/api/fee_pool")
    t, tms, _ = api("/headers/tip")
    ml = m if isinstance(m, list) else m.get("miners", [])
    print(f"Track transaction nonces")
    print(f"  Node: {h.get('status','?')} v{h.get('version','?')} ({hms}ms)")
    print(f"  Chain: epoch={e.get('epoch', e.get('current_epoch','?'))} slot={e.get('slot','?')} tip={t.get('height', t.get('slot','?'))}")
    print(f"  Miners: {len(ml)} | Pot: {e.get('epoch_pot', e.get('reward_pot','?'))} RTC | Fees: {f.get('fee_pool', f.get('balance','?'))} RTC")
    print(f"  Supply: {e.get('total_supply','?')} RTC | Uptime: {h.get('uptime','?')}")
if __name__ == "__main__":
    main()
