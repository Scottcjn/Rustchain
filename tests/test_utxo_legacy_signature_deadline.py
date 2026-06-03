# SPDX-License-Identifier: MIT
import sqlite3
import sys
import time
from pathlib import Path
from unittest.mock import patch

from flask import Flask


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "node"))

import utxo_endpoints
from utxo_db import UtxoDB, UNIT
from utxo_endpoints import register_utxo_blueprint


def legacy_only_verify(pubkey_hex, message, sig_hex):
    return sig_hex == "legacy" and b'"fee":' not in message


def v2_only_verify(pubkey_hex, message, sig_hex):
    return sig_hex == "v2" and b'"fee":' in message


def mock_addr_from_pk(pubkey_hex):
    return f"RTC_test_{pubkey_hex[:8]}"


def mock_current_slot():
    return 100


def build_client(tmp_path, verify_sig_fn):
    db_path = str(tmp_path / "utxo_legacy_signature_deadline.db")

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER DEFAULT 0)"
        )

    utxo_db = UtxoDB(db_path)
    utxo_db.init_tables()

    app = Flask(__name__)
    app.config["TESTING"] = True
    register_utxo_blueprint(
        app,
        utxo_db,
        db_path,
        verify_sig_fn=verify_sig_fn,
        addr_from_pk_fn=mock_addr_from_pk,
        current_slot_fn=mock_current_slot,
        dual_write=False,
    )

    return app.test_client(), utxo_db, db_path


def seed_coinbase(utxo_db, address, value_nrtc):
    assert utxo_db.apply_transaction(
        {
            "tx_type": "mining_reward",
            "inputs": [],
            "outputs": [{"address": address, "value_nrtc": value_nrtc}],
            "timestamp": int(time.time()),
            "_allow_minting": True,
        },
        block_height=1,
    )


def transfer_payload(signature, fee_rtc=1.0):
    return {
        "from_address": "RTC_test_aabbccdd",
        "to_address": "bob",
        "amount_rtc": 10.0,
        "fee_rtc": fee_rtc,
        "public_key": "aabbccdd" * 8,
        "signature": signature,
        "nonce": 1733420000000,
        "memo": "legacy-cutoff-test",
    }


def test_legacy_signature_is_accepted_before_cutoff(tmp_path):
    client, utxo_db, _db_path = build_client(tmp_path, legacy_only_verify)
    seed_coinbase(utxo_db, "RTC_test_aabbccdd", 100 * UNIT)
    with patch.object(utxo_endpoints.time, "time", return_value=1782863999):
        response = client.post("/utxo/transfer", json=transfer_payload("legacy", fee_rtc=0.0))

    assert response.status_code == 200
    assert response.get_json()["ok"] is True


def test_legacy_signature_cannot_authorize_nonzero_fee_before_cutoff(tmp_path):
    client, utxo_db, _db_path = build_client(tmp_path, legacy_only_verify)
    seed_coinbase(utxo_db, "RTC_test_aabbccdd", 100 * UNIT)
    with patch.object(utxo_endpoints.time, "time", return_value=1782863999):
        response = client.post("/utxo/transfer", json=transfer_payload("legacy", fee_rtc=1.0))

    assert response.status_code == 401
    assert response.get_json()["code"] == "LEGACY_SIGNATURE_FEE_UNBOUND"
    assert utxo_db.get_balance("RTC_test_aabbccdd") == 100 * UNIT
    assert utxo_db.get_balance("bob") == 0


def test_legacy_signature_is_rejected_after_cutoff(tmp_path):
    client, utxo_db, _db_path = build_client(tmp_path, legacy_only_verify)
    seed_coinbase(utxo_db, "RTC_test_aabbccdd", 100 * UNIT)
    with patch.object(utxo_endpoints.time, "time", return_value=1782864000):
        response = client.post("/utxo/transfer", json=transfer_payload("legacy", fee_rtc=0.0))

    assert response.status_code == 401
    assert response.get_json()["code"] == "LEGACY_SIGNATURE_EXPIRED"
    assert utxo_db.get_balance("RTC_test_aabbccdd") == 100 * UNIT
    assert utxo_db.get_balance("bob") == 0


def test_v2_signature_still_accepts_fee_after_cutoff(tmp_path):
    client, utxo_db, _db_path = build_client(tmp_path, v2_only_verify)
    seed_coinbase(utxo_db, "RTC_test_aabbccdd", 100 * UNIT)
    with patch.object(utxo_endpoints.time, "time", return_value=1782864000):
        response = client.post("/utxo/transfer", json=transfer_payload("v2"))

    assert response.status_code == 200
    assert response.get_json()["ok"] is True
    assert utxo_db.get_balance("bob") == 10 * UNIT
