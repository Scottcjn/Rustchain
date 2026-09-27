# SPDX-License-Identifier: MIT
"""node/sophia_elya_service.py is a legacy RIP-0005 prototype, not the node.

It carries its own epoch enrollment + settlement writers with none of the real
node's protections (probation/Sybil holds, anti-double-mining, hardware binding,
fingerprint validation), hands out enrollment tickets from an unauthenticated
/attest/submit, and defaults to the relative DB path "./rustchain_v2.db" -- the
same filename the real node uses. These tests pin that its money paths fail
closed by default, and refuse a consensus-shaped DB even when opted in.
"""
import importlib.util
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "node" / "sophia_elya_service.py"
ENV = "RUSTCHAIN_SOPHIA_ELYA_LEGACY_SETTLEMENT"


@pytest.fixture
def svc(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV, raising=False)
    spec = importlib.util.spec_from_file_location("sophia_elya_guard_under_test", SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.DB_PATH = str(tmp_path / "rustchain_v2.db")
    mod.app.config["TESTING"] = True
    return mod


def _tables(path):
    if not os.path.exists(path):
        return set()
    with sqlite3.connect(path) as c:
        return {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_money_paths_fail_closed_by_default(svc):
    for call in (
        svc.init_db,
        lambda: svc.enroll_epoch(1, "miner", 1.0),
        lambda: svc.finalize_epoch(1, 1.5),
        lambda: svc.inc_epoch_block(1),
    ):
        with pytest.raises(svc.LegacySettlementDisabled, match="rustchain_v2_integrated"):
            call()
    assert not os.path.exists(svc.DB_PATH)  # nothing created, nothing written


def test_enroll_route_refuses_without_consuming_ticket(svc):
    svc.tickets_db["t1"] = {"expires_at": time.time() + 60}
    resp = svc.app.test_client().post(
        "/epoch/enroll", json={"miner_pubkey": "sybil", "ticket_id": "t1"}
    )
    assert resp.status_code == 503
    assert resp.get_json()["reason"] == "legacy_settlement_disabled"
    assert "t1" in svc.tickets_db
    assert "epoch_enroll" not in _tables(svc.DB_PATH)


def test_submit_block_route_refuses_before_settlement_or_accounting(svc):
    before = svc.LAST_HASH_B3
    resp = svc.app.test_client().post(
        "/api/submit_block",
        json={"header": {"prev_hash_b3": before, "slot": 5}, "header_ext": {}},
    )
    assert resp.status_code == 503
    assert resp.get_json()["reason"] == "legacy_settlement_disabled"
    assert svc.LAST_HASH_B3 == before
    assert svc.LAST_EPOCH is None
    assert not os.path.exists(svc.DB_PATH)


def _make_consensus_db(path, *, with_attest_table):
    with sqlite3.connect(path) as c:
        c.execute(
            "CREATE TABLE balances (miner_id TEXT PRIMARY KEY NOT NULL, "
            "amount_i64 INTEGER NOT NULL DEFAULT 0, miner_pk TEXT, "
            "balance_rtc REAL DEFAULT 0.0, coinbase_address TEXT)"
        )
        c.execute(
            "CREATE TABLE epoch_enroll (epoch INTEGER, miner_pk TEXT, weight INTEGER, "
            "PRIMARY KEY (epoch, miner_pk))"
        )
        c.execute(
            "CREATE TABLE epoch_state (epoch INTEGER PRIMARY KEY, accepted_blocks INTEGER "
            "DEFAULT 0, finalized INTEGER DEFAULT 0, settled INTEGER DEFAULT 0, settled_ts INTEGER)"
        )
        c.execute("INSERT INTO epoch_state VALUES (7, 3, 0, 0, NULL)")
        c.execute("INSERT INTO epoch_enroll VALUES (7, 'honest', 1)")
        if with_attest_table:
            c.execute("CREATE TABLE miner_attest_recent (miner TEXT PRIMARY KEY, ts_ok INTEGER)")


@pytest.mark.parametrize("with_attest_table", [True, False])
def test_opt_in_still_refuses_consensus_node_db(svc, monkeypatch, with_attest_table):
    monkeypatch.setenv(ENV, "1")
    _make_consensus_db(svc.DB_PATH, with_attest_table=with_attest_table)
    with sqlite3.connect(svc.DB_PATH) as c:
        before = c.execute("SELECT * FROM epoch_enroll ORDER BY miner_pk").fetchall()

    for call in (
        svc.init_db,
        lambda: svc.enroll_epoch(7, "sybil", 2.5),
        lambda: svc.finalize_epoch(7, 1.5),
        lambda: svc.inc_epoch_block(7),
    ):
        with pytest.raises(svc.LegacySettlementDisabled, match="consensus node database"):
            call()

    with sqlite3.connect(svc.DB_PATH) as c:
        assert c.execute("SELECT * FROM epoch_enroll ORDER BY miner_pk").fetchall() == before
        assert c.execute("SELECT settled, accepted_blocks FROM epoch_state WHERE epoch=7").fetchone() == (0, 3)


def test_opt_in_sandbox_db_still_works(svc, monkeypatch):
    monkeypatch.setenv(ENV, "1")
    svc.init_db()
    svc.inc_epoch_block(9)
    svc.enroll_epoch(9, "m", 1.0)
    result = svc.finalize_epoch(9, 1.5)
    assert result["ok"] is True
    assert result["payouts"] == [("m", 1.5)]


def test_running_as_main_refuses_to_start(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != ENV}
    proc = subprocess.run(
        [sys.executable, str(SRC)], cwd=tmp_path, env=env,
        capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode != 0
    assert "refusing to start" in proc.stderr
    assert not (tmp_path / "rustchain_v2.db").exists()
