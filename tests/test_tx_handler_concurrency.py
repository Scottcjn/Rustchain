#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Regression tests for concurrent transaction-pool submissions.
"""

import sqlite3
import threading
import time

import pytest

from node import rustchain_tx_handler as tx_handler
from tests import mock_crypto


def _seed_balance(db_path, address, amount=1_000):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO balances (wallet, balance_urtc, wallet_nonce) VALUES (?, ?, ?)",
            (address, amount, 0),
        )


def _tx(from_addr, to_addr, public_key, amount, nonce, tx_hash):
    return mock_crypto.SignedTransaction(
        from_addr=from_addr,
        to_addr=to_addr,
        amount_urtc=amount,
        nonce=nonce,
        timestamp=int(time.time()),
        public_key=public_key,
        tx_hash=tx_hash,
    )


def test_concurrent_submit_serializes_pending_nonce_validation(tmp_path, monkeypatch):
    db_path = tmp_path / "tx.db"
    pool_a = tx_handler.TransactionPool(str(db_path))
    pool_b = tx_handler.TransactionPool(str(db_path))

    sender, public_key, _ = mock_crypto.generate_wallet_keypair()
    receiver, _, _ = mock_crypto.generate_wallet_keypair()
    _seed_balance(db_path, sender)

    real_connect = tx_handler.sqlite3.connect
    select_calls = 0
    select_calls_lock = threading.Lock()

    class RacingCursor(sqlite3.Cursor):
        def execute(self, sql, parameters=()):
            nonlocal select_calls
            result = super().execute(sql, parameters)
            if (
                "SELECT nonce FROM pending_transactions" in " ".join(sql.split())
                and parameters == (sender,)
            ):
                with select_calls_lock:
                    select_calls += 1
                    call_number = select_calls
                if call_number == 1:
                    time.sleep(0.25)
            return result

    class RacingConnection(sqlite3.Connection):
        def cursor(self, *args, **kwargs):
            kwargs.setdefault("factory", RacingCursor)
            return super().cursor(*args, **kwargs)

    def connect_with_racing_cursor(*args, **kwargs):
        kwargs["factory"] = RacingConnection
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(tx_handler.sqlite3, "connect", connect_with_racing_cursor)

    tx_a = _tx(sender, receiver, public_key, 100, 1, "tx-concurrent-a")
    tx_b = _tx(sender, receiver, public_key, 100, 1, "tx-concurrent-b")
    results = []

    def submit(pool, tx):
        results.append(pool.submit_transaction(tx))

    threads = [
        threading.Thread(target=submit, args=(pool_a, tx_a)),
        threading.Thread(target=submit, args=(pool_b, tx_b)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    accepted = [success for success, _ in results if success]
    rejected = [reason for success, reason in results if not success]
    assert len(accepted) == 1
    assert len(rejected) == 1
    assert "Invalid nonce" in rejected[0]

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT from_addr, nonce FROM pending_transactions WHERE status = 'pending'"
        ).fetchall()
    assert rows == [(sender, 1)]


def test_pending_wallet_nonce_unique_index_blocks_direct_duplicates(tmp_path):
    db_path = tmp_path / "tx.db"
    tx_handler.TransactionPool(str(db_path))

    row = (
        "tx-a",
        "sender",
        "receiver",
        100,
        1,
        123,
        "",
        "sig",
        "00",
        123,
    )
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """INSERT INTO pending_transactions
               (tx_hash, from_addr, to_addr, amount_urtc, nonce,
                timestamp, memo, signature, public_key, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            row,
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO pending_transactions
                   (tx_hash, from_addr, to_addr, amount_urtc, nonce,
                    timestamp, memo, signature, public_key, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("tx-b", *row[1:]),
            )
