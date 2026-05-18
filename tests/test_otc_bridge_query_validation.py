import importlib.util
import os
import sys
import time
import types
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_otc_bridge(tmp_path):
    if "flask_cors" not in sys.modules:
        flask_cors = types.ModuleType("flask_cors")
        flask_cors.CORS = lambda app, *args, **kwargs: app
        sys.modules["flask_cors"] = flask_cors

    db_path = tmp_path / "otc_bridge.db"
    os.environ["OTC_DB_PATH"] = str(db_path)

    module_path = Path(__file__).resolve().parents[1] / "otc-bridge" / "otc_bridge.py"
    spec = importlib.util.spec_from_file_location("otc_bridge_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.app.testing = True
    module.init_db()
    return module


def signed_order_payload(otc_bridge):
    private_key = Ed25519PrivateKey.generate()
    public_key_hex = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()
    wallet = otc_bridge.rtc_address_from_public_key(public_key_hex)
    payload = {
        "side": "buy",
        "pair": "RTC/USDC",
        "wallet": wallet,
        "amount_rtc": 1,
        "price_per_rtc": "0.10",
    }
    _, amount_micro_rtc = otc_bridge.decimal_units(
        payload["amount_rtc"], otc_bridge.RTC_UNIT, "amount_rtc"
    )
    _, price_per_rtc_nano_quote = otc_bridge.decimal_units(
        payload["price_per_rtc"], otc_bridge.QUOTE_PRICE_SCALE, "price_per_rtc"
    )
    timestamp = int(time.time())
    bound_fields = otc_bridge.create_order_auth_fields(
        payload["side"],
        payload["pair"],
        amount_micro_rtc,
        price_per_rtc_nano_quote,
        otc_bridge.ORDER_TTL_DEFAULT,
        "",
    )
    payload["wallet_auth"] = {
        "public_key": public_key_hex,
        "signature": private_key.sign(
            otc_bridge.wallet_auth_message(
                "create_order",
                otc_bridge.CREATE_ORDER_AUTH_ID,
                wallet,
                timestamp,
                bound_fields,
            )
        ).hex(),
        "timestamp": timestamp,
    }
    return payload


def test_orders_rejects_malformed_pagination(tmp_path):
    otc_bridge = load_otc_bridge(tmp_path)

    with otc_bridge.app.test_client() as client:
        limit_response = client.get("/api/orders?limit=abc")
        offset_response = client.get("/api/orders?offset=abc")

    assert limit_response.status_code == 400
    assert limit_response.get_json() == {"error": "limit_must_be_integer"}
    assert offset_response.status_code == 400
    assert offset_response.get_json() == {"error": "offset_must_be_integer"}


def test_otc_bridge_cors_uses_trusted_origin_allowlist(tmp_path, monkeypatch):
    monkeypatch.delenv("OTC_CORS_ORIGINS", raising=False)
    otc_bridge = load_otc_bridge(tmp_path)

    assert "*" not in otc_bridge.OTC_CORS_ORIGINS
    assert "https://bottube.ai" in otc_bridge.OTC_CORS_ORIGINS
    assert "https://rustchain.org" in otc_bridge.OTC_CORS_ORIGINS


def test_otc_bridge_cors_rejects_wildcard_origin(tmp_path):
    otc_bridge = load_otc_bridge(tmp_path)

    try:
        otc_bridge.parse_cors_origins("https://rustchain.org,*")
    except ValueError as exc:
        assert "must not include '*'" in str(exc)
    else:
        raise AssertionError("wildcard CORS origin should be rejected")


def test_orders_rejects_out_of_range_pagination(tmp_path):
    otc_bridge = load_otc_bridge(tmp_path)

    with otc_bridge.app.test_client() as client:
        limit_response = client.get("/api/orders?limit=0")
        offset_response = client.get("/api/orders?offset=-1")

    assert limit_response.status_code == 400
    assert limit_response.get_json() == {"error": "limit_must_be_positive"}
    assert offset_response.status_code == 400
    assert offset_response.get_json() == {"error": "offset_must_be_non_negative"}


def test_orders_accepts_capped_limit(tmp_path):
    otc_bridge = load_otc_bridge(tmp_path)

    with otc_bridge.app.test_client() as client:
        response = client.get("/api/orders?limit=500")

    assert response.status_code == 200
    assert response.get_json()["ok"] is True


def test_trades_rejects_bad_limits(tmp_path):
    otc_bridge = load_otc_bridge(tmp_path)

    with otc_bridge.app.test_client() as client:
        non_integer_response = client.get("/api/trades?limit=abc")
        negative_response = client.get("/api/trades?limit=-1")

    assert non_integer_response.status_code == 400
    assert non_integer_response.get_json() == {"error": "limit_must_be_integer"}
    assert negative_response.status_code == 400
    assert negative_response.get_json() == {"error": "limit_must_be_positive"}


def test_trades_accepts_capped_limit(tmp_path):
    otc_bridge = load_otc_bridge(tmp_path)

    with otc_bridge.app.test_client() as client:
        response = client.get("/api/trades?limit=500")

    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "trades": []}


def test_unexpected_order_errors_are_generic(tmp_path, monkeypatch):
    otc_bridge = load_otc_bridge(tmp_path)

    def fail_hash(_ip):
        raise RuntimeError("sensitive sqlite path: C:/private/otc_bridge.db")

    monkeypatch.setattr(otc_bridge, "check_rate_limit", lambda _ip: True)
    monkeypatch.setattr(otc_bridge, "hash_ip", fail_hash)

    with otc_bridge.app.test_client() as client:
        response = client.post(
            "/api/orders",
            json=signed_order_payload(otc_bridge),
        )

    assert response.status_code == 500
    assert response.get_json() == {"error": "Internal server error"}


def test_otc_bridge_no_longer_returns_raw_exception_strings():
    source = (REPO_ROOT / "otc-bridge" / "otc_bridge.py").read_text(encoding="utf-8")

    assert 'return jsonify({"error": str(e)}), 500' not in source
    assert 'return {"ok": False, "error": str(e)}' not in source


class ExplodingConnection:
    def cursor(self):
        raise RuntimeError("sensitive sqlite path /var/lib/rustchain/otc_bridge.db")

    def rollback(self):
        pass

    def close(self):
        pass


def test_mutating_order_errors_do_not_leak_exception_details(tmp_path, monkeypatch):
    otc_bridge = load_otc_bridge(tmp_path)
    monkeypatch.setattr(otc_bridge, "check_rate_limit", lambda _ip: True)
    monkeypatch.setattr(otc_bridge, "get_db", lambda: ExplodingConnection())

    cases = [
        ("/api/orders", {
            "side": "buy",
            "pair": "RTC/USDC",
            "wallet": "buyer-wallet",
            "amount_rtc": 1,
            "price_per_rtc": 1,
        }),
        ("/api/orders/otc_test/match", {"wallet": "taker-wallet"}),
        ("/api/orders/otc_test/confirm", {"wallet": "buyer-wallet", "quote_tx": "0xdeadbeef"}),
        ("/api/orders/otc_test/cancel", {"wallet": "maker-wallet"}),
    ]

    with otc_bridge.app.test_client() as client:
        for path, body in cases:
            response = client.post(path, json=body)
            assert response.status_code == 500
            assert response.get_json() == {"error": otc_bridge.GENERIC_INTERNAL_ERROR}


def test_escrow_helper_returns_generic_error_on_exception(tmp_path, monkeypatch):
    otc_bridge = load_otc_bridge(tmp_path)

    def raise_sensitive_error(*_args, **_kwargs):
        raise RuntimeError("upstream token leaked from /etc/otc.env")

    monkeypatch.setattr(otc_bridge.requests, "post", raise_sensitive_error)

    result = otc_bridge.rtc_create_escrow_job(
        poster_wallet="seller-wallet",
        amount_rtc=1,
        title="test escrow",
        description="test",
    )

    assert result == {"ok": False, "error": otc_bridge.GENERIC_INTERNAL_ERROR}
