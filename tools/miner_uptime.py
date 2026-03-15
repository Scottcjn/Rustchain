#!/usr/bin/env python3
"""RustChain Miner Uptime Tracker."""
import json, urllib.request, ssl, os, time, sqlite3
from datetime import datetime
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
DB = os.path.expanduser("~/.rustchain/uptime.db")
def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}
def track():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.execute("CREATE TABLE IF NOT EXISTS checks (ts TEXT, up INT, latency REAL)")
    conn.commit()
    start = time.time()
    h = api("/health")
    latency = (time.time() - start) * 1000
    up = 1 if h.get("status") == "ok" else 0
    conn.execute("INSERT INTO checks VALUES (?,?,?)", (datetime.utcnow().isoformat(), up, latency))
    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM checks").fetchone()[0]
    up_count = conn.execute("SELECT COUNT(*) FROM checks WHERE up=1").fetchone()[0]
    pct = up_count / total * 100 if total > 0 else 0
    print(f"Uptime: {pct:.1f}% ({up_count}/{total} checks) | Last: {'UP' if up else 'DOWN'} {latency:.0f}ms")
    conn.close()
if __name__ == "__main__":
    track()
