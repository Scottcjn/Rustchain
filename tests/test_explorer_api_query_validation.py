import importlib.util
import sys
import types
from pathlib import Path


def load_explorer_api():
    if "flask_cors" not in sys.modules:
        flask_cors = types.ModuleType("flask_cors")
        flask_cors.CORS = lambda app: app
        sys.modules["flask_cors"] = flask_cors

    module_path = Path(__file__).resolve().parents[1] / "tools" / "explorer-api" / "api.py"
    spec = importlib.util.spec_from_file_location("explorer_api_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.app.testing = True
    module._cache.clear()
    return module


def test_blocks_rejects_non_integer_pagination_params():
    explorer_api = load_explorer_api()

    with explorer_api.app.test_client() as client:
        page_response = client.get("/api/blocks?page=abc")
        limit_response = client.get("/api/blocks?limit=abc")

    assert page_response.status_code == 400
    assert page_response.get_json() == {"ok": False, "error": "page_must_be_integer"}
    assert limit_response.status_code == 400
    assert limit_response.get_json() == {"ok": False, "error": "limit_must_be_integer"}


def test_blocks_rejects_non_positive_pagination_params():
    explorer_api = load_explorer_api()

    with explorer_api.app.test_client() as client:
        page_response = client.get("/api/blocks?page=0")
        limit_response = client.get("/api/blocks?limit=-5")

    assert page_response.status_code == 400
    assert page_response.get_json() == {"ok": False, "error": "page_must_be_positive"}
    assert limit_response.status_code == 400
    assert limit_response.get_json() == {"ok": False, "error": "limit_must_be_positive"}


def test_blocks_caps_valid_limit_without_contacting_invalid_input_path(monkeypatch):
    explorer_api = load_explorer_api()

    def fake_get(path, params=None, timeout=None):
        assert path == "/headers/tip"
        return {"slot": 5, "miner": "alice", "tip_age": 7}

    monkeypatch.setattr(explorer_api, "_get", fake_get)

    with explorer_api.app.test_client() as client:
        response = client.get("/api/blocks?page=1&limit=500")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["limit"] == 100
    assert payload["page"] == 1


def test_transactions_rejects_bad_limit_params():
    explorer_api = load_explorer_api()

    with explorer_api.app.test_client() as client:
        non_integer_response = client.get("/api/transactions?limit=abc")
        negative_response = client.get("/api/transactions?limit=-1")

    assert non_integer_response.status_code == 400
    assert non_integer_response.get_json() == {
        "ok": False,
        "error": "limit_must_be_integer",
    }
    assert negative_response.status_code == 400
    assert negative_response.get_json() == {
        "ok": False,
        "error": "limit_must_be_positive",
    }


def test_transactions_caps_valid_limit(monkeypatch):
    explorer_api = load_explorer_api()

    def fake_get(path, params=None, timeout=None):
        if path == "/api/stats":
            return {"pending_withdrawals": 3}
        if path == "/api/fee_pool":
            return {"amount_rtc": 1.25}
        raise AssertionError(f"unexpected upstream path: {path}")

    monkeypatch.setattr(explorer_api, "_get", fake_get)

    with explorer_api.app.test_client() as client:
        response = client.get("/api/transactions?limit=500")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["limit"] == 100
    assert payload["pending_withdrawals"] == 3
