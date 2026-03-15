#!/usr/bin/env python3
"""RustChain Tokenomics Calculator — Mining reward projections."""
import json, os, urllib.request

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")

def api(path):
    try:
        return json.loads(urllib.request.urlopen(f"{NODE}{path}", timeout=10).read())
    except:
        return {}

def calculate():
    epoch = api("/epoch")
    miners = api("/api/miners")
    stats = api("/api/stats")
    
    miner_list = miners if isinstance(miners, list) else miners.get("miners", [])
    num_miners = len(miner_list)
    epoch_num = epoch.get("epoch", epoch.get("current_epoch", 0))
    pot = epoch.get("epoch_pot", epoch.get("reward_pot", 0))
    supply = epoch.get("total_supply", 0)
    
    print("RustChain Tokenomics Calculator")
    print("=" * 50)
    print(f"Current Epoch: {epoch_num}")
    print(f"Active Miners: {num_miners}")
    print(f"Epoch Reward Pot: {pot} RTC")
    print(f"Total Supply: {supply} RTC")
    print()
    
    if num_miners > 0 and pot > 0:
        per_miner = pot / num_miners
        print(f"Estimated reward per miner: {per_miner:.4f} RTC/epoch")
        print()
        print("Mining Projections:")
        for mult_name, mult in [("x86 (1.0x)", 1.0), ("G3 (1.5x)", 1.5), ("G4 (2.5x)", 2.5), ("G5 (4.0x)", 4.0)]:
            daily = per_miner * mult * 24  # rough: ~1 epoch/hr
            monthly = daily * 30
            print(f"  {mult_name}: {daily:.2f} RTC/day | {monthly:.1f} RTC/month | ${monthly*0.10:.2f}/month")

if __name__ == "__main__":
    calculate()
