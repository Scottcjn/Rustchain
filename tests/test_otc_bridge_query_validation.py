import importlib.util
import os
import sys
import types
from pathlib import Path


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
