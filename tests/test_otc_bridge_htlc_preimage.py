# SPDX-License-Identifier: MIT
import hashlib
import importlib.util
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def load_otc_bridge(tmp_path):
    module_path = Path(__file__).resolve().parents[1] / "otc-bridge" / "otc_bridge.py"
    db_path = tmp_path / "otc_bridge.db"
    previous_db_path = os.environ.get("OTC_DB_PATH")
    os.environ["OTC_DB_PATH"] = str(db_path)

    module_name = f"otc_bridge_htlc_test_{abs(hash(db_path))}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        module.init_db()
        return module
    finally:
        if previous_db_path is None:
            os.environ.pop("OTC_DB_PATH", None)
        else:
            os.environ["OTC_DB_PATH"] = previous_db_path


def make_wallet(module):
    private_key = Ed25519PrivateKey.generate()
    public_key_hex = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()
    return private_key, public_key_hex, module.rtc_address_from_public_key(public_key_hex)


def wallet_auth(module, private_key, public_key_hex, action, order_id, wallet, **bound_fields):
    timestamp = int(time.time())
    message = module.wallet_auth_message(action, order_id, wallet, timestamp, bound_fields)
    return {
        "public_key": public_key_hex,
        "signature": private_key.sign(message).hex(),
        "timestamp": timestamp,
    }


def create_order_auth(module, private_key, public_key_hex, wallet, payload):
    _, amount_micro_rtc = module.decimal_units(
        payload["amount_rtc"], module.RTC_UNIT, "amount_rtc"
    )
    _, price_per_rtc_nano_quote = module.decimal_units(
        payload["price_per_rtc"], module.QUOTE_PRICE_SCALE, "price_per_rtc"
    )
    bound_fields = module.create_order_auth_fields(
        payload["side"],
        payload["pair"],
        amount_micro_rtc,
        price_per_rtc_nano_quote,
        payload.get("ttl_seconds", module.ORDER_TTL_DEFAULT),
        payload.get("eth_address", ""),
    )
    return wallet_auth(
        module,
        private_key,
        public_key_hex,
        "create_order",
        module.CREATE_ORDER_AUTH_ID,
        wallet,
        **bound_fields,
    )


def signed_order_payload(module, private_key, public_key_hex, wallet, side):
    payload = {
        "side": side,
        "pair": "RTC/USDC",
        "wallet": wallet,
        "amount_rtc": 100,
        "price_per_rtc": "0.10",
    }
    payload["wallet_auth"] = create_order_auth(
        module, private_key, public_key_hex, wallet, payload
    )
    return payload


def create_buy_order(module, client, buyer_key, buyer_pub, buyer_wallet):
    return client.post(
        "/api/orders",
        json=signed_order_payload(module, buyer_key, buyer_pub, buyer_wallet, "buy"),
    )


def create_sell_order(module, client, seller_key, seller_pub, seller_wallet):
    with patch.object(module, "rtc_get_balance", return_value=500.0), patch.object(
        module,
        "rtc_create_escrow_job",
        return_value={"ok": True, "job_id": "job_sell1"},
    ):
        return client.post(
            "/api/orders",
            json=signed_order_payload(module, seller_key, seller_pub, seller_wallet, "sell"),
        )


def match_buy_order(module, client, order_id, seller_key, seller_pub, seller_wallet):
    with patch.object(module, "rtc_get_balance", return_value=500.0), patch.object(
        module,
        "rtc_create_escrow_job",
        return_value={"ok": True, "job_id": "job_conf1"},
    ):
        return client.post(
            f"/api/orders/{order_id}/match",
            json={
                "wallet": seller_wallet,
                "wallet_auth": wallet_auth(
                    module,
                    seller_key,
                    seller_pub,
                    "match_order",
                    order_id,
                    seller_wallet,
                    eth_address="",
                ),
            },
        )


def test_sell_order_returns_seller_htlc_secret_but_public_read_hides_it(tmp_path):
    module = load_otc_bridge(tmp_path)
    seller_key, seller_pub, seller_wallet = make_wallet(module)

    with module.app.test_client() as client:
        response = create_sell_order(module, client, seller_key, seller_pub, seller_wallet)
        assert response.status_code == 201
        body = response.get_json()

        secret = body["htlc_secret"]
        assert len(secret) == 64
        assert body["htlc_hash"] == hashlib.sha256(bytes.fromhex(secret)).hexdigest()

        public_read = client.get(f"/api/orders/{body['order_id']}")
        assert public_read.status_code == 200
        public_order = public_read.get_json()["order"]
        assert public_order["htlc_hash"] == body["htlc_hash"]
        assert "htlc_secret" not in public_order


def test_buy_order_defers_htlc_secret_to_matching_seller(tmp_path):
    module = load_otc_bridge(tmp_path)
    buyer_key, buyer_pub, buyer_wallet = make_wallet(module)
    seller_key, seller_pub, seller_wallet = make_wallet(module)

    with module.app.test_client() as client:
        create_response = create_buy_order(module, client, buyer_key, buyer_pub, buyer_wallet)
        order = create_response.get_json()
        assert "htlc_secret" not in order
        assert "htlc_hash" not in order

        match_response = match_buy_order(
            module, client, order["order_id"], seller_key, seller_pub, seller_wallet
        )
        assert match_response.status_code == 200
        match_body = match_response.get_json()
        seller_secret = match_body["htlc_secret"]
        assert len(seller_secret) == 64
        assert match_body["htlc_hash"] == hashlib.sha256(
            bytes.fromhex(seller_secret)
        ).hexdigest()

        public_read = client.get(f"/api/orders/{order['order_id']}")
        assert public_read.status_code == 200
        public_order = public_read.get_json()["order"]
        assert public_order["htlc_hash"] == match_body["htlc_hash"]
        assert "htlc_secret" not in public_order

        with patch.object(module.requests, "post") as mock_post:
            m_resp = MagicMock(ok=True, text='{"ok": true}')
            m_resp.json.return_value = {"ok": True, "phase": "pending", "tx_hash": "mock_tx"}
            mock_post.return_value = m_resp
            confirm_response = client.post(
                f"/api/orders/{order['order_id']}/confirm",
                json={
                    "wallet": seller_wallet,
                    "quote_tx": "0xabc123def456",
                    "secret": seller_secret,
                },
            )

        body = confirm_response.get_json()
        assert confirm_response.status_code == 200
        assert body["ok"] is True
        assert body["status"] == "completed"
        assert body["htlc_secret"] == seller_secret


def test_buy_order_buyer_cannot_confirm_with_seller_secret(tmp_path):
    module = load_otc_bridge(tmp_path)
    buyer_key, buyer_pub, buyer_wallet = make_wallet(module)
    seller_key, seller_pub, seller_wallet = make_wallet(module)

    with module.app.test_client() as client:
        create_response = create_buy_order(module, client, buyer_key, buyer_pub, buyer_wallet)
        order = create_response.get_json()
        match_response = match_buy_order(
            module, client, order["order_id"], seller_key, seller_pub, seller_wallet
        )
        assert match_response.status_code == 200
        seller_secret = match_response.get_json()["htlc_secret"]

        confirm_response = client.post(
            f"/api/orders/{order['order_id']}/confirm",
            json={
                "wallet": buyer_wallet,
                "quote_tx": "0xabc123def456",
                "secret": seller_secret,
            },
        )

        assert confirm_response.status_code == 403
        assert (
            confirm_response.get_json()["error"]
            == "Only the RTC seller can confirm settlement"
        )


def test_confirm_requires_quote_tx_before_releasing_escrow(tmp_path):
    module = load_otc_bridge(tmp_path)
    buyer_key, buyer_pub, buyer_wallet = make_wallet(module)
    seller_key, seller_pub, seller_wallet = make_wallet(module)

    with module.app.test_client() as client:
        create_response = create_buy_order(module, client, buyer_key, buyer_pub, buyer_wallet)
        order = create_response.get_json()
        match_response = match_buy_order(
            module, client, order["order_id"], seller_key, seller_pub, seller_wallet
        )
        assert match_response.status_code == 200
        seller_secret = match_response.get_json()["htlc_secret"]

        with patch.object(module.requests, "post") as mock_post:
            confirm_response = client.post(
                f"/api/orders/{order['order_id']}/confirm",
                json={"wallet": seller_wallet, "secret": seller_secret},
            )

        assert confirm_response.status_code == 400
        assert confirm_response.get_json()["error"] == "quote_tx required"
        mock_post.assert_not_called()

        public_order = client.get(f"/api/orders/{order['order_id']}").get_json()["order"]
        assert public_order["status"] == "matched"
        assert public_order["settlement_tx"] is None


def test_invalid_htlc_secret_returns_client_error(tmp_path):
    module = load_otc_bridge(tmp_path)
    buyer_key, buyer_pub, buyer_wallet = make_wallet(module)
    seller_key, seller_pub, seller_wallet = make_wallet(module)

    with module.app.test_client() as client:
        create_response = create_buy_order(module, client, buyer_key, buyer_pub, buyer_wallet)
        order_id = create_response.get_json()["order_id"]
        match_response = match_buy_order(
            module, client, order_id, seller_key, seller_pub, seller_wallet
        )
        assert match_response.status_code == 200

        confirm_response = client.post(
            f"/api/orders/{order_id}/confirm",
            json={
                "wallet": seller_wallet,
                "quote_tx": "0xabc123def456",
                "secret": "not-hex",
            },
        )

        assert confirm_response.status_code == 400
        assert confirm_response.get_json()["error"] == "Invalid HTLC secret format"
