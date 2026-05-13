import importlib.util
import os
import sys
import types
from pathlib import Path


def load_otc_bridge(tmp_path, cors_origins=None):
    flask_cors = sys.modules.get("flask_cors") or types.ModuleType("flask_cors")
    flask_cors.CORS = lambda app, **kwargs: app
    sys.modules["flask_cors"] = flask_cors

    db_path = tmp_path / "otc_bridge.db"
    os.environ["OTC_DB_PATH"] = str(db_path)
    if cors_origins is None:
        os.environ.pop("OTC_CORS_ORIGINS", None)
    else:
        os.environ["OTC_CORS_ORIGINS"] = cors_origins

    module_path = Path(__file__).resolve().parents[1] / "otc-bridge" / "otc_bridge.py"
    spec = importlib.util.spec_from_file_location("otc_bridge_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.app.testing = True
    module.init_db()
    return module


def test_cors_defaults_to_restricted_public_origins(tmp_path):
    otc_bridge = load_otc_bridge(tmp_path)

    assert otc_bridge.OTC_CORS_ORIGINS == ["https://bottube.ai", "https://rustchain.org"]
    assert "*" not in otc_bridge.OTC_CORS_ORIGINS


def test_cors_env_ignores_wildcard_origin(tmp_path):
    otc_bridge = load_otc_bridge(
        tmp_path,
        cors_origins="*, https://trusted.example, http://localhost:3000",
    )

    assert otc_bridge.OTC_CORS_ORIGINS == [
        "https://trusted.example",
        "http://localhost:3000",
    ]


def test_orders_rejects_malformed_pagination(tmp_path):
    otc_bridge = load_otc_bridge(tmp_path)

    with otc_bridge.app.test_client() as client:
        limit_response = client.get("/api/orders?limit=abc")
        offset_response = client.get("/api/orders?offset=abc")

    assert limit_response.status_code == 400
    assert limit_response.get_json() == {"error": "limit_must_be_integer"}
    assert offset_response.status_code == 400
    assert offset_response.get_json() == {"error": "offset_must_be_integer"}


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
