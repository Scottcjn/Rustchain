# SPDX-License-Identifier: MIT

import sys

import pytest

integrated_node = sys.modules["integrated_node"]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", "0" * 32)
    integrated_node.app.config["TESTING"] = True
    with integrated_node.app.test_client() as test_client:
        yield test_client


def test_integrated_rewards_settle_rejects_non_object_json(client):
    response = client.post(
        "/rewards/settle",
        headers={"X-Admin-Key": "0" * 32},
        json=["not", "an", "object"],
    )

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "JSON object required"}


@pytest.mark.parametrize("epoch", ["bad", True, {"value": 1}])
def test_integrated_rewards_settle_rejects_non_integer_epoch(client, epoch):
    response = client.post(
        "/rewards/settle",
        headers={"X-Admin-Key": "0" * 32},
        json={"epoch": epoch},
    )

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "epoch must be an integer"}
