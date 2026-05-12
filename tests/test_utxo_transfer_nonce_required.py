# SPDX-License-Identifier: MIT
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

from flask import Flask


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "node"))

from utxo_db import UNIT, UtxoDB
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
        "memo": "nonce-required-test",
    }


def cleanup_db(db_path):
    for suffix in ("", "-wal", "-shm"):
        path = db_path + suffix
        if os.path.exists(path):
            os.unlink(path)


def transfer_nonce_count(db_path):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM transfer_nonces").fetchone()[0]
    finally:
        conn.close()


def test_utxo_transfer_accepts_numeric_zero_nonce():
    client, utxo_db, db_path = build_client()
    try:
        seed_coinbase(utxo_db, "RTC_test_aabbccdd", 100 * UNIT)

        response = client.post("/utxo/transfer", json=payload(nonce=0))

        assert response.status_code == 200
        assert response.get_json()["ok"] is True
        assert transfer_nonce_count(db_path) == 1
    finally:
        cleanup_db(db_path)


def test_utxo_transfer_rejects_blank_nonce_values():
    for blank_nonce in ("", "   ", None, False):
        client, utxo_db, db_path = build_client()
        try:
            seed_coinbase(utxo_db, "RTC_test_aabbccdd", 100 * UNIT)

            response = client.post(
                "/utxo/transfer",
                json=payload(nonce=blank_nonce),
            )

            assert response.status_code == 400
            assert response.get_json()["error"] == "Missing required fields"
            assert transfer_nonce_count(db_path) == 0
        finally:
            cleanup_db(db_path)
