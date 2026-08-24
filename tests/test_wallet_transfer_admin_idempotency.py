# SPDX-License-Identifier: MIT
import sqlite3
import sys
import uuid
from pathlib import Path

import pytest


integrated_node = sys.modules["integrated_node"]


def _init_wallet_transfer_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE balances (
            miner_id TEXT PRIMARY KEY,
            amount_i64 INTEGER NOT NULL
        );

        CREATE TABLE pending_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL,
            epoch INTEGER NOT NULL,
            from_miner TEXT NOT NULL,
            to_miner TEXT NOT NULL,
            amount_i64 INTEGER NOT NULL,
            reason TEXT,
            status TEXT DEFAULT 'pending',
            created_at INTEGER NOT NULL,
            confirms_at INTEGER NOT NULL,
            tx_hash TEXT,
            voided_by TEXT,
            voided_reason TEXT,
            confirmed_at INTEGER
        );

        CREATE UNIQUE INDEX idx_pending_ledger_tx_hash ON pending_ledger(tx_hash);
        """
    )
    conn.commit()
    conn.close()


@pytest.fixture
def admin_transfer_client(monkeypatch):
    tmp_dir = Path(__file__).parent / ".tmp_wallet_transfer_admin"
    tmp_dir.mkdir(exist_ok=True)
    db_path = tmp_dir / f"{uuid.uuid4().hex}.sqlite3"
    _init_wallet_transfer_db(db_path)

    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    monkeypatch.setattr(integrated_node, "current_slot", lambda: 12345)
    # The admin per-IP rate limiter (12/min) is exercised elsewhere; here it
    # would 429 the parametrized negative cases before the gate under test.
    monkeypatch.setattr(integrated_node, "ADMIN_RATE_LIMIT_MAX", 0)
    monkeypatch.setenv("RC_ADMIN_KEY", "a" * 32)

    integrated_node.app.config["TESTING"] = True
    with integrated_node.app.test_client() as test_client:
        yield test_client, db_path

    if db_path.exists():
        try:
            db_path.unlink()
        except PermissionError:
            pass


def test_admin_transfer_idempotency_key_reuses_pending_transfer(admin_transfer_client):
    client, db_path = admin_transfer_client

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            ("founder_community", 3_000_000),
        )
        conn.commit()

    payload = {
        "from_miner": "founder_community",
        "to_miner": "contributor",
        "amount_rtc": 1.0,
        "reason": "bounty:123:test-payment:2026-08-22",
        "idempotency_key": "owner-repo-123-payment",
    }

    first = client.post("/wallet/transfer", json=payload, headers={"X-Admin-Key": "a" * 32})
    assert first.status_code == 200
    first_body = first.get_json()
    assert first_body["ok"] is True

    retry = client.post("/wallet/transfer", json=payload, headers={"X-Admin-Key": "a" * 32})
    assert retry.status_code == 200
    retry_body = retry.get_json()
    assert retry_body["ok"] is True

    assert retry_body["pending_id"] == first_body["pending_id"]
    assert retry_body["tx_hash"] == first_body["tx_hash"]

    with sqlite3.connect(db_path) as conn:
        pending_count, pending_total = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount_i64), 0) FROM pending_ledger"
        ).fetchone()

    assert pending_count == 1
    assert pending_total == 1_000_000


def test_admin_transfer_uses_preflight_amount_i64_without_float_loss(admin_transfer_client):
    client, db_path = admin_transfer_client

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            ("founder_community", 1_000_000),
        )
        conn.commit()

    response = client.post(
        "/wallet/transfer",
        json={
            "from_miner": "founder_community",
            "to_miner": "contributor",
            "amount_rtc": "0.000249",
            "reason": "test:float-loss",
            "idempotency_key": "test-float-loss",
        },
        headers={"X-Admin-Key": "a" * 32},
    )
    assert response.status_code == 200

    with sqlite3.connect(db_path) as conn:
        (pending_amount,) = conn.execute(
            "SELECT amount_i64 FROM pending_ledger"
        ).fetchone()

    assert pending_amount == 249


def test_admin_transfer_idempotency_key_rejects_changed_transfer(admin_transfer_client):
    client, db_path = admin_transfer_client

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            ("founder_community", 3_000_000),
        )
        conn.commit()

    payload = {
        "from_miner": "founder_community",
        "to_miner": "contributor",
        "amount_rtc": 1.0,
        "reason": "bounty:123:test-payment:2026-08-22",
        "idempotency_key": "owner-repo-123-payment",
    }

    first = client.post("/wallet/transfer", json=payload, headers={"X-Admin-Key": "a" * 32})
    assert first.status_code == 200

    changed = dict(payload)
    changed["amount_rtc"] = 2.0
    conflict = client.post("/wallet/transfer", json=changed, headers={"X-Admin-Key": "a" * 32})
    assert conflict.status_code == 409
    assert conflict.get_json()["error"] == "idempotency_key_conflict"

    with sqlite3.connect(db_path) as conn:
        pending_count, pending_total = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount_i64), 0) FROM pending_ledger"
        ).fetchone()

    assert pending_count == 1
    assert pending_total == 1_000_000


def _fund(db_path, amount_i64=3_000_000):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            ("founder_community", amount_i64),
        )
        conn.commit()


def _pending_count(db_path):
    with sqlite3.connect(db_path) as conn:
        return conn.execute("SELECT COUNT(*) FROM pending_ledger").fetchone()[0]


_BASE = {"from_miner": "founder_community", "to_miner": "contributor", "amount_rtc": 1.0}
_HDR = {"X-Admin-Key": "a" * 32}


@pytest.mark.parametrize(
    "key_field, expected_error",
    [
        pytest.param({}, "idempotency_key_required", id="missing"),
        pytest.param({"idempotency_key": None}, "idempotency_key_required", id="null"),
        pytest.param({"idempotency_key": ""}, "idempotency_key_required", id="empty"),
        pytest.param({"idempotency_key": "   "}, "invalid_idempotency_key", id="whitespace-only"),
        pytest.param({"idempotency_key": 123}, "invalid_idempotency_key", id="non-string"),
        pytest.param({"idempotency_key": "bad key!"}, "invalid_idempotency_key", id="bad-charset"),
        pytest.param({"idempotency_key": "bounty:<number>:<slug>:<date>"}, "invalid_idempotency_key", id="angle-brackets"),
        pytest.param({"idempotency_key": "k" * 129}, "invalid_idempotency_key", id="too-long"),
    ],
)
def test_admin_transfer_requires_well_formed_idempotency_key(admin_transfer_client, key_field, expected_error):
    """Phase-2 hardening: a keyless admin transfer can double-pay on retry, so it is
    rejected before any pending row is written. Missing/empty -> required;
    present-but-malformed -> invalid (the two are distinct so monitors can classify)."""
    client, db_path = admin_transfer_client
    _fund(db_path)

    payload = {**_BASE, "reason": "bounty:1:negative-test:2026-08-22", **key_field}
    response = client.post("/wallet/transfer", json=payload, headers=_HDR)

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == expected_error
    if expected_error == "idempotency_key_required":
        # The hint must itself be a VALID key example (a copy-pasted hint
        # that the regex rejects is a trap).
        import re
        example = body["hint"].split("e.g. ", 1)[1].split(".")[0].rstrip(".")
        assert re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", example), example
    assert _pending_count(db_path) == 0


def test_admin_transfer_requires_reason_but_accepts_memo_fallback(admin_transfer_client):
    """Phase-1 hardening: attribution is mandatory; `memo` is accepted as the
    legacy field name so existing payers keep working."""
    client, db_path = admin_transfer_client
    _fund(db_path)

    no_reason = client.post(
        "/wallet/transfer", json={**_BASE, "idempotency_key": "no-reason"}, headers=_HDR
    )
    assert no_reason.status_code == 400
    assert no_reason.get_json()["error"] == "reason_required"

    too_long = client.post(
        "/wallet/transfer",
        json={**_BASE, "idempotency_key": "too-long", "reason": "x" * 501},
        headers=_HDR,
    )
    assert too_long.status_code == 400
    assert too_long.get_json()["error"] == "reason_too_long"

    memo_only = client.post(
        "/wallet/transfer",
        json={**_BASE, "idempotency_key": "memo-only", "memo": "legacy memo attribution"},
        headers=_HDR,
    )
    assert memo_only.status_code == 200
    assert memo_only.get_json()["ok"] is True

    with sqlite3.connect(db_path) as conn:
        (stored_reason,) = conn.execute("SELECT reason FROM pending_ledger").fetchone()
    assert stored_reason == "legacy memo attribution"
    assert _pending_count(db_path) == 1


def test_admin_transfer_replay_ignores_reason_but_refuses_voided(admin_transfer_client):
    """Replay semantics (live on prod since 2026-08-20): the money-relevant
    triple (from, to, amount) decides conflict — a changed `reason` on a
    replay is NOT a conflict (legacy rows carry "admin_transfer"). But a
    replay of a VOIDED row must not come back `ok: true`."""
    import hashlib

    client, db_path = admin_transfer_client
    _fund(db_path)

    payload = {**_BASE, "reason": "bounty:9:first:2026-08-22", "idempotency_key": "replay-semantics"}
    first = client.post("/wallet/transfer", json=payload, headers=_HDR)
    assert first.status_code == 200
    pending_id = first.get_json()["pending_id"]

    # Same key, same triple, different reason -> same row, no conflict.
    replay = client.post(
        "/wallet/transfer", json={**payload, "reason": "bounty:9:retry-wording:2026-08-22"}, headers=_HDR
    )
    assert replay.status_code == 200
    assert replay.get_json()["pending_id"] == pending_id
    assert _pending_count(db_path) == 1

    # Void the row out-of-band (admin void path), then replay the key.
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE pending_ledger SET status = 'voided' WHERE id = ?", (pending_id,))
        conn.commit()

    voided = client.post("/wallet/transfer", json=payload, headers=_HDR)
    assert voided.status_code == 409
    body = voided.get_json()
    assert body["ok"] is False
    assert body["error"] == "idempotency_key_voided"
    assert body["tx_hash"] == hashlib.sha256(b"wallet_transfer_idempotency:replay-semantics").hexdigest()[:32]
    assert _pending_count(db_path) == 1  # nothing re-issued
