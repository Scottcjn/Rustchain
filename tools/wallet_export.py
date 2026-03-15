#!/usr/bin/env python3
"""RustChain Wallet Export — Export wallet to various formats."""
import json, os, sys, csv
DIR = os.path.expanduser("~/.clawrtc/wallets")
def export_all(fmt="json"):
    wallets = []
    for f in os.listdir(DIR) if os.path.exists(DIR) else []:
        if f.endswith(".json"):
            with open(os.path.join(DIR, f)) as fh:
                w = json.load(fh)
                w["file"] = f
                wallets.append(w)
    if fmt == "csv" and wallets:
        with open("wallets_export.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=wallets[0].keys())
            writer.writeheader(); writer.writerows(wallets)
        print(f"Exported {len(wallets)} wallets to wallets_export.csv")
    else:
        with open("wallets_export.json", "w") as f:
            json.dump(wallets, f, indent=2)
        print(f"Exported {len(wallets)} wallets to wallets_export.json")
if __name__ == "__main__":
    export_all(sys.argv[1] if len(sys.argv) > 1 else "json")
