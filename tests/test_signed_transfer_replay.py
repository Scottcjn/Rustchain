import sqlite3
import sys
import uuid
import json
from pathlib import Path

import pytest


SDK_PATH = Path(__file__).resolve().parents[1] / "sdk" / "python"
if str(SDK_PATH) not in sys.path:
    sys.path.insert(0, str(SDK_PATH))

integrated_node = sys.modules["integrated_node"]


def _init_signed_transfer_db(db_path: Path) -> None:
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

        CREATE TABLE transfer_nonces (
            from_address TEXT NOT NULL,
            nonce TEXT NOT NULL,
            used_at INTEGER NOT NULL,
            PRIMARY KEY (from_address, nonce)
        );

        CREATE UNIQUE INDEX idx_pending_ledger_tx_hash ON pending_ledger(tx_hash);
        """
    )
    conn.commit()
    conn.close()


@pytest.fixture
def signed_transfer_client(monkeypatch):
    local_tmp_dir = Path(__file__).parent / ".tmp_signed_transfer"
    local_tmp_dir.mkdir(exist_ok=True)
    db_path = local_tmp_dir / f"{uuid.uuid4().hex}.sqlite3"
    _init_signed_transfer_db(db_path)

    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    monkeypatch.setattr(integrated_node, "current_slot", lambda: 12345)
    monkeypatch.setattr(integrated_node, "verify_rtc_signature", lambda public_key, message, signature: True)
    monkeypatch.setattr(integrated_node, "address_from_pubkey", lambda public_key: "RTC" + "a" * 40)

    integrated_node.app.config["TESTING"] = True
    with integrated_node.app.test_client() as test_client:
        yield test_client, db_path

    if db_path.exists():
        try:
            db_path.unlink()
        except PermissionError:
            pass


def _payload(amount_rtc: float = 1.5, nonce: int = 1733420000000) -> dict:
    return {
        "from_address": "RTC" + "a" * 40,
        "to_address": "RTC" + "b" * 40,
        "amount_rtc": amount_rtc,
        "nonce": nonce,
        "signature": "11" * 64,
        "public_key": "22" * 32,
        "memo": "test replay protection",
    }


def test_signed_transfer_rejects_duplicate_nonce(signed_transfer_client):
    client, db_path = signed_transfer_client

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            ("RTC" + "a" * 40, 10_000_000),
        )
        conn.commit()

    first = client.post("/wallet/transfer/signed", json=_payload())
    assert first.status_code == 200
    assert first.get_json()["replay_protected"] is True

    second = client.post("/wallet/transfer/signed", json=_payload())
    assert second.status_code == 400
    body = second.get_json()
    assert body["code"] == "REPLAY_DETECTED"
    assert "Nonce already used" in body["error"]

    with sqlite3.connect(db_path) as conn:
        nonce_count = conn.execute("SELECT COUNT(*) FROM transfer_nonces").fetchone()[0]
        pending_count = conn.execute("SELECT COUNT(*) FROM pending_ledger").fetchone()[0]

    assert nonce_count == 1
    assert pending_count == 1


def test_insufficient_balance_does_not_burn_nonce(signed_transfer_client):
    client, db_path = signed_transfer_client
    payload = _payload(amount_rtc=5.0, nonce=1733420009999)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            ("RTC" + "a" * 40, 1_000_000),
        )
        conn.commit()

    rejected = client.post("/wallet/transfer/signed", json=payload)
    assert rejected.status_code == 400
    assert rejected.get_json()["error"] == "Insufficient available balance"

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE balances SET amount_i64 = ? WHERE miner_id = ?",
            (10_000_000, "RTC" + "a" * 40),
        )
        conn.commit()

    accepted = client.post("/wallet/transfer/signed", json=payload)
    assert accepted.status_code == 200
    assert accepted.get_json()["ok"] is True

    with sqlite3.connect(db_path) as conn:
        nonce_count = conn.execute("SELECT COUNT(*) FROM transfer_nonces").fetchone()[0]
        pending_count = conn.execute("SELECT COUNT(*) FROM pending_ledger").fetchone()[0]

    assert nonce_count == 1
    assert pending_count == 1


def test_signed_transfer_accepts_sdk_fee_signed_message(signed_transfer_client, monkeypatch):
    client, db_path = signed_transfer_client
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from rustchain_sdk.wallet import RustChainWallet

    wallet = RustChainWallet.create(strength=128)
    transfer = wallet.sign_transfer(
        "RTC" + "b" * 40,
        1.5,
        fee=0.25,
        memo="fee-bound",
        nonce=1733420001234,
    )
    payload = {
        "from_address": transfer["from_address"],
        "to_address": transfer["to_address"],
        "amount_rtc": transfer["amount_rtc"],
        "fee_rtc": transfer["fee_rtc"],
        "nonce": transfer["nonce"],
        "signature": transfer["signature"],
        "public_key": transfer["public_key"],
        "memo": transfer["memo"],
    }
    captured = {}

    def verify_signature(public_key, message, signature):
        captured.setdefault("messages", []).append(message)
        try:
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key)).verify(
                bytes.fromhex(signature),
                message,
            )
            return True
        except Exception:
            return False

    monkeypatch.setattr(integrated_node, "verify_rtc_signature", verify_signature)
    monkeypatch.setattr(integrated_node, "address_from_pubkey", lambda public_key: wallet.address)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            (wallet.address, 10_000_000),
        )
        conn.commit()

    response = client.post("/wallet/transfer/signed", json=payload)

    expected_message = json.dumps(
        {
            "amount": 1.5,
            "fee": 0.25,
            "from": wallet.address,
            "memo": "fee-bound",
            "nonce": "1733420001234",
            "to": "RTC" + "b" * 40,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    assert captured["messages"][0] == expected_message
    assert response.status_code == 200
    assert response.get_json()["ok"] is True


def test_signed_transfer_keeps_legacy_zero_fee_signature_compatible(
    signed_transfer_client,
    monkeypatch,
):
    client, db_path = signed_transfer_client
    seen_messages = []

    def verify_legacy_only(public_key, message, signature):
        body = json.loads(message)
        seen_messages.append(body)
        return "fee" not in body

    monkeypatch.setattr(integrated_node, "verify_rtc_signature", verify_legacy_only)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            ("RTC" + "a" * 40, 10_000_000),
        )
        conn.commit()

    response = client.post("/wallet/transfer/signed", json=_payload(nonce=1733420004444))

    assert response.status_code == 200
    assert "fee" in seen_messages[0]
    assert "fee" not in seen_messages[1]
