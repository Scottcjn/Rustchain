#!/usr/bin/env python3
"""RustChain Miner Score — Calculate composite miner performance score."""
import json, urllib.request, ssl, os, sys
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
def api(p):
    ctx = ssl.create_default_context()
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}
def score(miner_id=None):
    miners = api("/api/miners")
    ml = miners if isinstance(miners, list) else miners.get("miners", [])
    if miner_id:
        ml = [m for m in ml if m.get("miner_id") == miner_id or m.get("id") == miner_id]
    for m in ml:
        blocks = int(m.get("blocks_mined", m.get("total_blocks", 0)))
        mult = float(m.get("antiquity_multiplier", m.get("multiplier", 1)))
        uptime = float(m.get("uptime", m.get("uptime_pct", 50)))
        s = int(blocks * mult * 0.5 + uptime * 0.5)
        grade = "S" if s > 500 else "A" if s > 200 else "B" if s > 100 else "C" if s > 50 else "D"
        mid = str(m.get("miner_id", m.get("id", "?")))[:16]
        print(f"  {mid}  Score: {s}  Grade: {grade}  (blocks:{blocks} mult:{mult} uptime:{uptime:.0f}%)")
if __name__ == "__main__":
    score(sys.argv[1] if len(sys.argv) > 1 else None)
