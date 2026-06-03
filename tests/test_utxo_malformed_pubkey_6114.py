# SPDX-License-Identifier: MIT
"""Regression test for #6114: malformed public_key should return 400, not 500."""

import os
import sys
import importlib

import pytest
from flask import Flask


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "node"))
if NODE_DIR not in sys.path:
    sys.path.insert(0, NODE_DIR)

utxo_endpoints = importlib.import_module("utxo_endpoints")


def _addr_from_pk(pubkey_hex: str) -> str:
    """Stub: only valid hex survives; raises ValueError on bad hex."""
    try:
        bytes.fromhex(pubkey_hex)
    except ValueError:
        raise ValueError(f"Invalid hex: {pubkey_hex[:20]}")
    return f"RTC1{pubkey_hex[:40]}"


@pytest.fixture
def client(tmp_path):
    app = Flask(__name__)
    utxo_endpoints.register_utxo_blueprint(
        app,
        utxo_db=object(),
        db_path=str(tmp_path / "utxo.db"),
        verify_sig_fn=lambda *args: False,
        addr_from_pk_fn=_addr_from_pk,
        current_slot_fn=lambda: 1,
    )
    return app.test_client()


def test_malformed_public_key_returns_400(client):
    """Non-hex public_key should return 400, not 500."""
    resp = client.post("/utxo/transfer", json={
        "from_address": "RTC1aaaa",
        "to_address": "RTC1bbbb",
        "public_key": "not-hex-at-all!!",
        "signature": "abcd1234",
        "nonce": "n1",
        "amount_rtc": 1.0,
    })
    assert resp.status_code == 400
    data = resp.get_json()
    assert "public_key" in data["error"].lower() or "hex" in data["error"].lower()


def test_short_public_key_returns_400(client):
    """Too-short hex public_key should return 400."""
    resp = client.post("/utxo/transfer", json={
        "from_address": "RTC1aaaa",
        "to_address": "RTC1bbbb",
        "public_key": "abcd",
        "signature": "abcd1234",
        "nonce": "n1",
        "amount_rtc": 1.0,
    })
    assert resp.status_code == 400


def test_valid_hex_length_passes_hex_check(client):
    """Valid 64-char hex public_key should pass hex validation (may fail later)."""
    valid_pk = "a" * 64
    resp = client.post("/utxo/transfer", json={
        "from_address": "RTC1aaaa",
        "to_address": "RTC1bbbb",
        "public_key": valid_pk,
        "signature": "b" * 128,
        "nonce": "n1",
        "amount_rtc": 1.0,
    })
    data = resp.get_json()
    if resp.status_code == 400 and "error" in data:
        assert "64 hex" not in data["error"]
