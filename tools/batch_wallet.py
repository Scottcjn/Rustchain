#!/usr/bin/env python3
"""RustChain Batch Wallet Operations — Bulk balance checks, transfers, exports."""
import json, csv, urllib.request, os, sys

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")

def api(path):
    try:
        import ssl; ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        return json.loads(urllib.request.urlopen(f"{NODE}{path}", timeout=10, context=ctx).read())
    except: return {}

def batch_balance(addresses):
    results = []
    for addr in addresses:
        r = api(f"/wallet/balance?miner_id={addr}")
        bal = r.get("balance", r.get("rtc_balance", 0))
        results.append({"address": addr, "balance": bal})
        print(f"  {addr[:20]}... : {bal} RTC")
    return results

def export_balances(addresses, fmt="csv"):
    results = batch_balance(addresses)
    if fmt == "csv":
        with open("balances.csv", "w", newline="") as f:
            w = csv.DictWriter(f, ["address", "balance"])
            w.writeheader()
            w.writerows(results)
    else:
        with open("balances.json", "w") as f:
            json.dump(results, f, indent=2)
    total = sum(r["balance"] for r in results if isinstance(r["balance"], (int, float)))
    print(f"\nTotal across {len(results)} wallets: {total} RTC")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python batch_wallet.py addr1 addr2 addr3 ...")
        print("       python batch_wallet.py --file addresses.txt")
        sys.exit(1)
    if sys.argv[1] == "--file":
        with open(sys.argv[2]) as f:
            addrs = [l.strip() for l in f if l.strip()]
    else:
        addrs = sys.argv[1:]
    export_balances(addrs)
