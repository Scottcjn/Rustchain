# SPDX-License-Identifier: MIT
"""Regression tests for transfer metadata in ``GET /wallet/history``."""

import sqlite3
import sys
from contextlib import closing

import pytest

integrated_node = sys.modules["integrated_node"]

WALLET = "RTC" + "a" * 40
SENDER = "RTC" + "b" * 40
RECIPIENT = "RTC" + "c" * 40


def _init_db(db_path, *, pending_ledger=True):
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute(
            """
            CREATE TABLE ledger (
                ts INTEGER, epoch INTEGER, miner_id TEXT,
                delta_i64 INTEGER, reason TEXT
            )
            """
        )
        if pending_ledger:
            conn.execute(
                """
                CREATE TABLE pending_ledger (
                    id INTEGER PRIMARY KEY, ts INTEGER, epoch INTEGER,
                    from_miner TEXT, to_miner TEXT, amount_i64 INTEGER,
                    reason TEXT, status TEXT, voided_by TEXT,
                    voided_reason TEXT, created_at INTEGER,
                    confirms_at INTEGER, confirmed_at INTEGER, tx_hash TEXT
                )
                """
            )


def _insert_ledger(db_path, *, ts, delta, reason, epoch=7):
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute(
            "INSERT INTO ledger VALUES (?, ?, ?, ?, ?)",
            (ts, epoch, WALLET, delta, reason),
        )
        conn.commit()


def _insert_pending(db_path, *, tx_hash, memo, status="confirmed"):
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO pending_ledger
                (ts, epoch, from_miner, to_miner, amount_i64, reason,
                 status, created_at, tx_hash)
            VALUES (1, 7, ?, ?, 1000000, ?, ?, 1, ?)
            """,
            (SENDER, RECIPIENT, memo, status, tx_hash),
        )
        conn.commit()


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "wallet_history.sqlite3"
    _init_db(db_path)
    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    integrated_node.app.config["TESTING"] = True
    with integrated_node.app.test_client() as test_client:
        test_client.db_path = db_path
        yield test_client


def test_transfer_in_and_out_include_memo_and_status(client):
    _insert_ledger(
        client.db_path,
        ts=20,
        delta=1_000_000,
        reason=f"transfer_in:{SENDER}:tx-in",
    )
    _insert_ledger(
        client.db_path,
        ts=10,
        delta=-2_000_000,
        reason=f"transfer_out:{RECIPIENT}:tx-out",
    )
    _insert_pending(client.db_path, tx_hash="tx-in", memo="incoming memo")
    _insert_pending(client.db_path, tx_hash="tx-out", memo="outgoing memo")

    response = client.get(f"/wallet/history?miner_id={WALLET}")

    assert response.status_code == 200
    transfers = {row["tx_hash"]: row for row in response.get_json()["transactions"]}
    assert transfers["tx-in"]["memo"] == "incoming memo"
    assert transfers["tx-in"]["status"] == "confirmed"
    assert transfers["tx-in"]["from"] == SENDER
    assert transfers["tx-out"]["memo"] == "outgoing memo"
    assert transfers["tx-out"]["status"] == "confirmed"
    assert transfers["tx-out"]["to"] == RECIPIENT


def test_transfer_metadata_uses_one_batched_query(client, monkeypatch):
    for index in range(3):
        tx_hash = f"tx-{index}"
        _insert_ledger(
            client.db_path,
            ts=30 - index,
            delta=1_000_000,
            reason=f"transfer_in:{SENDER}:{tx_hash}",
        )
        _insert_pending(client.db_path, tx_hash=tx_hash, memo=f"memo {index}")

    real_connect = sqlite3.connect
    metadata_queries = []

    class CountingConnection:
        def __init__(self, connection):
            self.connection = connection

        def __enter__(self):
            self.connection.__enter__()
            return self

        def __exit__(self, *args):
            return self.connection.__exit__(*args)

        def execute(self, sql, parameters=()):
            normalized = " ".join(sql.split()).lower()
            if "from pending_ledger" in normalized and "tx_hash in" in normalized:
                metadata_queries.append((normalized, tuple(parameters)))
            return self.connection.execute(sql, parameters)

    monkeypatch.setattr(
        integrated_node.sqlite3,
        "connect",
        lambda *args, **kwargs: CountingConnection(real_connect(*args, **kwargs)),
    )

    response = client.get(f"/wallet/history?miner_id={WALLET}")

    assert response.status_code == 200
    assert len(metadata_queries) == 1
    assert metadata_queries[0][1] == ("tx-0", "tx-1", "tx-2")


def test_memo_strips_control_characters_then_truncates(client):
    raw_memo = "start\x00\n\t\x7f" + "x" * 210
    _insert_ledger(
        client.db_path,
        ts=10,
        delta=1_000_000,
        reason=f"transfer_in:{SENDER}:tx-clean",
    )
    _insert_pending(client.db_path, tx_hash="tx-clean", memo=raw_memo)

    row = client.get(
        f"/wallet/history?miner_id={WALLET}"
    ).get_json()["transactions"][0]

    assert row["memo"] == ("start" + "x" * 210)[:200]
    assert len(row["memo"]) == 200


def test_missing_pending_ledger_returns_null_metadata(tmp_path, monkeypatch):
    db_path = tmp_path / "without_pending.sqlite3"
    _init_db(db_path, pending_ledger=False)
    _insert_ledger(
        db_path,
        ts=10,
        delta=-1_000_000,
        reason=f"transfer_out:{RECIPIENT}:tx-missing",
    )
    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))

    response = integrated_node.app.test_client().get(
        f"/wallet/history?miner_id={WALLET}"
    )

    assert response.status_code == 200
    row = response.get_json()["transactions"][0]
    assert row["memo"] is None
    assert row["status"] is None


def test_non_transfer_ledger_response_is_unchanged(client):
    _insert_ledger(
        client.db_path,
        ts=123,
        delta=4_500_000,
        epoch=9,
        reason="manual_adjustment",
    )

    body = client.get(f"/wallet/history?miner_id={WALLET}").get_json()

    assert body == {
        "ok": True,
        "miner_id": WALLET,
        "total": 1,
        "transactions": [{
            "type": "ledger",
            "amount": 4.5,
            "epoch": 9,
            "timestamp": 123,
            "tx_hash": None,
            "reason": "manual_adjustment",
        }],
    }
