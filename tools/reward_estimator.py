#!/usr/bin/env python3
"""RustChain Reward Estimator — Estimate next epoch reward."""
import json, urllib.request, ssl, os
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}
def estimate():
    e = api("/epoch")
    pot = float(e.get("epoch_pot", e.get("reward_pot", 0)))
    miners = int(e.get("enrolled_miners", 1))
    slot = int(e.get("slot", 0))
    slots_per = int(e.get("slots_per_epoch", 60))
    remaining = max(0, slots_per - (slot % slots_per if slots_per else 1))
    per_miner = pot / max(miners, 1)
    print(f"Next Epoch Reward Estimate")
    print(f"  Current pot:    {pot:.4f} RTC")
    print(f"  Miners:         {miners}")
    print(f"  Per miner:      {per_miner:.4f} RTC")
    print(f"  Slots left:     {remaining}")
    print(f"  Est. final pot: {pot * (1 + remaining * 0.001):.4f} RTC")
if __name__ == "__main__":
    estimate()
