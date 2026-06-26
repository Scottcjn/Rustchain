#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Regression tests for pending transaction ordering."""

import importlib
import os
import sqlite3
import sys
import threading
import types

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "node"))
if NODE_DIR not in sys.path:
    sys.path.insert(0, NODE_DIR)

mock = types.ModuleType("rustchain_crypto")


class FakeSignedTransaction:
    def __init__(
        self,
        from_addr,
        to_addr,
        amount_urtc,
        nonce,
        timestamp,
        memo,
        signature,
        public_key,
        tx_hash,
    ):
        self.from_addr = from_addr
        self.to_addr = to_addr
        self.amount_urtc = amount_urtc
        self.nonce = nonce
        self.timestamp = timestamp
        self.memo = memo
        self.signature = signature
        self.public_key = public_key
        self.tx_hash = tx_hash

    def verify(self):
        return True


mock.SignedTransaction = FakeSignedTransaction  # type: ignore[attr-defined]
mock.Ed25519Signer = object  # type: ignore[attr-defined]
mock.blake2b256_hex = lambda data: "00" * 32  # type: ignore[attr-defined]
mock.address_from_public_key = lambda data: data.hex()  # type: ignore[attr-defined]
previous_crypto = sys.modules.get("rustchain_crypto")
sys.modules["rustchain_crypto"] = mock

rustchain_tx_handler = importlib.import_module("rustchain_tx_handler")
TransactionPool = rustchain_tx_handler.TransactionPool

if previous_crypto is None:
    sys.modules.pop("rustchain_crypto", None)
else:
    sys.modules["rustchain_crypto"] = previous_crypto


def _insert_pending(conn, tx_hash, from_addr, nonce, created_at):
    conn.execute(
        """INSERT INTO pending_transactions
           (tx_hash, from_addr, to_addr, amount_urtc, nonce, timestamp,
            memo, signature, public_key, created_at, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
        (
            tx_hash,
            from_addr,
            "receiver",
            1,
            nonce,
            created_at,
            "",
            "sig",
            "00",
            created_at,
        ),
    )


def test_pending_transactions_use_fifo_order_across_wallets(tmp_path):
    pool = TransactionPool(str(tmp_path / "tx.db"))

    with sqlite3.connect(pool.db_path) as conn:
        _insert_pending(conn, "b" * 64, "wallet-a", 9, 100)
        _insert_pending(conn, "a" * 64, "wallet-b", 1, 200)

    pending = pool.get_pending_transactions()

    assert [tx.tx_hash for tx in pending] == ["b" * 64, "a" * 64]


def test_pending_transactions_preserve_insert_order_for_same_admission_time(tmp_path):
    pool = TransactionPool(str(tmp_path / "tx.db"))

    with sqlite3.connect(pool.db_path) as conn:
        _insert_pending(conn, "d" * 64, "wallet-a", 1, 100)
        _insert_pending(conn, "c" * 64, "wallet-b", 1, 100)

    pending = pool.get_pending_transactions()

    assert [tx.tx_hash for tx in pending] == ["d" * 64, "c" * 64]


def test_submit_transaction_preserves_fifo_when_clock_collides(tmp_path, monkeypatch):
    pool = TransactionPool(str(tmp_path / "tx.db"))
    monkeypatch.setattr(rustchain_tx_handler, "address_from_public_key", lambda data: data.hex())
    monkeypatch.setattr(rustchain_tx_handler.time, "time", lambda: 100)

    with sqlite3.connect(pool.db_path) as conn:
        conn.execute(
            "INSERT INTO balances (wallet, balance_urtc, wallet_nonce) VALUES (?, ?, ?)",
            ("aa", 10, 0),
        )

    first = FakeSignedTransaction(
        from_addr="aa",
        to_addr="bb",
        amount_urtc=1,
        nonce=1,
        timestamp=100,
        memo="",
        signature="sig",
        public_key="aa",
        tx_hash="z" * 64,
    )
    second = FakeSignedTransaction(
        from_addr="aa",
        to_addr="cc",
        amount_urtc=1,
        nonce=2,
        timestamp=101,
        memo="",
        signature="sig",
        public_key="aa",
        tx_hash="a" * 64,
    )

    assert pool.submit_transaction(first) == (True, "z" * 64)
    assert pool.submit_transaction(second) == (True, "a" * 64)

    pending = pool.get_pending_transactions()

    assert [tx.tx_hash for tx in pending] == ["z" * 64, "a" * 64]


def test_submit_transaction_serializes_nonce_validation_across_pool_instances(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "tx.db"
    first_pool = TransactionPool(str(db_path))
    second_pool = TransactionPool(str(db_path))

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO balances (wallet, balance_urtc, wallet_nonce) VALUES (?, ?, ?)",
            ("aa", 10, 0),
        )

    original_connect = sqlite3.connect
    pending_sum_barrier = threading.Barrier(2)

    class InstrumentedCursor:
        def __init__(self, cursor):
            self._cursor = cursor
            self._last_sql = ""

        def execute(self, sql, params=()):
            self._last_sql = " ".join(str(sql).split())
            self._cursor.execute(sql, params)
            return self

        def fetchone(self):
            row = self._cursor.fetchone()
            if "SELECT COALESCE(SUM(amount_urtc), 0) as pending" in self._last_sql:
                try:
                    pending_sum_barrier.wait(timeout=1.0)
                except threading.BrokenBarrierError:
                    pass
            return row

        def fetchall(self):
            return self._cursor.fetchall()

        def __getattr__(self, name):
            return getattr(self._cursor, name)

    class InstrumentedConnection:
        def __init__(self, conn):
            object.__setattr__(self, "_conn", conn)

        def cursor(self):
            return InstrumentedCursor(self._conn.cursor())

        def __getattr__(self, name):
            return getattr(self._conn, name)

        def __setattr__(self, name, value):
            setattr(self._conn, name, value)

    def instrumented_connect(*args, **kwargs):
        return InstrumentedConnection(original_connect(*args, **kwargs))

    monkeypatch.setattr(rustchain_tx_handler.sqlite3, "connect", instrumented_connect)
    monkeypatch.setattr(rustchain_tx_handler, "address_from_public_key", lambda data: data.hex())
    monkeypatch.setattr(
        TransactionPool,
        "register_public_key",
        lambda self, address, public_key: True,
    )

    first_tx = FakeSignedTransaction(
        from_addr="aa",
        to_addr="bb",
        amount_urtc=1,
        nonce=1,
        timestamp=100,
        memo="",
        signature="sig",
        public_key="aa",
        tx_hash="1" * 64,
    )
    second_tx = FakeSignedTransaction(
        from_addr="aa",
        to_addr="cc",
        amount_urtc=1,
        nonce=1,
        timestamp=101,
        memo="",
        signature="sig",
        public_key="aa",
        tx_hash="2" * 64,
    )

    results = []

    def submit(pool, tx):
        results.append(pool.submit_transaction(tx))

    threads = [
        threading.Thread(target=submit, args=(first_pool, first_tx)),
        threading.Thread(target=submit, args=(second_pool, second_tx)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert all(not thread.is_alive() for thread in threads)
    assert sorted(success for success, _ in results) == [False, True]

    with original_connect(db_path) as conn:
        rows = conn.execute(
            "SELECT tx_hash, from_addr, nonce FROM pending_transactions WHERE from_addr = ?",
            ("aa",),
        ).fetchall()

    assert len(rows) == 1
    assert rows[0][2] == 1


def test_legacy_pending_table_gets_created_at_migration(tmp_path):
    db_path = tmp_path / "legacy.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """CREATE TABLE balances (
               wallet TEXT PRIMARY KEY,
               balance_urtc INTEGER NOT NULL DEFAULT 0,
               wallet_nonce INTEGER DEFAULT 0
            )"""
        )
        conn.execute(
            """CREATE TABLE pending_transactions (
               tx_hash TEXT PRIMARY KEY,
               from_addr TEXT NOT NULL,
               to_addr TEXT NOT NULL,
               amount_urtc INTEGER NOT NULL,
               nonce INTEGER NOT NULL,
               timestamp INTEGER NOT NULL,
               memo TEXT DEFAULT '',
               signature TEXT NOT NULL,
               public_key TEXT NOT NULL,
               status TEXT DEFAULT 'pending'
            )"""
        )
        conn.execute(
            """INSERT INTO pending_transactions
               (tx_hash, from_addr, to_addr, amount_urtc, nonce, timestamp,
                memo, signature, public_key, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
            ("b" * 64, "wallet-a", "receiver", 1, 9, 100, "", "sig", "00"),
        )
        conn.execute(
            """INSERT INTO pending_transactions
               (tx_hash, from_addr, to_addr, amount_urtc, nonce, timestamp,
                memo, signature, public_key, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
            ("a" * 64, "wallet-b", "receiver", 1, 1, 200, "", "sig", "00"),
        )

    pool = TransactionPool(str(db_path))

    with sqlite3.connect(db_path) as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(pending_transactions)")]
        assert "created_at" in columns

    pending = pool.get_pending_transactions()

    assert [tx.tx_hash for tx in pending] == ["b" * 64, "a" * 64]
