import hashlib
import hmac
import importlib.util
import json
import sys
from pathlib import Path

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_API_PATH = REPO_ROOT / "bridge" / "bridge_api.py"


def _load_bridge_api(tmp_path, monkeypatch):
    monkeypatch.setenv("BRIDGE_DB_PATH", str(tmp_path / "bridge.db"))
    monkeypatch.setenv("BRIDGE_ADMIN_KEY", "test-admin-key")
    monkeypatch.setenv("BRIDGE_RECEIPT_SECRET", "test-bridge-secret")
    monkeypatch.setenv("BRIDGE_REQUIRE_PROOF", "true")

    module_name = "bridge_api_base_wallet_validation"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, BRIDGE_API_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _receipt_signature(module, sender_wallet, amount, target_chain, target_wallet, tx_hash):
    payload = {
        "sender_wallet": sender_wallet,
        "amount_base": module._amount_to_base(amount),
        "target_chain": target_chain,
        "target_wallet": target_wallet,
        "tx_hash": tx_hash,
    }
    message = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(
        module.BRIDGE_RECEIPT_SECRET.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()


def test_bridge_lock_rejects_length_valid_non_hex_base_wallet(tmp_path, monkeypatch):
    bridge_api = _load_bridge_api(tmp_path, monkeypatch)
    app = Flask(__name__)
    app.config["TESTING"] = True
    bridge_api.register_bridge_routes(app)

    target_wallet = "0xZZ15a73199d56b7e9c71575bec1632cd1d36908f"
    tx_hash = "rtc-lock-non-hex-base-wallet"
    response = app.test_client().post(
        "/bridge/lock",
        json={
            "sender_wallet": "test-miner",
            "amount": 10.0,
            "target_chain": "base",
            "target_wallet": target_wallet,
            "tx_hash": tx_hash,
            "receipt_signature": _receipt_signature(
                bridge_api,
                "test-miner",
                10.0,
                "base",
                target_wallet,
                tx_hash,
            ),
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Base wallet must be a 0x EVM address"
