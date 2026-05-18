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
        flask_cors.CORS = lambda app, *args, **kwargs: app
        sys.modules["flask_cors"] = flask_cors

    db_path = tmp_path / "otc_bridge.db"
    os.environ["OTC_DB_PATH"] = str(db_path)

    module_path = Path(__file__).resolve().parents[1] / "otc-bridge" / "otc_bridge.py"
    spec = importlib.util.spec_from_file_location("otc_bridge_wallet_auth_test", module_path)
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
    return private_key, public_key_hex, otc_bridge.rtc_address_from_public_key(public_key_hex)


def wallet_auth(otc_bridge, private_key, public_key_hex, action, order_id, wallet, **bound_fields):
    timestamp = int(time.time())
    message = otc_bridge.wallet_auth_message(action, order_id, wallet, timestamp, bound_fields)
    return {
        "public_key": public_key_hex,
        "signature": private_key.sign(message).hex(),
        "timestamp": timestamp,
    }


def create_order_auth(otc_bridge, private_key, public_key_hex, wallet, payload):
    bound_fields = otc_bridge.create_order_auth_fields(
        payload["side"],
        payload["pair"],
        10_000_000,
        100_000_000,
        payload.get("ttl_seconds", otc_bridge.ORDER_TTL_DEFAULT),
        payload.get("eth_address", ""),
    )
    return wallet_auth(
        otc_bridge,
        private_key,
        public_key_hex,
        "create_order",
        otc_bridge.CREATE_ORDER_AUTH_ID,
        wallet,
        **bound_fields,
    )


def signed_order_payload(otc_bridge, private_key, public_key_hex, wallet, side="buy"):
    payload = {
        "side": side,
        "pair": "RTC/USDC",
        "wallet": wallet,
        "amount_rtc": 10,
        "price_per_rtc": "0.10",
    }
    payload["wallet_auth"] = create_order_auth(
        otc_bridge, private_key, public_key_hex, wallet, payload
    )
    return payload


def open_order_count(client):
    response = client.get("/api/orders")
    assert response.status_code == 200
    return response.get_json()["total"]


def create_buy_order(client, otc_bridge, private_key, public_key_hex, wallet):
    response = client.post(
        "/api/orders",
        json=signed_order_payload(otc_bridge, private_key, public_key_hex, wallet),
    )
    assert response.status_code == 201
    return response.get_json()["order_id"]


def order_status(client, order_id):
    response = client.get(f"/api/orders/{order_id}")
    assert response.status_code == 200
    return response.get_json()["order"]["status"]


def test_cancel_requires_wallet_signature_and_preserves_order(tmp_path):
    otc_bridge = load_otc_bridge(tmp_path)
    maker_key, maker_pub, maker_wallet = make_wallet(otc_bridge)

    with otc_bridge.app.test_client() as client:
        order_id = create_buy_order(client, otc_bridge, maker_key, maker_pub, maker_wallet)
        response = client.post(f"/api/orders/{order_id}/cancel", json={"wallet": maker_wallet})

        assert response.status_code == 401
        assert response.get_json() == {"error": "wallet_auth_required"}
        assert order_status(client, order_id) == "open"


def test_cancel_rejects_signature_from_different_wallet_key(tmp_path):
    otc_bridge = load_otc_bridge(tmp_path)
    maker_key, maker_pub, maker_wallet = make_wallet(otc_bridge)
    attacker_key, attacker_pub, _ = make_wallet(otc_bridge)

    with otc_bridge.app.test_client() as client:
        order_id = create_buy_order(client, otc_bridge, maker_key, maker_pub, maker_wallet)
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
        assert order_status(client, order_id) == "open"


def test_signed_cancel_succeeds_for_order_maker(tmp_path):
    otc_bridge = load_otc_bridge(tmp_path)
    maker_key, maker_pub, maker_wallet = make_wallet(otc_bridge)

    with otc_bridge.app.test_client() as client:
        order_id = create_buy_order(client, otc_bridge, maker_key, maker_pub, maker_wallet)
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
    _, _, taker_wallet = make_wallet(otc_bridge)

    with otc_bridge.app.test_client() as client:
        order_id = create_buy_order(client, otc_bridge, maker_key, maker_pub, maker_wallet)
        response = client.post(
            f"/api/orders/{order_id}/match",
            json={"wallet": taker_wallet, "eth_address": "0x1234"},
        )

        assert response.status_code == 401
        assert response.get_json() == {"error": "wallet_auth_required"}
        assert order_status(client, order_id) == "open"


def test_match_signature_binds_eth_address(tmp_path):
    otc_bridge = load_otc_bridge(tmp_path)
    maker_key, maker_pub, maker_wallet = make_wallet(otc_bridge)
    taker_key, taker_pub, taker_wallet = make_wallet(otc_bridge)

    with otc_bridge.app.test_client() as client:
        order_id = create_buy_order(client, otc_bridge, maker_key, maker_pub, maker_wallet)
        auth = wallet_auth(
            otc_bridge,
            taker_key,
            taker_pub,
            "match_order",
            order_id,
            taker_wallet,
            eth_address="0x1111111111111111111111111111111111111111",
        )
        response = client.post(
            f"/api/orders/{order_id}/match",
            json={
                "wallet": taker_wallet,
                "eth_address": "0x2222222222222222222222222222222222222222",
                "wallet_auth": auth,
            },
        )

        assert response.status_code == 401
        assert response.get_json() == {"error": "wallet_auth_invalid_signature"}
        assert order_status(client, order_id) == "open"


def test_signed_match_succeeds_when_eth_address_matches_signature(tmp_path):
    otc_bridge = load_otc_bridge(tmp_path)
    maker_key, maker_pub, maker_wallet = make_wallet(otc_bridge)
    taker_key, taker_pub, taker_wallet = make_wallet(otc_bridge)
    eth_address = "0x1111111111111111111111111111111111111111"

    with otc_bridge.app.test_client() as client:
        order_id = create_buy_order(client, otc_bridge, maker_key, maker_pub, maker_wallet)
        with patch.object(otc_bridge, "rtc_get_balance", return_value=500.0), patch.object(
            otc_bridge, "rtc_create_escrow_job", return_value={"ok": True, "job_id": "job_auth_match"}
        ):
            response = client.post(
                f"/api/orders/{order_id}/match",
                json={
                    "wallet": taker_wallet,
                    "eth_address": eth_address,
                    "wallet_auth": wallet_auth(
                        otc_bridge,
                        taker_key,
                        taker_pub,
                        "match_order",
                        order_id,
                        taker_wallet,
                        eth_address=eth_address,
                    ),
                },
            )

        assert response.status_code == 200
        assert response.get_json()["status"] == "matched"


def test_create_buy_order_requires_wallet_signature_and_preserves_orderbook(tmp_path):
    otc_bridge = load_otc_bridge(tmp_path)
    _, _, maker_wallet = make_wallet(otc_bridge)

    with otc_bridge.app.test_client() as client:
        response = client.post(
            "/api/orders",
            json={
                "side": "buy",
                "pair": "RTC/USDC",
                "wallet": maker_wallet,
                "amount_rtc": 10,
                "price_per_rtc": "0.10",
            },
        )

        assert response.status_code == 401
        assert response.get_json() == {"error": "wallet_auth_required"}
        assert open_order_count(client) == 0


def test_create_sell_order_requires_wallet_signature_before_escrow(tmp_path):
    otc_bridge = load_otc_bridge(tmp_path)
    _, _, maker_wallet = make_wallet(otc_bridge)

    with otc_bridge.app.test_client() as client:
        with patch.object(otc_bridge, "rtc_get_balance", return_value=500.0), patch.object(
            otc_bridge, "rtc_create_escrow_job", return_value={"ok": True, "job_id": "job_unsigned"}
        ) as create_escrow:
            response = client.post(
                "/api/orders",
                json={
                    "side": "sell",
                    "pair": "RTC/USDC",
                    "wallet": maker_wallet,
                    "amount_rtc": 10,
                    "price_per_rtc": "0.10",
                },
            )

        assert response.status_code == 401
        assert response.get_json() == {"error": "wallet_auth_required"}
        create_escrow.assert_not_called()
        assert open_order_count(client) == 0


def test_signed_create_order_rejects_non_native_maker_wallet(tmp_path):
    otc_bridge = load_otc_bridge(tmp_path)
    maker_key, maker_pub, _ = make_wallet(otc_bridge)
    maker_wallet = "named_maker"
    payload = {
        "side": "buy",
        "pair": "RTC/USDC",
        "wallet": maker_wallet,
        "amount_rtc": 10,
        "price_per_rtc": "0.10",
    }
    payload["wallet_auth"] = create_order_auth(
        otc_bridge, maker_key, maker_pub, maker_wallet, payload
    )

    with otc_bridge.app.test_client() as client:
        response = client.post("/api/orders", json=payload)

        assert response.status_code == 401
        assert response.get_json() == {"error": "wallet_must_be_native_rtc_address"}
        assert open_order_count(client) == 0
