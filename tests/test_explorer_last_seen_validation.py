# SPDX-License-Identifier: MIT
from unittest.mock import Mock, patch

from explorer.app import app as explorer_app


def _mock_miners_response(miner):
    response = Mock()
    response.status_code = 200
    response.json.return_value = {"miners": [miner]}
    return response


def test_miners_api_handles_invalid_last_seen_without_500():
    miner = {"id": "miner-bad-time", "last_seen": "not-a-timestamp"}

    with (
        explorer_app.test_client() as client,
        patch("explorer.app.requests.get", return_value=_mock_miners_response(miner)),
    ):
        response = client.get("/api/miners")

    assert response.status_code == 200
    body = response.get_json()
    assert body["miners"][0]["last_seen_formatted"] == "Unknown"
    assert body["miners"][0]["status"] == "unknown"


def test_miner_detail_handles_invalid_last_seen_without_500():
    miner = {"id": "miner-bad-time", "last_seen": "not-a-timestamp"}

    with (
        explorer_app.test_client() as client,
        patch("explorer.app.requests.get", return_value=_mock_miners_response(miner)),
    ):
        response = client.get("/api/miner/miner-bad-time")

    assert response.status_code == 200
    body = response.get_json()
    assert body["last_seen_formatted"] == "Unknown"
    assert body["status"] == "unknown"
