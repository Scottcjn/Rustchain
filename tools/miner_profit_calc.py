#!/usr/bin/env python3
"""RustChain Miner Profit Calculator — Real-time profit estimation."""
import json, urllib.request, ssl, os, sys
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}
def calc(watts=50, elec=0.12, mult=1.0):
    e = api("/epoch")
    pot = float(e.get("epoch_pot", e.get("reward_pot", 0.5)))
    miners = int(e.get("enrolled_miners", 3))
    reward = pot / max(miners, 1) * mult
    daily = reward * 24
    daily_cost = (watts / 1000) * 24 * elec
    profit = daily * 0.10 - daily_cost
    print(f"Daily RTC: {daily:.4f} | Revenue: ${daily*0.10:.4f} | Power: ${daily_cost:.4f} | Profit: ${profit:.4f}")
if __name__ == "__main__":
    calc(float(sys.argv[1]) if len(sys.argv) > 1 else 50,
         float(sys.argv[2]) if len(sys.argv) > 2 else 0.12,
         float(sys.argv[3]) if len(sys.argv) > 3 else 1.0)
