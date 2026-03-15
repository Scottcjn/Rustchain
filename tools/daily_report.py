#!/usr/bin/env python3
"""RustChain Daily Report — Generate daily mining summary."""
import json, urllib.request, ssl, os, time
from datetime import datetime
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}
def report():
    h = api("/health"); e = api("/epoch"); m = api("/api/miners"); f = api("/api/fee_pool")
    ml = m if isinstance(m, list) else m.get("miners", [])
    r = f"RustChain Daily Report — {datetime.utcnow().strftime('%Y-%m-%d')}\n"
    r += f"{'='*45}\n"
    r += f"Status: {h.get('status','?')} | Version: {h.get('version','?')}\n"
    r += f"Epoch: {e.get('epoch', e.get('current_epoch','?'))} | Slot: {e.get('slot','?')}\n"
    r += f"Miners: {len(ml)} | Pot: {e.get('epoch_pot', e.get('reward_pot','?'))} RTC\n"
    r += f"Supply: {e.get('total_supply','?')} RTC | Fees: {f.get('fee_pool', f.get('balance','?'))} RTC\n"
    print(r)
    with open(f"daily_report_{datetime.utcnow().strftime('%Y%m%d')}.txt", "w") as fh:
        fh.write(r)
if __name__ == "__main__":
    report()
