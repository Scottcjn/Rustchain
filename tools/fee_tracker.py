#!/usr/bin/env python3
"""RustChain Fee Pool Tracker — Monitor fee accumulation and distribution."""
import json, urllib.request, os, time, sqlite3
from datetime import datetime

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
DB = os.path.expanduser("~/.rustchain/fee_history.db")

def api(path):
    try:
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return json.loads(urllib.request.urlopen(f"{NODE}{path}", timeout=10, context=ctx).read())
    except:
        return {}

def init_db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.execute("CREATE TABLE IF NOT EXISTS snapshots (ts TEXT, epoch INT, fee_pool REAL, total_fees REAL)")
    conn.commit()
    return conn

def track():
    conn = init_db()
    fee = api("/api/fee_pool")
    epoch = api("/epoch")
    
    pool = fee.get("fee_pool", fee.get("balance", 0))
    total = fee.get("total_collected", 0)
    ep = epoch.get("epoch", epoch.get("current_epoch", 0))
    
    conn.execute("INSERT INTO snapshots VALUES (?,?,?,?)",
                 (datetime.utcnow().isoformat(), ep, pool, total))
    conn.commit()
    
    # Get history
    rows = conn.execute("SELECT * FROM snapshots ORDER BY ts DESC LIMIT 10").fetchall()
    
    print(f"Fee Pool: {pool} RTC")
    print(f"Total Collected: {total} RTC")
    print(f"Current Epoch: {ep}")
    print(f"\nHistory ({len(rows)} snapshots):")
    for ts, e, fp, tf in rows:
        print(f"  {ts[:19]} | Epoch {e} | Pool: {fp} | Total: {tf}")
    
    conn.close()

if __name__ == "__main__":
    track()
