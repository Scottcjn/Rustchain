# SPDX-License-Identifier: MIT

import importlib.util
import os
import sys
import time
import types
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def load_otc_bridge(tmp_path):
    if "flask_cors" not in sys.modules:
        flask_cors = types.ModuleType("flask_cors")
        flask_cors.CORS = lambda app: app
        sys.modules["flask_cors"] = flask_cors

    db_path = tmp_path / "otc_bridge.db"
    os.environ["OTC_DB_PATH"] = str(db_path)

    module_path = Path(__file__).resolve().parents[1] / "otc-bridge" / "otc_bridge.py"
    spec = importlib.util.spec_from_file_location("otc_bridge_wallet_auth_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.app.testing = True
    module.init_db()
    return module


def make_wallet(otc_bridge):
    private_key = Ed25519PrivateKey.generate()
    public_key_hex = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()
    return private_key, public_key_hex, otc_bridge.address_from_public_key(public_key_hex)


def wallet_auth(otc_bridge, private_key, public_key_hex, action, order_id, wallet):
    timestamp = int(time.time())
    message = otc_bridge.canonical_wallet_auth_message(action, order_id, wallet, timestamp)
    return {
        "public_key": public_key_hex,
        "signature": private_key.sign(message).hex(),
        "timestamp": timestamp,
    }


def create_buy_order(client, wallet):
    response = client.post(
        "/api/orders",
        json={
            "side": "buy",
            "pair": "RTC/USDC",
            "wallet": wallet,
            "amount_rtc": 10,
            "price_per_rtc": 0.10,
        },
    )
    assert response.status_code == 201
    return response.get_json()["order_id"]


def get_order_status(client, order_id):
    response = client.get(f"/api/orders/{order_id}")
    assert response.status_code == 200
    return response.get_json()["order"]["status"]


def test_cancel_requires_wallet_signature_and_preserves_order(tmp_path):
    otc_bridge = load_otc_bridge(tmp_path)
    maker_key, maker_pub, maker_wallet = make_wallet(otc_bridge)

    with otc_bridge.app.test_client() as client:
        order_id = create_buy_order(client, maker_wallet)
        response = client.post(f"/api/orders/{order_id}/cancel", json={"wallet": maker_wallet})

        assert response.status_code == 401
        assert response.get_json() == {"error": "wallet_auth_required"}
        assert get_order_status(client, order_id) == "open"


def test_cancel_rejects_signature_from_different_wallet_key(tmp_path):
    otc_bridge = load_otc_bridge(tmp_path)
    maker_key, maker_pub, maker_wallet = make_wallet(otc_bridge)
    attacker_key, attacker_pub, _ = make_wallet(otc_bridge)

    with otc_bridge.app.test_client() as client:
        order_id = create_buy_order(client, maker_wallet)
        response = client.post(
            f"/api/orders/{order_id}/cancel",
            json={
                "wallet": maker_wallet,
                "wallet_auth": wallet_auth(
                    otc_bridge, attacker_key, attacker_pub, "cancel_order", order_id, maker_wallet
                ),
            },
        )

        assert response.status_code == 401
        assert response.get_json() == {"error": "wallet_auth_public_key_does_not_match_wallet"}
        assert get_order_status(client, order_id) == "open"


def test_signed_cancel_succeeds_for_order_maker(tmp_path):
    otc_bridge = load_otc_bridge(tmp_path)
    maker_key, maker_pub, maker_wallet = make_wallet(otc_bridge)

    with otc_bridge.app.test_client() as client:
        order_id = create_buy_order(client, maker_wallet)
        response = client.post(
            f"/api/orders/{order_id}/cancel",
            json={
                "wallet": maker_wallet,
                "wallet_auth": wallet_auth(
                    otc_bridge, maker_key, maker_pub, "cancel_order", order_id, maker_wallet
                ),
            },
        )

        assert response.status_code == 200
        assert response.get_json()["status"] == "cancelled"


def test_match_requires_taker_wallet_signature(tmp_path):
    otc_bridge = load_otc_bridge(tmp_path)
    maker_key, maker_pub, maker_wallet = make_wallet(otc_bridge)
    taker_key, taker_pub, taker_wallet = make_wallet(otc_bridge)

    with otc_bridge.app.test_client() as client:
        order_id = create_buy_order(client, maker_wallet)
        unsigned_response = client.post(f"/api/orders/{order_id}/match", json={"wallet": taker_wallet})
        assert unsigned_response.status_code == 401
        assert unsigned_response.get_json() == {"error": "wallet_auth_required"}
        assert get_order_status(client, order_id) == "open"

        with patch.object(otc_bridge, "rtc_get_balance", return_value=500.0), patch.object(
            otc_bridge, "rtc_create_escrow_job", return_value={"ok": True, "job_id": "job_auth_match"}
        ):
            signed_response = client.post(
                f"/api/orders/{order_id}/match",
                json={
                    "wallet": taker_wallet,
                    "wallet_auth": wallet_auth(
                        otc_bridge, taker_key, taker_pub, "match_order", order_id, taker_wallet
                    ),
                },
            )

        assert signed_response.status_code == 200
        assert signed_response.get_json()["status"] == "matched"
