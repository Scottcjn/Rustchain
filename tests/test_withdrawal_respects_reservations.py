# SPDX-License-Identifier: MIT
"""Integration: a withdrawal must not drain funds reserved by a pending transfer.

The withdrawal balance check runs BEFORE signature verification, so we can prove
the available-balance gate rejects without needing a valid signature.
"""
import sqlite3
import sys
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
NODE = REPO_ROOT / "node"
sys.path.insert(0, str(NODE))

# The big node module is imported as "integrated_node" by the existing suite.
import importlib.util  # noqa: E402

if "integrated_node" not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        "integrated_node", NODE / "rustchain_v2_integrated_v2.2.1_rip200.py"
    )
    integrated_node = importlib.util.module_from_spec(spec)
    sys.modules["integrated_node"] = integrated_node
    spec.loader.exec_module(integrated_node)
else:
    integrated_node = sys.modules["integrated_node"]


def _init_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER NOT NULL);
        CREATE TABLE pending_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, epoch INTEGER,
            from_miner TEXT NOT NULL, to_miner TEXT NOT NULL, amount_i64 INTEGER NOT NULL,
            reason TEXT, status TEXT DEFAULT 'pending', created_at INTEGER,
            confirms_at INTEGER, tx_hash TEXT, voided_by TEXT, voided_reason TEXT,
            confirmed_at INTEGER
        );
        CREATE TABLE withdrawal_nonces (miner_pk TEXT, nonce TEXT, used_at INTEGER);
        CREATE TABLE withdrawal_limits (miner_pk TEXT, date TEXT, total_withdrawn REAL);
        CREATE TABLE miner_keys (miner_pk TEXT PRIMARY KEY, pubkey_sr25519 TEXT);
        CREATE TABLE bridge_transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT, direction TEXT, source_address TEXT,
            amount_i64 INTEGER, status TEXT, source_debited INTEGER DEFAULT 0
        );
        """
    )
    conn.commit()
    conn.close()


@pytest.fixture
def client(monkeypatch, tmp_path):
    db_path = tmp_path / "withdraw_reservation.sqlite3"
    _init_db(db_path)
    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    monkeypatch.setattr(integrated_node, "current_slot", lambda: 12345)
    integrated_node.app.config["TESTING"] = True
    with integrated_node.app.test_client() as c:
        yield c, db_path


WALLET = "RTC0123456789abcdef0123456789abcdef01234567"


def _fund(db_path, amount_i64):
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)", (WALLET, amount_i64))
    conn.commit()
    conn.close()


def _reserve_pending(db_path, amount_i64):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO pending_ledger (ts, epoch, from_miner, to_miner, amount_i64, status, "
        "created_at, confirms_at, tx_hash) VALUES (0,0,?,?,?, 'pending', 0, 0, ?)",
        (WALLET, "someone", amount_i64, "txh_" + uuid.uuid4().hex),
    )
    conn.commit()
    conn.close()


def test_withdrawal_blocked_by_pending_reservation(client):
    c, db_path = client
    _fund(db_path, 100 * 1_000_000)         # 100 RTC on the ledger
    _reserve_pending(db_path, 90 * 1_000_000)  # 90 RTC reserved by a pending transfer

    # Try to withdraw 50 RTC — raw balance is 100, but available is only 10.
    # Signature is junk on purpose: the available-balance gate runs first.
    resp = c.post("/withdraw/request", json={
        "miner_pk": WALLET, "destination": "RTCdestination", "amount": 50,
        "nonce": "n1", "signature": "deadbeef",
    })
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["error"] == "Insufficient balance"
    # available reflects the reservation: 100 - 90 = 10 RTC, well under 50.
    assert body["available"] == pytest.approx(10.0)


def test_withdrawal_blocked_by_undebited_bridge_deposit(client):
    c, db_path = client
    _fund(db_path, 100 * 1_000_000)
    # A bridge deposit not yet hard-debited reserves 90 RTC.
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO bridge_transfers (direction, source_address, amount_i64, status, source_debited) "
        "VALUES ('deposit', ?, ?, 'locked', 0)", (WALLET, 90 * 1_000_000))
    conn.commit()
    conn.close()

    resp = c.post("/withdraw/request", json={
        "miner_pk": WALLET, "destination": "RTCdestination", "amount": 50,
        "nonce": "nb", "signature": "deadbeef",
    })
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Insufficient balance"
    assert resp.get_json()["available"] == pytest.approx(10.0)


def test_withdrawal_allowed_when_unreserved(client):
    c, db_path = client
    _fund(db_path, 100 * 1_000_000)  # no pending reservation

    # 50 RTC is available; the available-balance gate passes, so the request
    # proceeds PAST it and is rejected LATER for an unregistered signing key.
    # That later 404 proves the balance gate did not block.
    resp = c.post("/withdraw/request", json={
        "miner_pk": WALLET, "destination": "RTCdestination", "amount": 50,
        "nonce": "n2", "signature": "deadbeef",
    })
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "Miner not registered"
