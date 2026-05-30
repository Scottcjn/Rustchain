# SPDX-License-Identifier: MIT
"""Regression tests for state-transition audit events."""

import json
import sqlite3
import sys


integrated_node = sys.modules["integrated_node"]


def test_record_state_transition_event_creates_queryable_audit_row(tmp_path):
    db_path = tmp_path / "state-events.sqlite3"

    with sqlite3.connect(db_path) as conn:
        integrated_node.record_state_transition_event(
            conn,
            "epoch_finalized",
            "epoch",
            "7",
            epoch=7,
            actor="settler",
            details={"miner_count": 2, "total_weight_units": 3000},
            ts=12345,
        )
        row = conn.execute(
            """
            SELECT ts, event_type, entity_type, entity_id, epoch, actor, details_json
            FROM state_transition_events
            """
        ).fetchone()

    assert row[:6] == (12345, "epoch_finalized", "epoch", "7", 7, "settler")
    assert json.loads(row[6]) == {"miner_count": 2, "total_weight_units": 3000}


def test_record_attestation_success_writes_miner_audit_event(monkeypatch, tmp_path):
    db_path = tmp_path / "attestation-events.sqlite3"
    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    integrated_node.app.config["DB_PATH"] = str(db_path)
    integrated_node.init_db()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS miner_attest_recent (
                miner TEXT PRIMARY KEY,
                ts_ok INTEGER NOT NULL,
                device_family TEXT,
                device_arch TEXT,
                entropy_score REAL DEFAULT 0.0,
                fingerprint_passed INTEGER DEFAULT 0,
                source_ip TEXT,
                signing_pubkey TEXT,
                fingerprint_checks_json TEXT DEFAULT '{}'
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS miner_attest_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                miner TEXT NOT NULL,
                ts_ok INTEGER NOT NULL,
                device_family TEXT,
                device_arch TEXT,
                entropy_score REAL DEFAULT 0.0,
                fingerprint_passed INTEGER DEFAULT 0,
                fingerprint_checks_json TEXT DEFAULT '{}'
            )
            """
        )

    integrated_node.record_attestation_success(
        "miner-audit-1",
        {"family": "x86", "arch": "default"},
        fingerprint_passed=True,
        source_ip="127.0.0.1",
        fingerprint={"checks": {"clock_drift": {"passed": True}}},
        entropy_score=0.9,
    )

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT event_type, entity_type, entity_id, actor, details_json
            FROM state_transition_events
            WHERE event_type = 'miner_attestation_success'
            """
        ).fetchone()

    assert row[:4] == (
        "miner_attestation_success",
        "miner",
        "miner-audit-1",
        "miner-audit-1",
    )
    details = json.loads(row[4])
    assert details["fingerprint_passed"] is True
    assert details["source_ip_present"] is True
