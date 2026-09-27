#!/usr/bin/env python3
"""Run settle_epoch_rip200 from a given source dir against a synthetic DB.

Usage: settle_probe.py <source_dir> <db_path> <epoch> <adm:0|1> [hold_json]
Prints the result JSON and per-miner balances. Runs in its own process so the
live and patched module sets never share sys.modules.
"""
import json
import os
import sqlite3
import sys

src, db, epoch, adm = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4] == "1"
sys.path.insert(0, src)
# the rest of node/ (utxo_db, db_helpers, ...) and sybil_guard for the patched run
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.modules["rustchain_p2p_sync_secure"] = None
os.environ.setdefault("RUSTCHAIN_DB_PATH", db)
os.environ.setdefault("DB_PATH", db)
import rewards_implementation_rip200 as ri  # noqa: E402

ri.DB_PATH = db
res = ri.settle_epoch_rip200(db, epoch, enable_anti_double_mining=adm)
with sqlite3.connect(db) as c:
    bal = dict(c.execute("SELECT miner_id, amount_i64 FROM balances"))
    # The live (pre-guard) module set never creates the escrow table, so test
    # for it explicitly instead of swallowing sqlite errors (falsegreen FG001):
    # any real DB failure now propagates and the probe exits non-zero.
    has_escrow = c.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sybil_review_escrow'"
    ).fetchone() is not None
    esc = (c.execute("SELECT epoch, miner, would_be_weight_units, reason FROM sybil_review_escrow").fetchall()
           if has_escrow else [])
print(json.dumps({"ok": res.get("ok"), "error": res.get("error"), "adm": "anti_double_mining_telemetry" in res,
                  "balances": bal, "escrow": esc,
                  "ADM_AVAILABLE": ri.ANTI_DOUBLE_MINING_AVAILABLE}, default=str))
