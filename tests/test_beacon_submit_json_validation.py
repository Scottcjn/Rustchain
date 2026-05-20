# SPDX-License-Identifier: MIT
import sys

import pytest


integrated_node = sys.modules["integrated_node"]


@pytest.fixture
def beacon_submit_client(monkeypatch):
    monkeypatch.setattr(integrated_node, "store_envelope", lambda *args, **kwargs: pytest.fail("store_envelope should not be called"))

    integrated_node.app.config["TESTING"] = True
    with integrated_node.app.test_client() as test_client:
        yield test_client


def test_beacon_submit_rejects_non_object_json_before_storage(beacon_submit_client):
    response = beacon_submit_client.post("/beacon/submit", json=["not", "an", "object"])

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "invalid_json"}
