#!/usr/bin/env python3
"""RustChain Miner Scheduler — Schedule mining during optimal times."""
import json, urllib.request, ssl, os, time, sched

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
scheduler = sched.scheduler(time.time, time.sleep)

def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}

def check_optimal():
    e = api("/epoch")
    miners = e.get("enrolled_miners", 0)
    pot = e.get("epoch_pot", e.get("reward_pot", 0))
    
    # Optimal when fewer miners = higher per-miner reward
    per_miner = pot / max(miners, 1)
    is_optimal = miners < 5 or per_miner > 1.0
    
    status = "OPTIMAL" if is_optimal else "SUBOPTIMAL"
    print(f"[{time.strftime('%H:%M:%S')}] Miners: {miners} | Pot: {pot} | Per miner: {per_miner:.4f} | {status}")
    
    # Reschedule check
    scheduler.enter(300, 1, check_optimal)

def main():
    print("RustChain Mining Scheduler")
    print("Checking every 5 minutes for optimal mining conditions...")
    scheduler.enter(0, 1, check_optimal)
    scheduler.run()

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: print("\nScheduler stopped")
