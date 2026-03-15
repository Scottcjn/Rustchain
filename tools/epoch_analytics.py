#!/usr/bin/env python3
"""RustChain Epoch Analytics — Historical epoch performance analysis."""
import json, urllib.request, ssl, os, sqlite3, time
from datetime import datetime

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
DB = os.path.expanduser("~/.rustchain/epoch_analytics.db")

def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}

def init_db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS epochs 
        (epoch INT PRIMARY KEY, slot INT, miners INT, pot REAL, supply REAL, ts TEXT)""")
    conn.commit()
    return conn

def record():
    conn = init_db()
    e = api("/epoch")
    ep = e.get("epoch", e.get("current_epoch", 0))
    conn.execute("INSERT OR REPLACE INTO epochs VALUES (?,?,?,?,?,?)",
        (ep, e.get("slot", 0), e.get("enrolled_miners", 0),
         e.get("epoch_pot", e.get("reward_pot", 0)),
         e.get("total_supply", 0), datetime.utcnow().isoformat()))
    conn.commit()
    
    # Analytics
    rows = conn.execute("SELECT * FROM epochs ORDER BY epoch DESC LIMIT 20").fetchall()
    print(f"Epoch Analytics ({len(rows)} records)")
    print("=" * 60)
    for ep, slot, miners, pot, supply, ts in rows:
        print(f"  Epoch {ep:>4} | Slot {slot:>5} | Miners: {miners} | Pot: {pot:.2f} RTC")
    
    if len(rows) >= 2:
        avg_miners = sum(r[2] for r in rows) / len(rows)
        avg_pot = sum(r[3] for r in rows) / len(rows)
        print(f"\n  Avg miners: {avg_miners:.1f} | Avg pot: {avg_pot:.2f} RTC")
    conn.close()

if __name__ == "__main__":
    record()
