# SPDX-License-Identifier: MIT

import os
import sys

from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import rewards_implementation_rip200 as rewards


def _app(tmp_path, monkeypatch):
    monkeypatch.setenv("RC_SETTLE_KEY", "test-settle")
    app = Flask(__name__)
    rewards.register_rewards_rip200(app, str(tmp_path / "rewards.db"))
    app.config["TESTING"] = True
    return app


def test_settle_rewards_rejects_non_object_json(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)

    response = app.test_client().post(
        "/rewards/settle",
        headers={"X-Admin-Key": "test-settle"},
        json=["not", "an", "object"],
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "JSON object required"


def test_settle_rewards_rejects_non_integer_epoch(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)

    response = app.test_client().post(
        "/rewards/settle",
        headers={"X-Admin-Key": "test-settle"},
        json={"epoch": "bad"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "epoch must be an integer"


def test_settle_rewards_rejects_object_epoch(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)

    response = app.test_client().post(
        "/rewards/settle",
        headers={"X-Admin-Key": "test-settle"},
        json={"epoch": {"value": 1}},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "epoch must be an integer"


def test_settle_rewards_rejects_negative_epoch(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)

    response = app.test_client().post(
        "/rewards/settle",
        headers={"X-Admin-Key": "test-settle"},
        json={"epoch": -1},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "epoch must be non-negative"


def test_settle_rewards_rejects_boolean_epoch(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)

    response = app.test_client().post(
        "/rewards/settle",
        headers={"X-Admin-Key": "test-settle"},
        json={"epoch": True},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "epoch must be an integer"
