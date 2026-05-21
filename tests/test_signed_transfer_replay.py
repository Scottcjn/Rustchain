import sqlite3
import sys
import time
import uuid
import json
from contextlib import closing
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


def _init_legacy_pending_confirm_db(
    db_path: Path,
    ledger_sql: str | None = None,
) -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE balances (
            miner_pk TEXT PRIMARY KEY,
            balance_rtc REAL DEFAULT 0
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
    if ledger_sql:
        conn.execute(ledger_sql)
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


def test_signed_transfer_uses_preflight_amount_i64_without_float_loss(signed_transfer_client):
    client, db_path = signed_transfer_client

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
            ("RTC" + "a" * 40, 1_000_000),
        )
        conn.commit()

    response = client.post(
        "/wallet/transfer/signed",
        json=_payload(amount_rtc="0.000249", nonce=1733420011111),
    )
    assert response.status_code == 200

    with sqlite3.connect(db_path) as conn:
        (pending_amount,) = conn.execute(
            "SELECT amount_i64 FROM pending_ledger"
        ).fetchone()

    assert pending_amount == 249


def test_signed_transfer_rejects_nonzero_fee_until_fee_settlement(
    signed_transfer_client,
    monkeypatch,
):
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
    assert response.status_code == 400
    assert response.get_json()["code"] == "SIGNED_TRANSFER_FEE_UNSETTLED"

    with sqlite3.connect(db_path) as conn:
        nonce_count = conn.execute("SELECT COUNT(*) FROM transfer_nonces").fetchone()[0]
        pending_count = conn.execute("SELECT COUNT(*) FROM pending_ledger").fetchone()[0]

    assert nonce_count == 0
    assert pending_count == 0


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


def test_pending_confirm_updates_fresh_init_db_legacy_balances(monkeypatch):
    local_tmp_dir = Path(__file__).parent / ".tmp_signed_transfer"
    local_tmp_dir.mkdir(exist_ok=True)
    db_path = local_tmp_dir / f"{uuid.uuid4().hex}.sqlite3"

    admin_key = "test-admin-key"
    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    monkeypatch.setattr(integrated_node, "send_sophiacheck_alert", lambda *args, **kwargs: None)
    monkeypatch.setenv("RC_ADMIN_KEY", admin_key)
    integrated_node.app.config["TESTING"] = True
    integrated_node.app.config["DB_PATH"] = str(db_path)
    integrated_node.init_db()

    from_wallet = "RTC" + "a" * 40
    to_wallet = "RTC" + "b" * 40
    amount_i64 = 1_250_000
    now = int(time.time())

    with closing(sqlite3.connect(db_path)) as conn:
        balance_cols = {row[1] for row in conn.execute("PRAGMA table_info(balances)")}
        ledger_cols = {row[1] for row in conn.execute("PRAGMA table_info(ledger)")}
        assert {"miner_pk", "balance_rtc"}.issubset(balance_cols)
        assert "amount_i64" not in balance_cols
        assert {"ts", "epoch", "miner_id", "delta_i64", "reason"}.issubset(ledger_cols)
        conn.execute(
            "INSERT INTO balances (miner_pk, balance_rtc) VALUES (?, ?)",
            (from_wallet, 2.0),
        )
        conn.execute(
            """
            INSERT INTO pending_ledger
                (ts, epoch, from_miner, to_miner, amount_i64, reason, created_at, confirms_at, tx_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now - 10,
                7,
                from_wallet,
                to_wallet,
                amount_i64,
                "signed_wallet_transfer:legacy",
                now - 10,
                now - 1,
                "legacy-confirm-tx",
            ),
        )
        conn.commit()

    with integrated_node.app.test_client() as client:
        response = client.post("/pending/confirm", headers={"X-Admin-Key": admin_key})

    assert response.status_code == 200
    body = response.get_json()
    assert body["confirmed_count"] == 1
    assert body["confirmed_ids"] == [1]
    assert body["errors"] is None

    with closing(sqlite3.connect(db_path)) as conn:
        balances = dict(conn.execute("SELECT miner_pk, balance_rtc FROM balances").fetchall())
        (status, confirmed_at) = conn.execute(
            "SELECT status, confirmed_at FROM pending_ledger WHERE id = 1"
        ).fetchone()
        ledger_rows = conn.execute(
            "SELECT miner_id, delta_i64, reason FROM ledger ORDER BY id"
        ).fetchall()

    assert balances[from_wallet] == pytest.approx(0.75)
    assert balances[to_wallet] == pytest.approx(1.25)
    assert status == "confirmed"
    assert confirmed_at is not None
    assert ledger_rows == [
        (from_wallet, -amount_i64, f"transfer_out:{to_wallet}:legacy-confirm-tx"),
        (to_wallet, amount_i64, f"transfer_in:{from_wallet}:legacy-confirm-tx"),
    ]

    if db_path.exists():
        db_path.unlink()


def test_pending_confirm_rolls_back_balance_changes_when_ledger_write_fails(monkeypatch):
    local_tmp_dir = Path(__file__).parent / ".tmp_signed_transfer"
    local_tmp_dir.mkdir(exist_ok=True)
    db_path = local_tmp_dir / f"{uuid.uuid4().hex}.sqlite3"
    _init_legacy_pending_confirm_db(
        db_path,
        ledger_sql="CREATE TABLE ledger (id INTEGER PRIMARY KEY AUTOINCREMENT, from_miner TEXT NOT NULL)",
    )

    admin_key = "test-admin-key"
    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    monkeypatch.setenv("RC_ADMIN_KEY", admin_key)
    integrated_node.app.config["TESTING"] = True

    from_wallet = "RTC" + "a" * 40
    to_wallet = "RTC" + "b" * 40
    amount_i64 = 1_250_000
    now = int(time.time())

    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute(
            "INSERT INTO balances (miner_pk, balance_rtc) VALUES (?, ?)",
            (from_wallet, 2.0),
        )
        conn.execute(
            """
            INSERT INTO pending_ledger
                (ts, epoch, from_miner, to_miner, amount_i64, reason, created_at, confirms_at, tx_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now - 10,
                7,
                from_wallet,
                to_wallet,
                amount_i64,
                "signed_wallet_transfer:legacy",
                now - 10,
                now - 1,
                "legacy-confirm-rollback-tx",
            ),
        )
        conn.commit()

    with integrated_node.app.test_client() as client:
        response = client.post("/pending/confirm", headers={"X-Admin-Key": admin_key})

    assert response.status_code == 200
    body = response.get_json()
    assert body["confirmed_count"] == 0
    assert body["confirmed_ids"] == []
    assert body["errors"][0]["id"] == 1

    with closing(sqlite3.connect(db_path)) as conn:
        balances = dict(conn.execute("SELECT miner_pk, balance_rtc FROM balances").fetchall())
        (status, confirmed_at) = conn.execute(
            "SELECT status, confirmed_at FROM pending_ledger WHERE id = 1"
        ).fetchone()

    assert balances == {from_wallet: 2.0}
    assert status == "pending"
    assert confirmed_at is None

    if db_path.exists():
        db_path.unlink()


def test_pending_confirm_keeps_transfer_pending_on_unsupported_balance_schema(monkeypatch):
    local_tmp_dir = Path(__file__).parent / ".tmp_signed_transfer"
    local_tmp_dir.mkdir(exist_ok=True)
    db_path = local_tmp_dir / f"{uuid.uuid4().hex}.sqlite3"

    with closing(sqlite3.connect(db_path)) as conn:
        conn.executescript(
            """
            CREATE TABLE balances (
                wallet TEXT PRIMARY KEY,
                credits INTEGER DEFAULT 0
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

    admin_key = "test-admin-key"
    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    monkeypatch.setenv("RC_ADMIN_KEY", admin_key)
    integrated_node.app.config["TESTING"] = True

    from_wallet = "RTC" + "a" * 40
    to_wallet = "RTC" + "b" * 40
    now = int(time.time())

    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO pending_ledger
                (ts, epoch, from_miner, to_miner, amount_i64, reason, created_at, confirms_at, tx_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now - 10,
                7,
                from_wallet,
                to_wallet,
                1_250_000,
                "signed_wallet_transfer:unsupported-schema",
                now - 10,
                now - 1,
                "unsupported-schema-tx",
            ),
        )
        conn.commit()

    with integrated_node.app.test_client() as client:
        response = client.post("/pending/confirm", headers={"X-Admin-Key": admin_key})

    assert response.status_code == 200
    body = response.get_json()
    assert body["confirmed_count"] == 0
    assert body["confirmed_ids"] == []
    assert body["errors"] == [
        {"id": 1, "error": "unsupported balances schema for wallet transfer"}
    ]

    with closing(sqlite3.connect(db_path)) as conn:
        (status, voided_reason, confirmed_at) = conn.execute(
            "SELECT status, voided_reason, confirmed_at FROM pending_ledger WHERE id = 1"
        ).fetchone()

    assert status == "pending"
    assert voided_reason is None
    assert confirmed_at is None

    if db_path.exists():
        db_path.unlink()
