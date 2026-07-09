#!/usr/bin/env python3
"""RustChain /api/tokenomics endpoint.

Read-only. Serves the published RTC reference rate, live holder count,
and the holder-milestone schedule codified at rustchain-bounties#12458.

The current rate is read from tokenomics_config.json next to this file so
milestone flips are an ops action (edit config + announce), not a deploy.
Registered from wsgi.py via register_tokenomics(app, DB_PATH).
"""

import json
import os
import sqlite3
import time
from contextlib import closing

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_CONFIG_PATH = os.path.join(_BASE_DIR, "tokenomics_config.json")

TOTAL_SUPPLY_RTC = 8_388_608  # 2^23, consensus-enforced
UNIT = 1_000_000  # uRTC per RTC

# Holder milestones per rustchain-bounties#12458 (one-way ratchet,
# announced 24-48h ahead, never retroactive)
MILESTONES = [
    {"holders": 761, "reference_rate_usd": 0.10, "label": "genesis"},
    {"holders": 1000, "reference_rate_usd": 0.15, "label": "1k holders"},
    {"holders": 2000, "reference_rate_usd": 0.20, "label": "2k holders"},
]

_cache = {"ts": 0.0, "holders": 0, "wallets": 0, "circulating_rtc": 0.0}
_CACHE_TTL_S = 60


def _read_rate() -> float:
    try:
        with open(_CONFIG_PATH) as f:
            return float(json.load(f)["reference_rate_usd"])
    except (OSError, ValueError, KeyError):
        return 0.15  # last published rate as fallback


def _ledger_stats(db_path: str) -> dict:
    now = time.time()
    if now - _cache["ts"] < _CACHE_TTL_S:
        return _cache
    with closing(sqlite3.connect(db_path, timeout=5)) as conn:
        row = conn.execute(
            "SELECT COUNT(*), COUNT(CASE WHEN amount_i64 > 0 THEN 1 END), "
            "COALESCE(SUM(amount_i64), 0) FROM balances"
        ).fetchone()
    _cache.update(
        ts=now,
        wallets=row[0],
        holders=row[1],
        circulating_rtc=round(row[2] / UNIT, 6),
    )
    return _cache


def register_tokenomics(app, db_path: str):
    from flask import jsonify

    @app.route("/api/tokenomics", methods=["GET"])
    @app.route("/tokenomics", methods=["GET"])
    def api_tokenomics():
        try:
            stats = _ledger_stats(db_path)
        except sqlite3.Error:
            return jsonify({"ok": False, "error": "ledger unavailable"}), 503

        rate = _read_rate()
        holders = stats["holders"]
        upcoming = [m for m in MILESTONES if m["reference_rate_usd"] > rate]
        next_milestone = None
        if upcoming:
            nxt = min(upcoming, key=lambda m: m["holders"])
            next_milestone = dict(nxt, holders_remaining=max(0, nxt["holders"] - holders))

        return jsonify({
            "ok": True,
            "token": "RTC",
            "total_supply_rtc": TOTAL_SUPPLY_RTC,
            "reference_rate_usd": rate,
            "rate_basis": ("internal reference rate for bounty accounting, "
                           "not a market price or promise of convertibility"),
            "holders": holders,
            "wallets": stats["wallets"],
            "circulating_rtc": stats["circulating_rtc"],
            "milestones": MILESTONES,
            "next_milestone": next_milestone,
            "policy": ("one-way ratchet, announced 24-48h ahead, not retroactive "
                       "(github.com/Scottcjn/rustchain-bounties/issues/12458)"),
            "as_of": int(time.time()),
        })
