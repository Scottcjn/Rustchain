import os
import json
import gc
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

from flask import Flask


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "node"))

from utxo_db import UtxoDB, UNIT
import utxo_endpoints
from utxo_endpoints import register_utxo_blueprint


def mock_verify_sig(pubkey_hex, message, sig_hex):
    return True


def mock_addr_from_pk(pubkey_hex):
    return f"RTC_test_{pubkey_hex[:8]}"


def mock_current_slot():
    return 100


def build_client():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER DEFAULT 0)"
    )
    conn.commit()
    conn.close()

    utxo_db = UtxoDB(db_path)
    utxo_db.init_tables()

    app = Flask(__name__)
    app.config["TESTING"] = True
    register_utxo_blueprint(
        app,
        utxo_db,
        db_path,
        verify_sig_fn=mock_verify_sig,
        addr_from_pk_fn=mock_addr_from_pk,
        current_slot_fn=mock_current_slot,
        dual_write=False,
    )

    return app.test_client(), utxo_db, db_path


def seed_coinbase(utxo_db, address, value_nrtc, height=1):
    ok = utxo_db.apply_transaction(
        {
            "tx_type": "mining_reward",
            "inputs": [],
            "outputs": [{"address": address, "value_nrtc": value_nrtc}],
            "timestamp": int(time.time()),
            "_allow_minting": True,
        },
        block_height=height,
    )
    assert ok is True


def payload(nonce=1733420000000, amount_rtc=10.0):
    return {
        "from_address": "RTC_test_aabbccdd",
        "to_address": "bob",
        "amount_rtc": amount_rtc,
        "public_key": "aabbccdd" * 8,
        "signature": "sig" * 22,
        "nonce": nonce,
        "memo": "replay-test",
    }


def cleanup_db(client, db_path):
    try:
        client.__exit__(None, None, None)
    except Exception:
        pass
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.execute("PRAGMA journal_mode=DELETE")
    except sqlite3.Error:
        pass
    utxo_endpoints._utxo_db = None
    utxo_endpoints._db_path = None
    gc.collect()
    for path in (db_path, f"{db_path}-wal", f"{db_path}-shm"):
        for attempt in range(20):
            try:
                if os.path.exists(path):
                    os.unlink(path)
                break
            except PermissionError:
                if attempt == 19:
                    break
                time.sleep(0.05)


def test_utxo_transfer_rejects_duplicate_nonce():
    client, utxo_db, db_path = build_client()
    try:
        seed_coinbase(utxo_db, "RTC_test_aabbccdd", 100 * UNIT)

        first = client.post("/utxo/transfer", json=payload())
        assert first.status_code == 200
        assert first.get_json()["ok"] is True

        second = client.post("/utxo/transfer", json=payload())
        assert second.status_code == 400
        body = second.get_json()
        assert body["code"] == "REPLAY_DETECTED"
        assert "Nonce already used" in body["error"]

        assert utxo_db.get_balance("bob") == 10 * UNIT

        with sqlite3.connect(db_path) as conn:
            nonce_count = conn.execute("SELECT COUNT(*) FROM transfer_nonces").fetchone()[0]

        assert nonce_count == 1
    finally:
        cleanup_db(client, db_path)


def test_utxo_transfer_rejects_non_scalar_nonce_replay_bypass():
    """Object nonces must not bypass replay protection via key order.

    JSON signing uses sort_keys=True, so {"a":1,"b":2} and {"b":2,"a":1}
    produce the same signed bytes. The replay table previously stored
    str(nonce), whose order follows the submitted JSON object, allowing the
    same signature to drain another UTXO with a reordered nonce object.
    """
    client, utxo_db, db_path = build_client()
    try:
        sender = "RTC_test_aabbccdd"
        recipient = "bob"
        seed_coinbase(utxo_db, sender, 20 * UNIT)

        signed_message = json.dumps(
            {
                "from": sender,
                "to": recipient,
                "amount": 10.0,
                "fee": 0.0,
                "memo": "replay-test",
                "nonce": {"a": 1, "b": 2},
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()

        old_verify = utxo_endpoints._verify_sig_fn

        def verify_object_nonce(pubkey_hex, message, sig_hex):
            return sig_hex == "object-nonce-sig" and message == signed_message

        try:
            utxo_endpoints._verify_sig_fn = verify_object_nonce
            first = payload(nonce={"a": 1, "b": 2})
            first["signature"] = "object-nonce-sig"
            first_response = client.post("/utxo/transfer", json=first)
        finally:
            utxo_endpoints._verify_sig_fn = old_verify

        assert first_response.status_code == 400
        assert "Invalid nonce" in first_response.get_json()["error"]
        assert utxo_db.get_balance(sender) == 20 * UNIT
        assert utxo_db.get_balance(recipient) == 0

        with sqlite3.connect(db_path) as conn:
            nonce_count = conn.execute(
                "SELECT COUNT(*) FROM transfer_nonces"
            ).fetchone()[0]
        assert nonce_count == 0
    finally:
        cleanup_db(client, db_path)


def test_utxo_transfer_failed_attempt_does_not_burn_nonce():
    client, utxo_db, db_path = build_client()
    try:
        seed_coinbase(utxo_db, "RTC_test_aabbccdd", 5 * UNIT)
        req = payload(nonce=1733420009999, amount_rtc=10.0)

        rejected = client.post("/utxo/transfer", json=req)
        assert rejected.status_code == 400
        assert rejected.get_json()["error"] == "Insufficient UTXO balance"

        with sqlite3.connect(db_path) as conn:
            nonce_count = conn.execute("SELECT COUNT(*) FROM transfer_nonces").fetchone()[0]
        assert nonce_count == 0

        seed_coinbase(utxo_db, "RTC_test_aabbccdd", 20 * UNIT, height=2)
        accepted = client.post("/utxo/transfer", json=req)
        assert accepted.status_code == 200
        assert accepted.get_json()["ok"] is True

        with sqlite3.connect(db_path) as conn:
            nonce_count = conn.execute("SELECT COUNT(*) FROM transfer_nonces").fetchone()[0]
        assert nonce_count == 1
        assert utxo_db.get_balance("bob") == 10 * UNIT
    finally:
        cleanup_db(client, db_path)
