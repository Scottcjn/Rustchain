import importlib.util
from pathlib import Path

import pytest
import requests


def load_explorer_app():
    module_path = Path(__file__).resolve().parents[1] / "explorer" / "app.py"
    spec = importlib.util.spec_from_file_location("explorer_app_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.app.testing = True
    return module


@pytest.mark.parametrize(
    ("path", "expected_payload"),
    [
        ("/api/miners", {"error": "Upstream RustChain API unavailable", "miners": []}),
        ("/api/network/stats", {"error": "Upstream RustChain API unavailable"}),
        ("/api/miner/alice", {"error": "Upstream RustChain API unavailable"}),
    ],
)
def test_explorer_api_hides_upstream_exception_details(monkeypatch, path, expected_payload):
    explorer_app = load_explorer_app()
    leaked_error = (
        "HTTPConnectionPool(host='127.0.0.1', port=8000): "
        "url=/api/miners?token=super-secret trace=/srv/rustchain/private/node.py"
    )

    def fail_upstream(*args, **kwargs):
        raise requests.exceptions.ConnectionError(leaked_error)

    monkeypatch.setattr(explorer_app.requests, "get", fail_upstream)

    with explorer_app.app.test_client() as client:
        response = client.get(path)

    assert response.status_code == 500
    assert response.get_json() == expected_payload

    response_text = response.get_data(as_text=True)
    for secret in ("127.0.0.1", "8000", "super-secret", "/srv/rustchain/private", "node.py"):
        assert secret not in response_text
