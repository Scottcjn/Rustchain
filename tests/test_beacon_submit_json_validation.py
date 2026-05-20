# SPDX-License-Identifier: MIT
"""Regression coverage for /beacon/submit JSON body shape validation."""

import sys

import pytest


integrated_node = sys.modules["integrated_node"]


@pytest.fixture
def client():
    integrated_node.app.config["TESTING"] = True
    with integrated_node.app.test_client() as c:
        yield c


def test_beacon_submit_rejects_non_object_json(client):
    response = client.post("/beacon/submit", json=["not", "an", "object"])

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "invalid_json"}
