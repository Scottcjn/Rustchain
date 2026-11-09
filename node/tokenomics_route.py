#!/usr/bin/env python3
"""RustChain /api/tokenomics endpoint.

Read-only. Serves the fixed RTC supply, live holder/wallet counts and
circulating supply from the ledger, plus a plain statement of what RTC is.

RTC carries no USD reference rate and no holder-count price schedule: it is
an experimental token with no cash value and no off-ramp (see POLICY).
Registered from wsgi.py via register_tokenomics(app, DB_PATH).
"""

import sqlite3
import time
from contextlib import closing

TOTAL_SUPPLY_RTC = 8_388_608  # 2^23, consensus-enforced
UNIT = 1_000_000  # uRTC per RTC

POLICY = ("RTC is an experimental token used inside the RustChain ecosystem to "
          "recognize contributions and pay for services. It has no cash value and no "
          "off-ramp: no exchange listing, no redemption, no conversion to cash. "
          "Bounty amounts are set in RTC per bounty.")

_cache = {"ts": 0.0, "holders": 0, "wallets": 0, "circulating_rtc": 0.0}
_CACHE_TTL_S = 60


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

        return jsonify({
            "ok": True,
            "token": "RTC",
            "total_supply_rtc": TOTAL_SUPPLY_RTC,
            "holders": stats["holders"],
            "wallets": stats["wallets"],
            "circulating_rtc": stats["circulating_rtc"],
            "policy": POLICY,
            "as_of": int(time.time()),
        })
