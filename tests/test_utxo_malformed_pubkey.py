# SPDX-License-Identifier: MIT
"""Regression test for #6114: malformed hex in public_key should return 400."""

import hashlib
import os
import sys
import importlib

import pytest
from flask import Flask


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "node"))
if NODE_DIR not in sys.path:
    sys.path.insert(0, NODE_DIR)

utxo_endpoints = importlib.import_module("utxo_endpoints")


def _real_addr_from_pk(public_key_hex: str) -> str:
    pubkey_hash = hashlib.sha256(bytes.fromhex(public_key_hex)).hexdigest()[:40]
    return f"RTC{pubkey_hash}"


@pytest.fixture
def client(tmp_path):
    app = Flask(__name__)
    utxo_endpoints.register_utxo_blueprint(
        app,
        utxo_db=object(),
        db_path=str(tmp_path / "utxo.db"),
        verify_sig_fn=lambda *args: False,
        addr_from_pk_fn=_real_addr_from_pk,
        current_slot_fn=lambda: 1,
    )
    return app.test_client()


def _transfer_payload(**overrides):
    fake_pubkey = "ab" * 32
    expected_addr = _real_addr_from_pk(fake_pubkey)
    payload = {
        "from_address": expected_addr,
        "to_address": "RTC" + "b" * 40,
        "amount_rtc": 1,
        "public_key": fake_pubkey,
        "signature": "cd" * 32,
        "nonce": 1,
    }
    payload.update(overrides)
    return payload


def test_malformed_hex_pubkey_returns_400(client):
    resp = client.post(
        "/utxo/transfer",
        json=_transfer_payload(public_key="not-hex"),
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Invalid public_key"


def test_odd_length_hex_pubkey_returns_400(client):
    resp = client.post(
        "/utxo/transfer",
        json=_transfer_payload(public_key="abc"),
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Invalid public_key"


def test_valid_hex_pubkey_does_not_crash(client):
    valid_pubkey = "ab" * 32
    expected_addr = _real_addr_from_pk(valid_pubkey)
    resp = client.post(
        "/utxo/transfer",
        json=_transfer_payload(public_key=valid_pubkey, from_address=expected_addr),
    )
    assert resp.status_code == 401
    assert "signature" in resp.get_json()["error"].lower()
