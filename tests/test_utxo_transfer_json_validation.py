# SPDX-License-Identifier: MIT

import os
import sys
import importlib

import pytest
from flask import Flask


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "node"))
if NODE_DIR not in sys.path:
    sys.path.insert(0, NODE_DIR)

utxo_endpoints = importlib.import_module("utxo_endpoints")


@pytest.fixture
def client(tmp_path):
    app = Flask(__name__)
    utxo_endpoints.register_utxo_blueprint(
        app,
        utxo_db=object(),
        db_path=str(tmp_path / "utxo.db"),
        verify_sig_fn=lambda *args: False,
        addr_from_pk_fn=lambda public_key: "RTC" + "a" * 40,
        current_slot_fn=lambda: 1,
    )
    return app.test_client()


def _transfer_payload(**overrides):
    payload = {
        "from_address": "RTC" + "a" * 40,
        "to_address": "RTC" + "b" * 40,
        "amount_rtc": 1,
        "public_key": "pubkey",
        "signature": "signature",
        "nonce": 1,
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize(
    "field,value",
    (
        ("from_address", ["RTC" + "a" * 40]),
        ("to_address", {"address": "RTC" + "b" * 40}),
        ("public_key", ["pubkey"]),
        ("signature", {"sig": "signature"}),
    ),
)
def test_utxo_transfer_rejects_structured_string_fields(client, field, value):
    response = client.post("/utxo/transfer", json=_transfer_payload(**{field: value}))

    assert response.status_code == 400
    assert response.get_json() == {"error": f"{field} must be a string"}


def test_utxo_transfer_rejects_malformed_public_key_material(client, monkeypatch):
    monkeypatch.setattr(
        utxo_endpoints,
        "_addr_from_pk_fn",
        lambda public_key: (_ for _ in ()).throw(ValueError("bad hex")),
    )

    response = client.post(
        "/utxo/transfer",
        json=_transfer_payload(public_key="not-hex"),
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "Invalid public_key"}


def test_utxo_transfer_still_reports_missing_trimmed_string_fields(client):
    response = client.post(
        "/utxo/transfer",
        json=_transfer_payload(from_address="   "),
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Missing required fields"
