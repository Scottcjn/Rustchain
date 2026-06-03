#!/usr/bin/env python3
"""RustChain Miner Score — Calculate composite miner performance score."""
import json
import os
import ssl
import sys
import urllib.request

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")


def api(p):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except Exception:
        return {}


def _miner_rows(payload):
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = []
        for key in ("miners", "data", "items", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                rows = value
                break
    else:
        rows = []
    return [row for row in rows if isinstance(row, dict)]


def _as_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def score(miner_id=None):
    miners = api("/api/miners")
    ml = _miner_rows(miners)
    if miner_id:
        ml = [m for m in ml if m.get("miner_id") == miner_id or m.get("id") == miner_id]
    for m in ml:
        blocks = _as_int(m.get("blocks_mined", m.get("total_blocks", 0)))
        mult = _as_float(m.get("antiquity_multiplier", m.get("multiplier", 1)), 1.0)
        uptime = _as_float(m.get("uptime", m.get("uptime_pct", 50)), 50.0)
        s = int(blocks * mult * 0.5 + uptime * 0.5)
        grade = "S" if s > 500 else "A" if s > 200 else "B" if s > 100 else "C" if s > 50 else "D"
        mid = str(m.get("miner_id", m.get("id", "?")))[:16]
        print(f"  {mid}  Score: {s}  Grade: {grade}  (blocks:{blocks} mult:{mult} uptime:{uptime:.0f}%)")


if __name__ == "__main__":
    score(sys.argv[1] if len(sys.argv) > 1 else None)
