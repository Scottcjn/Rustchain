#!/usr/bin/env python3
"""RustChain Reward History — Export mining rewards to CSV/JSON."""
import json, csv, urllib.request, os, sys

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")

def api(path):
    try:
        import ssl; ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        return json.loads(urllib.request.urlopen(f"{NODE}{path}", timeout=10, context=ctx).read())
    except:
        return {}

def export(miner_id, fmt="csv"):
    rewards = api(f"/rewards/history/{miner_id}")
    if not rewards:
        rewards = api(f"/wallet/history/{miner_id}")
    
    entries = rewards if isinstance(rewards, list) else rewards.get("history", rewards.get("rewards", []))
    
    if fmt == "json":
        with open(f"rewards_{miner_id[:12]}.json", "w") as f:
            json.dump(entries, f, indent=2)
        print(f"Exported {len(entries)} entries to rewards_{miner_id[:12]}.json")
    else:
        with open(f"rewards_{miner_id[:12]}.csv", "w", newline="") as f:
            if entries:
                w = csv.DictWriter(f, fieldnames=entries[0].keys())
                w.writeheader()
                w.writerows(entries)
        print(f"Exported {len(entries)} entries to rewards_{miner_id[:12]}.csv")
    
    total = sum(float(e.get("amount", e.get("reward", 0))) for e in entries)
    print(f"Total earned: {total} RTC")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python reward_history.py <miner_id> [csv|json]")
        sys.exit(1)
    export(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "csv")
