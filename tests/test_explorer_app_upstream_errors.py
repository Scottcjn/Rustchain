import importlib.util
from pathlib import Path

import pytest
import requests


MODULE_PATH = Path(__file__).resolve().parents[1] / "explorer" / "app.py"


@pytest.fixture()
def explorer_app_module():
    spec = importlib.util.spec_from_file_location("explorer_app_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.app.config["TESTING"] = True
    return module


@pytest.mark.parametrize(
    ("route", "expected_extra"),
    [
        ("/api/miners", {"miners": []}),
        ("/api/network/stats", {}),
        ("/api/miner/alice", {}),
    ],
)
def test_upstream_connection_errors_do_not_leak_internal_details(
    explorer_app_module, monkeypatch, route, expected_extra
):
    sensitive_error = (
        "HTTPConnectionPool(host='127.0.0.1', port=8000): "
        "url=/api/miners?token=super-secret trace=/srv/rustchain/private/node.py"
    )

    def raise_sensitive_error(*args, **kwargs):
        raise requests.exceptions.ConnectionError(sensitive_error)

    monkeypatch.setattr(explorer_app_module.requests, "get", raise_sensitive_error)

    response = explorer_app_module.app.test_client().get(route)

    assert response.status_code == 500
    body = response.get_json()
    assert body == {"error": "Upstream node unavailable", **expected_extra}
    assert "127.0.0.1" not in str(body)
    assert "super-secret" not in str(body)
    assert "/srv/rustchain/private" not in str(body)
