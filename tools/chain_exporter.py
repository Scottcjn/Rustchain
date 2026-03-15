#!/usr/bin/env python3
"""RustChain Chain Data Exporter — Export chain state to various formats."""
import json, csv, urllib.request, ssl, os

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")

def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}

def export_miners(fmt="csv"):
    miners = api("/api/miners")
    miner_list = miners if isinstance(miners, list) else miners.get("miners", [])
    if fmt == "csv" and miner_list:
        with open("miners_export.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=miner_list[0].keys())
            w.writeheader(); w.writerows(miner_list)
        print(f"Exported {len(miner_list)} miners to miners_export.csv")
    else:
        with open("miners_export.json", "w") as f:
            json.dump(miner_list, f, indent=2)
        print(f"Exported {len(miner_list)} miners to miners_export.json")

def export_full():
    state = {"health": api("/health"), "epoch": api("/epoch"), "tip": api("/headers/tip"),
             "miners": api("/api/miners"), "stats": api("/api/stats"), "fee_pool": api("/api/fee_pool")}
    with open("chain_state.json", "w") as f:
        json.dump(state, f, indent=2)
    print("Full chain state exported to chain_state.json")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "full": export_full()
    else: export_miners(sys.argv[1] if len(sys.argv) > 1 else "csv")
