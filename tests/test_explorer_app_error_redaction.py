import importlib.util
from pathlib import Path
from unittest.mock import Mock

import requests


def load_explorer_app():
    module_path = Path(__file__).resolve().parents[1] / "explorer" / "app.py"
    spec = importlib.util.spec_from_file_location("explorer_app_error_redaction_test", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.app.testing = True
    return module


def test_explorer_api_redacts_upstream_request_exceptions(monkeypatch):
    explorer_app = load_explorer_app()
    leaked = (
        "HTTPConnectionPool(host='127.0.0.1', port=8000): "
        "url=/api/miners?token=super-secret trace=/srv/rustchain/private/node.py"
    )
    logger_exception = Mock()

    def fail_request(*args, **kwargs):
        raise requests.exceptions.ConnectionError(leaked)

    monkeypatch.setattr(explorer_app.requests, "get", fail_request)
    monkeypatch.setattr(explorer_app.app.logger, "exception", logger_exception)

    with explorer_app.app.test_client() as client:
        responses = [
            client.get("/api/miners"),
            client.get("/api/network/stats"),
            client.get("/api/miner/alice"),
        ]

    for response in responses:
        assert response.status_code == 502
        body = response.get_json()
        assert body["error"] == "Upstream node unavailable"
        rendered = str(body)
        assert "127.0.0.1" not in rendered
        assert "super-secret" not in rendered
        assert "/srv/rustchain/private/node.py" not in rendered

    assert responses[0].get_json()["miners"] == []
    assert logger_exception.call_count == 3
