#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Regression tests for UTXO mempool expiry cleanup."""

import json
import os
import sys
import time

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, NODE_DIR)

import utxo_db
from utxo_db import UtxoDB


def _insert_box(conn, box_id: str, value_nrtc: int = 100_000):
    conn.execute(
        """
        INSERT INTO utxo_boxes (
            box_id, value_nrtc, proposition, owner_address, creation_height,
            transaction_id, output_index, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            box_id,
            value_nrtc,
            "00",
            "RTC_TEST_OWNER",
            1,
            "ab" * 32,
            0,
            int(time.time()),
        ),
    )


def _insert_mempool_tx(conn, tx_id: str, expires_at: int, fee_nrtc: int = 0):
    conn.execute(
        """
        INSERT INTO utxo_mempool (tx_id, tx_data_json, fee_nrtc, submitted_at, expires_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (tx_id, json.dumps({"tx_id": tx_id}), fee_nrtc, int(time.time()), expires_at),
    )


def test_block_candidates_skip_and_remove_expired_transactions(tmp_path):
    db = UtxoDB(str(tmp_path / "utxo.db"))
    db.init_tables()
    now = int(time.time())

    conn = db._conn()
    try:
        _insert_mempool_tx(conn, "expired_tx", now - 1, fee_nrtc=10)
        _insert_mempool_tx(conn, "fresh_tx", now + 60, fee_nrtc=1)
        conn.execute(
            "INSERT INTO utxo_mempool_inputs (box_id, tx_id) VALUES (?, ?)",
            ("cd" * 32, "expired_tx"),
        )
        conn.commit()
    finally:
        conn.close()

    candidates = db.mempool_get_block_candidates()

    assert candidates == [{"tx_id": "fresh_tx"}]
    conn = db._conn()
    try:
        assert conn.execute("SELECT COUNT(*) FROM utxo_mempool WHERE tx_id = 'expired_tx'").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM utxo_mempool_inputs WHERE tx_id = 'expired_tx'").fetchone()[0] == 0
    finally:
        conn.close()


def test_mempool_add_sweeps_expired_rows_before_pool_size_check(tmp_path, monkeypatch):
    db = UtxoDB(str(tmp_path / "utxo.db"))
    db.init_tables()
    now = int(time.time())
    input_box_id = "ef" * 32

    conn = db._conn()
    try:
        _insert_box(conn, input_box_id)
        _insert_mempool_tx(conn, "expired_tx", now - 1)
        conn.execute(
            "INSERT INTO utxo_mempool_inputs (box_id, tx_id) VALUES (?, ?)",
            ("12" * 32, "expired_tx"),
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(utxo_db, "MAX_POOL_SIZE", 1)
    accepted = db.mempool_add(
        {
            "tx_id": "fresh_tx",
            "tx_type": "transfer",
            "inputs": [{"box_id": input_box_id, "spending_proof": "sig"}],
            "outputs": [{"value_nrtc": 99_000}],
            "fee_nrtc": 1_000,
        }
    )

    assert accepted is True
    conn = db._conn()
    try:
        rows = conn.execute("SELECT tx_id FROM utxo_mempool ORDER BY tx_id").fetchall()
        input_rows = conn.execute("SELECT tx_id FROM utxo_mempool_inputs ORDER BY tx_id").fetchall()
    finally:
        conn.close()

    assert [row["tx_id"] for row in rows] == ["fresh_tx"]
    assert [row["tx_id"] for row in input_rows] == ["fresh_tx"]
