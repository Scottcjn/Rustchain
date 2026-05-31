#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Regression tests for pending transaction ordering."""

import importlib
import os
import sqlite3
import sys
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


mock.SignedTransaction = FakeSignedTransaction  # type: ignore[attr-defined]
mock.Ed25519Signer = object  # type: ignore[attr-defined]
mock.blake2b256_hex = lambda data: "00" * 32  # type: ignore[attr-defined]
mock.address_from_public_key = lambda data: "addr-from-pub"  # type: ignore[attr-defined]
previous_crypto = sys.modules.get("rustchain_crypto")
sys.modules["rustchain_crypto"] = mock

TransactionPool = importlib.import_module("rustchain_tx_handler").TransactionPool

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


def test_pending_transactions_use_hash_tiebreaker_for_same_admission_time(tmp_path):
    pool = TransactionPool(str(tmp_path / "tx.db"))

    with sqlite3.connect(pool.db_path) as conn:
        _insert_pending(conn, "d" * 64, "wallet-a", 1, 100)
        _insert_pending(conn, "c" * 64, "wallet-b", 1, 100)

    pending = pool.get_pending_transactions()

    assert [tx.tx_hash for tx in pending] == ["c" * 64, "d" * 64]
