#!/usr/bin/env python3
"""RustChain wRTC Price Tracker — Live price with SQLite history."""
import json, urllib.request, os, time, sqlite3
from datetime import datetime

DB = os.path.expanduser("~/.rustchain/price_history.db")
PAIR = "8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb"

def get_price():
    try:
        r = urllib.request.urlopen(f"https://api.dexscreener.com/latest/dex/pairs/solana/{PAIR}", timeout=10)
        data = json.loads(r.read())
        pair = data.get("pair", data.get("pairs", [{}])[0] if isinstance(data.get("pairs"), list) else {})
        return {
            "price_usd": float(pair.get("priceUsd", 0)),
            "price_sol": float(pair.get("priceNative", 0)),
            "volume_24h": float(pair.get("volume", {}).get("h24", 0)),
            "change_24h": float(pair.get("priceChange", {}).get("h24", 0)),
            "liquidity": float(pair.get("liquidity", {}).get("usd", 0)),
        }
    except: return None

def track():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.execute("CREATE TABLE IF NOT EXISTS prices (ts TEXT, usd REAL, sol REAL, vol REAL, change REAL)")
    conn.commit()
    
    p = get_price()
    if p:
        conn.execute("INSERT INTO prices VALUES (?,?,?,?,?)",
                     (datetime.utcnow().isoformat(), p["price_usd"], p["price_sol"], p["volume_24h"], p["change_24h"]))
        conn.commit()
        
        print(f"wRTC Price: ${p['price_usd']:.6f}")
        print(f"24h Change: {p['change_24h']:+.2f}%")
        print(f"24h Volume: ${p['volume_24h']:,.0f}")
        print(f"Liquidity:  ${p['liquidity']:,.0f}")
    
    rows = conn.execute("SELECT * FROM prices ORDER BY ts DESC LIMIT 10").fetchall()
    if rows:
        print(f"\nPrice History ({len(rows)} snapshots):")
        for ts, usd, sol, vol, chg in rows:
            print(f"  {ts[:16]} | ${usd:.6f} | {chg:+.1f}%")
    conn.close()

if __name__ == "__main__":
    track()
