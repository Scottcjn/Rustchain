#!/usr/bin/env python3
"""RustChain Network Statistics Aggregator — Comprehensive network overview."""
import json, urllib.request, os, time
from datetime import datetime

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")

def api(path):
    try:
        import ssl; ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        return json.loads(urllib.request.urlopen(f"{NODE}{path}", timeout=10, context=ctx).read())
    except: return {}

def aggregate():
    health = api("/health")
    epoch = api("/epoch")
    miners = api("/api/miners")
    stats = api("/api/stats")
    tip = api("/headers/tip")
    fee = api("/api/fee_pool")
    
    miner_list = miners if isinstance(miners, list) else miners.get("miners", [])
    
    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "node": {
            "status": health.get("status", "unknown"),
            "version": health.get("version", "?"),
            "uptime": health.get("uptime", "?"),
        },
        "chain": {
            "epoch": epoch.get("epoch", epoch.get("current_epoch", 0)),
            "slot": epoch.get("slot", 0),
            "height": tip.get("height", tip.get("slot", 0)),
        },
        "network": {
            "active_miners": len(miner_list),
            "total_supply": epoch.get("total_supply", 0),
            "fee_pool": fee.get("fee_pool", fee.get("balance", 0)),
            "epoch_pot": epoch.get("epoch_pot", epoch.get("reward_pot", 0)),
        },
        "hardware_distribution": {},
    }
    
    for m in miner_list:
        hw = m.get("hardware", m.get("cpu_arch", "unknown"))
        report["hardware_distribution"][hw] = report["hardware_distribution"].get(hw, 0) + 1
    
    print(json.dumps(report, indent=2))
    
    with open("network_stats.json", "w") as f:
        json.dump(report, f, indent=2)

if __name__ == "__main__":
    aggregate()
