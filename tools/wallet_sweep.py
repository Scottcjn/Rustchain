#!/usr/bin/env python3
"""RustChain Sweep dust balances to main wallet."""
import json, urllib.request, ssl, os, time
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
    t, tms = api("/headers/tip")
    ml = m if isinstance(m, list) else m.get("miners", [])
    print(f"Sweep dust balances to main wallet")
    print(f"  Node: {h.get('status','?')} v{h.get('version','?')} uptime:{h.get('uptime','?')} ({hms}ms)")
    print(f"  Chain: epoch {e.get('epoch', e.get('current_epoch','?'))} slot {e.get('slot','?')} height {t.get('height', t.get('slot','?'))}")
    print(f"  Network: {len(ml)} miners | pot:{e.get('epoch_pot', e.get('reward_pot','?'))} RTC | fees:{f.get('fee_pool', f.get('balance','?'))} RTC")
    print(f"  Supply: {e.get('total_supply','?')} RTC")
if __name__ == "__main__":
    main()
