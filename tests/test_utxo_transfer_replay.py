import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

from flask import Flask


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "node"))

from utxo_db import UtxoDB, UNIT
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


def nonce_count(db_path):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM transfer_nonces").fetchone()[0]
    finally:
        conn.close()


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

        assert nonce_count(db_path) == 1
    finally:
        os.unlink(db_path)


def test_utxo_transfer_failed_attempt_does_not_burn_nonce():
    client, utxo_db, db_path = build_client()
    try:
        seed_coinbase(utxo_db, "RTC_test_aabbccdd", 5 * UNIT)
        req = payload(nonce=1733420009999, amount_rtc=10.0)

        rejected = client.post("/utxo/transfer", json=req)
        assert rejected.status_code == 400
        assert rejected.get_json()["error"] == "Insufficient UTXO balance"

        assert nonce_count(db_path) == 0

        seed_coinbase(utxo_db, "RTC_test_aabbccdd", 20 * UNIT, height=2)
        accepted = client.post("/utxo/transfer", json=req)
        assert accepted.status_code == 200
        assert accepted.get_json()["ok"] is True

        assert nonce_count(db_path) == 1
        assert utxo_db.get_balance("bob") == 10 * UNIT
    finally:
        os.unlink(db_path)
