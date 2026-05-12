# SPDX-License-Identifier: MIT
import hashlib
import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


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


def create_buy_order(client):
    return client.post(
        "/api/orders",
        json={
            "side": "buy",
            "pair": "RTC/USDC",
            "wallet": "buyer1",
            "amount_rtc": 100,
            "price_per_rtc": 0.10,
        },
    )


def create_sell_order(module, client):
    with patch.object(module, "rtc_get_balance", return_value=500.0), patch.object(
        module,
        "rtc_create_escrow_job",
        return_value={"ok": True, "job_id": "job_sell1"},
    ):
        return client.post(
            "/api/orders",
            json={
                "side": "sell",
                "pair": "RTC/USDC",
                "wallet": "seller1",
                "amount_rtc": 100,
                "price_per_rtc": 0.10,
            },
        )


def match_buy_order(module, client, order_id):
    with patch.object(module, "rtc_get_balance", return_value=500.0), patch.object(
        module,
        "rtc_create_escrow_job",
        return_value={"ok": True, "job_id": "job_conf1"},
    ):
        return client.post(
            f"/api/orders/{order_id}/match",
            json={"wallet": "seller1"},
        )


def test_sell_order_returns_seller_htlc_secret_but_public_read_hides_it(tmp_path):
    module = load_otc_bridge(tmp_path)

    with module.app.test_client() as client:
        response = create_sell_order(module, client)
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

    with module.app.test_client() as client:
        create_response = create_buy_order(client)
        order = create_response.get_json()
        assert "htlc_secret" not in order
        assert "htlc_hash" not in order

        match_response = match_buy_order(module, client, order["order_id"])
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
            mock_post.return_value = MagicMock(ok=True, text='{"ok": true}')
            confirm_response = client.post(
                f"/api/orders/{order['order_id']}/confirm",
                json={
                    "wallet": "seller1",
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

    with module.app.test_client() as client:
        create_response = create_buy_order(client)
        order = create_response.get_json()
        match_response = match_buy_order(module, client, order["order_id"])
        assert match_response.status_code == 200
        seller_secret = match_response.get_json()["htlc_secret"]

        confirm_response = client.post(
            f"/api/orders/{order['order_id']}/confirm",
            json={
                "wallet": "buyer1",
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

    with module.app.test_client() as client:
        create_response = create_buy_order(client)
        order = create_response.get_json()
        match_response = match_buy_order(module, client, order["order_id"])
        assert match_response.status_code == 200
        seller_secret = match_response.get_json()["htlc_secret"]

        with patch.object(module.requests, "post") as mock_post:
            confirm_response = client.post(
                f"/api/orders/{order['order_id']}/confirm",
                json={"wallet": "seller1", "secret": seller_secret},
            )

        assert confirm_response.status_code == 400
        assert confirm_response.get_json()["error"] == "quote_tx required"
        mock_post.assert_not_called()

        public_order = client.get(f"/api/orders/{order['order_id']}").get_json()["order"]
        assert public_order["status"] == "matched"
        assert public_order["settlement_tx"] is None


def test_invalid_htlc_secret_returns_client_error(tmp_path):
    module = load_otc_bridge(tmp_path)

    with module.app.test_client() as client:
        create_response = create_buy_order(client)
        order_id = create_response.get_json()["order_id"]
        match_response = match_buy_order(module, client, order_id)
        assert match_response.status_code == 200

        confirm_response = client.post(
            f"/api/orders/{order_id}/confirm",
            json={
                "wallet": "seller1",
                "quote_tx": "0xabc123def456",
                "secret": "not-hex",
            },
        )

        assert confirm_response.status_code == 400
        assert confirm_response.get_json()["error"] == "Invalid HTLC secret format"
