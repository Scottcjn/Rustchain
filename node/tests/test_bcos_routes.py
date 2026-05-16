# SPDX-License-Identifier: MIT

import os
import sys

from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from bcos_routes import register_bcos_routes


def test_bcos_attest_rejects_non_object_json(tmp_path, monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin")
    app = Flask(__name__)
    register_bcos_routes(app, str(tmp_path / "bcos.db"))
    app.config["TESTING"] = True

    response = app.test_client().post(
        "/bcos/attest",
        headers={"X-Admin-Key": "test-admin"},
        json=["not", "an", "object"],
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "JSON object required"


def test_bcos_attest_rejects_non_object_report(tmp_path, monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin")
    app = Flask(__name__)
    register_bcos_routes(app, str(tmp_path / "bcos.db"))
    app.config["TESTING"] = True

    response = app.test_client().post(
        "/bcos/attest",
        headers={"X-Admin-Key": "test-admin"},
        json={"report": ["not", "an", "object"]},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "report must be an object"
