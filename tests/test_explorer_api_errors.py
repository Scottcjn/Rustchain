import json
from unittest.mock import patch

import pytest
import requests

from explorer.app import app as explorer_app


@pytest.mark.parametrize(
    ("endpoint", "expects_miners_fallback"),
    [
        ("/api/miners", True),
        ("/api/network/stats", False),
        ("/api/miner/miner-001", False),
    ],
)
def test_explorer_api_hides_upstream_connection_details(
    endpoint,
    expects_miners_fallback,
):
    sensitive_error = (
        "HTTPConnectionPool(host='127.0.0.1', port=8000): "
        "url=/api/miners?token=super-secret "
        "trace=/srv/rustchain/private/node.py"
    )

    with (
        explorer_app.test_client() as client,
        patch("explorer.app.requests.get") as mock_get,
    ):
        mock_get.side_effect = requests.exceptions.ConnectionError(sensitive_error)
        response = client.get(endpoint)

    assert response.status_code == 500
    body = response.get_json()
    assert body["error"] == "Upstream node unavailable"
    if expects_miners_fallback:
        assert body["miners"] == []

    serialized_body = json.dumps(body)
    assert "127.0.0.1" not in serialized_body
    assert "super-secret" not in serialized_body
    assert "/srv/rustchain/private" not in serialized_body
