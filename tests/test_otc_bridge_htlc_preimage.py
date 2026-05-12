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


def test_create_order_returns_creator_htlc_secret_but_public_read_hides_it(tmp_path):
    module = load_otc_bridge(tmp_path)

    with module.app.test_client() as client:
        response = create_buy_order(client)
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


def test_creator_htlc_secret_can_complete_matched_order(tmp_path):
    module = load_otc_bridge(tmp_path)

    with module.app.test_client() as client:
        create_response = create_buy_order(client)
        order = create_response.get_json()
        match_response = match_buy_order(module, client, order["order_id"])
        assert match_response.status_code == 200

        with patch.object(module.requests, "post") as mock_post:
            mock_post.return_value = MagicMock(ok=True, text='{"ok": true}')
            confirm_response = client.post(
                f"/api/orders/{order['order_id']}/confirm",
                json={
                    "wallet": "buyer1",
                    "quote_tx": "0xabc123def456",
                    "secret": order["htlc_secret"],
                },
            )

        body = confirm_response.get_json()
        assert confirm_response.status_code == 200
        assert body["ok"] is True
        assert body["status"] == "completed"
        assert body["htlc_secret"] == order["htlc_secret"]


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
                "wallet": "buyer1",
                "quote_tx": "0xabc123def456",
                "secret": "not-hex",
            },
        )

        assert confirm_response.status_code == 400
        assert confirm_response.get_json()["error"] == "Invalid HTLC secret format"
