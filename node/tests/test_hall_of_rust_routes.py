# SPDX-License-Identifier: MIT

import os
import sys

from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from hall_of_rust import hall_bp


def _client():
    app = Flask(__name__)
    app.register_blueprint(hall_bp)
    app.config["TESTING"] = True
    return app.test_client()


def test_hall_induct_rejects_non_object_json():
    response = _client().post("/hall/induct", json=["not", "an", "object"])

    assert response.status_code == 400
    assert response.get_json()["error"] == "JSON object required"


def test_hall_eulogy_rejects_non_object_json():
    response = _client().post("/hall/eulogy/deadbeef", json=["nickname"])

    assert response.status_code == 400
    assert response.get_json()["error"] == "JSON object required"
