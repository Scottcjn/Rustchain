#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Regression tests for #16471 silent-success / wrong-effect defects in node settlement & payout ledger."""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
NODE_DIR = ROOT / "node"
for p in (str(ROOT), str(NODE_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import anti_double_mining as adm
import auto_epoch_settler
import payout_ledger
import rewards_implementation_rip200 as rew
import settle_epoch as settle_epoch_cli
import sybil_guard


def test_adm_no_eligible_miners_rolls_back_sybil_escrow_rows(tmp_path: Path):
    """Defect 4: when settle_epoch_with_anti_double_mining returns ok=False (no_eligible_miners)
    on a shared connection, settle_epoch_rip200 must roll back instead of committing
    orphan sybil_review_escrow rows for an unsettled epoch."""
    db_path = str(tmp_path / "test_adm_rollback.db")
    adm.setup_test_scenario(db_path)
    with sqlite3.connect(db_path) as conn:
        sybil_guard.init_schema(conn)
        for m in ("miner-a1", "miner-a2", "miner-a3", "miner-b1", "miner-c1", "miner-c2"):
            conn.execute(
                "UPDATE miner_attest_recent SET fingerprint_passed = 0 WHERE miner = ?",
                (m,),
            )
            conn.execute("INSERT INTO epoch_enroll (epoch, miner_pk) VALUES (0, ?)", (m,))
        conn.execute("ALTER TABLE epoch_enroll ADD COLUMN weight REAL DEFAULT 2.5")
        conn.execute("UPDATE epoch_enroll SET weight = 2.5")
        conn.execute(
            "INSERT INTO miner_probation (miner, state, first_seen, last_seen, needs_review, review_reason, updated_at) "
            "VALUES (?, ?, 1700000000, 1700000000, 1, ?, 1700000000)",
            ("miner-b1", "grandfathered", "manual_review"),
        )
        conn.commit()

    res = rew.settle_epoch_rip200(db_path, epoch=0, enable_anti_double_mining=True)
    assert res["ok"] is False
    assert res["error"] == "no_eligible_miners"

    with sqlite3.connect(db_path) as conn:
        escrow_rows = conn.execute(
            "SELECT epoch, miner, would_be_weight_units FROM sybil_review_escrow"
        ).fetchall()
    assert escrow_rows == []


def test_auto_epoch_settler_uses_epoch_endpoint_and_epoch_enroll(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Defect 5a: auto_epoch_settler must query /epoch (not only non-existent /api/stats)
    and detect unsettled epochs from epoch_enroll even when headers has 0 rows."""
    db_path = str(tmp_path / "auto_settler.db")
    monkeypatch.setattr(auto_epoch_settler, "DB_PATH", db_path)

    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE headers (slot INTEGER)")
        conn.execute("CREATE TABLE epoch_enroll (epoch INTEGER, miner_pk TEXT)")
        conn.execute("CREATE TABLE epoch_state (epoch INTEGER PRIMARY KEY, settled INTEGER)")
        conn.execute("INSERT INTO epoch_enroll (epoch, miner_pk) VALUES (5, 'miner-1')")
        conn.commit()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"epoch": 6, "slot": 6 * 144 + 10}

    with patch.object(auto_epoch_settler.requests, "get", return_value=mock_resp):
        slot = auto_epoch_settler.get_current_slot()
        assert slot == 6 * 144 + 10
        unsettled = auto_epoch_settler.get_unsettled_epochs()
        assert unsettled == [5]


def test_settle_epoch_cli_returns_none_on_401_or_ok_false(monkeypatch: pytest.MonkeyPatch):
    """Defect 5b: node/settle_epoch.py trigger_settlement() must pass X-Admin-Key when set
    and return None when /rewards/settle responds with ok=False or non-200."""
    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin-secret")
    epoch_resp = MagicMock(status_code=200)
    epoch_resp.json.return_value = {"epoch": 10}

    refused_resp = MagicMock(status_code=200)
    refused_resp.json.return_value = {"ok": False, "error": "no_eligible_miners"}

    with patch.object(settle_epoch_cli.requests, "get", return_value=epoch_resp), patch.object(
        settle_epoch_cli.requests, "post", return_value=refused_resp
    ) as mock_post:
        res = settle_epoch_cli.trigger_settlement()
        assert res is None
        assert mock_post.call_args.kwargs["headers"]["X-Admin-Key"] == "test-admin-secret"


def test_payout_ledger_preserves_tx_hash_against_empty_string_and_updates_blank_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Defect 5c: payout_ledger must not erase a recorded tx_hash when tx_hash='' is passed
    on status advance, and must allow attaching tx_hash to an already-confirmed record whose
    tx_hash was blank."""
    db_path = str(tmp_path / "ledger.db")
    monkeypatch.setattr(payout_ledger, "DB_PATH", db_path)
    payout_ledger.init_payout_ledger_tables()

    rec_id = payout_ledger.ledger_create("16471", "cyzcz", "35", wallet_address="RTC" + "a" * 40)
    assert payout_ledger.ledger_update_status(rec_id, "pending", tx_hash="0xabc123", notes="queued")

    # Advancing to confirmed with tx_hash="" must NOT erase "0xabc123"
    assert payout_ledger.ledger_update_status(rec_id, "confirmed", tx_hash="", notes="")
    rec = payout_ledger.ledger_get(rec_id)
    assert rec["status"] == "confirmed"
    assert rec["tx_hash"] == "0xabc123"
    assert rec["notes"] == "queued"

    # If a record reached confirmed with blank tx_hash, re-updating confirmed with a real tx_hash attaches it
    rec_id2 = payout_ledger.ledger_create("16472", "cyzcz", "20", wallet_address="RTC" + "b" * 40)
    assert payout_ledger.ledger_update_status(rec_id2, "confirmed")
    assert payout_ledger.ledger_get(rec_id2)["tx_hash"] == ""
    assert payout_ledger.ledger_update_status(rec_id2, "confirmed", tx_hash="0xdef456", notes="late hash")
    rec2 = payout_ledger.ledger_get(rec_id2)
    assert rec2["tx_hash"] == "0xdef456"
    assert rec2["notes"] == "late hash"
