#!/usr/bin/env python3
"""RustChain Supply Tracker — Monitor total supply and emission rate."""
import json, urllib.request, ssl, os, sqlite3, time
from datetime import datetime

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
DB = os.path.expanduser("~/.rustchain/supply_history.db")

def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}

def track():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.execute("CREATE TABLE IF NOT EXISTS supply (ts TEXT, epoch INT, supply REAL, fee_pool REAL)")
    conn.commit()
    
    e = api("/epoch")
    f = api("/api/fee_pool")
    supply = e.get("total_supply", 0)
    epoch = e.get("epoch", e.get("current_epoch", 0))
    pool = f.get("fee_pool", f.get("balance", 0))
    
    conn.execute("INSERT INTO supply VALUES (?,?,?,?)",
        (datetime.utcnow().isoformat(), epoch, supply, pool))
    conn.commit()
    
    rows = conn.execute("SELECT * FROM supply ORDER BY ts DESC LIMIT 20").fetchall()
    print(f"RTC Supply: {supply}")
    print(f"Fee Pool: {pool} RTC")
    print(f"Epoch: {epoch}")
    if len(rows) >= 2:
        rate = (rows[0][2] - rows[-1][2]) / max(len(rows)-1, 1)
        print(f"Emission rate: {rate:.4f} RTC/sample")
    conn.close()

if __name__ == "__main__":
    track()
