#!/usr/bin/env python3
"""RustChain Epoch Settlement Tracker — Watch reward distributions in real-time."""
import json, urllib.request, os, ssl, time

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
def api(p):
    try:
        ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}

def watch():
    last_epoch = None
    print("Watching for epoch settlements... (Ctrl+C to stop)")
    while True:
        e = api("/epoch")
        current = e.get("epoch", e.get("current_epoch", 0))
        if last_epoch is not None and current != last_epoch:
            pot = e.get("epoch_pot", e.get("reward_pot", 0))
            miners = e.get("enrolled_miners", 0)
            per_miner = pot / max(miners, 1)
            print(f"\n  EPOCH {last_epoch} → {current} SETTLED!")
            print(f"  Pot: {pot} RTC | Miners: {miners} | Per miner: {per_miner:.4f} RTC")
            rewards = api(f"/rewards/epoch/{last_epoch}")
            if rewards:
                print(f"  Reward details: {json.dumps(rewards)[:200]}")
        last_epoch = current
        time.sleep(30)

if __name__ == "__main__":
    try: watch()
    except KeyboardInterrupt: print("\nDone")
