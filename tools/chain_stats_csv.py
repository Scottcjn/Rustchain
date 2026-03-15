#!/usr/bin/env python3
"""RustChain Chain Stats to CSV — Export chain metrics for spreadsheets."""
import json, urllib.request, ssl, os, csv, time
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}
def export():
    h = api("/health"); e = api("/epoch"); f = api("/api/fee_pool"); m = api("/api/miners")
    ml = m if isinstance(m, list) else m.get("miners", [])
    row = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"), "status": h.get("status","?"),
           "epoch": e.get("epoch", e.get("current_epoch",0)), "slot": e.get("slot",0),
           "miners": len(ml), "supply": e.get("total_supply",0),
           "pot": e.get("epoch_pot", e.get("reward_pot",0)), "fees": f.get("fee_pool", f.get("balance",0))}
    fname = "chain_stats.csv"
    exists = os.path.exists(fname)
    with open(fname, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=row.keys())
        if not exists: w.writeheader()
        w.writerow(row)
    print(f"Appended to {fname}: epoch {row['epoch']}")
if __name__ == "__main__":
    export()
