import requests
import time
import json
import os
from datetime import datetime

# Configuration
# Note: Production bridge APIs might be on different nodes or ports
# We will poll known nodes for bridge endpoints
BRIDGE_NODES = [
    {"name": "Node 1", "url": "https://50.28.86.131/bridge/stats"},
    {"name": "Node 2", "url": "https://50.28.86.153/bridge/stats"},
]

# Solana RPC for wRTC Supply (Mainnet-beta example)
# SOLANA_RPC = "https://api.mainnet-beta.solana.com"
# wRTC Mint Address on Solana (Hypothetical for now)
WRTC_MINT = "wRTCxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

DATA_FILE = "bridge_status.json"

def safe_dict(value):
    return value if isinstance(value, dict) else {}

def safe_list(value):
    return value if isinstance(value, list) else []

def safe_number(value, fallback=0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return number if number == number else fallback

def get_bridge_stats():
    results = {
        "timestamp": datetime.now().isoformat(),
        "bridge_nodes": [],
        "total_locked_rtc": 0,
        "circulating_wrtc": 0,
        "recent_transactions": []
    }
    
    # 1. Poll Bridge Nodes
    for node in BRIDGE_NODES:
        try:
            resp = requests.get(node["url"], timeout=10, verify=os.path.expanduser("~/.rustchain/node_cert.pem") if os.path.exists(os.path.expanduser("~/.rustchain/node_cert.pem")) else True)
            if resp.status_code == 200:
                data = safe_dict(resp.json())
                all_time = safe_dict(data.get("all_time"))
                solana_stats = safe_dict(safe_dict(data.get("by_chain")).get("solana"))
                node_stats = {
                    "name": node["name"],
                    "status": "up",
                    "total_locked": safe_number(all_time.get("total_rtc_locked")),
                    "completed_count": safe_number(solana_stats.get("bridged_count"))
                }
                results["bridge_nodes"].append(node_stats)
                # Take max locked value from healthy nodes as source of truth
                results["total_locked_rtc"] = max(results["total_locked_rtc"], node_stats["total_locked"])
            else:
                results["bridge_nodes"].append({"name": node["name"], "status": "down", "error": f"HTTP {resp.status_code}"})
        except Exception as e:
            results["bridge_nodes"].append({"name": node["name"], "status": "down", "error": str(e)})

    # 2. Get Recent Ledger (from first healthy node)
    for node in BRIDGE_NODES:
        try:
            ledger_url = node["url"].replace("/stats", "/ledger?limit=10")
            resp = requests.get(ledger_url, timeout=10, verify=os.path.expanduser("~/.rustchain/node_cert.pem") if os.path.exists(os.path.expanduser("~/.rustchain/node_cert.pem")) else True)
            if resp.status_code == 200:
                results["recent_transactions"] = safe_list(safe_dict(resp.json()).get("locks"))
                break
        except: continue

    # 3. Save to data file
    with open(DATA_FILE, 'w') as f:
        json.dump(results, f, indent=2)
    
    return results

if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    print("Updating wRTC Bridge Stats...")
    stats = get_bridge_stats()
    print(f"Total Locked RTC: {stats['total_locked_rtc']}")
    print(f"Recent Tx Count: {len(stats['recent_transactions'])}")
