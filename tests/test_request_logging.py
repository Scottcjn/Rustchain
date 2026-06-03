# SPDX-License-Identifier: MIT
import json
import sys
from unittest.mock import patch

import pytest


integrated_node = sys.modules["integrated_node"]


@pytest.fixture
def client():
    integrated_node.app.config["TESTING"] = True
    with integrated_node.app.test_client() as client:
        yield client


def test_after_request_emits_structured_request_log(client):
    with patch.object(integrated_node.app.logger, "info") as logger_info:
        response = client.get("/definitely-missing", headers={"X-Request-Id": "req-test-1"})

    assert response.status_code == 404
    assert response.headers["X-Request-Id"] == "req-test-1"
    logger_info.assert_called_once()

    payload = json.loads(logger_info.call_args.args[0])
    assert payload["req_id"] == "req-test-1"
    assert payload["method"] == "GET"
    assert payload["path"] == "/definitely-missing"
    assert payload["status"] == 404
    assert isinstance(payload["dur_ms"], int)
