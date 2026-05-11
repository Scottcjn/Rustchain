# SPDX-License-Identifier: MIT
import os
import sys


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import profile_badge_generator


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(profile_badge_generator, "DB_PATH", str(tmp_path / "badges.db"))
    profile_badge_generator.app.config["TESTING"] = True
    return profile_badge_generator.app.test_client()


def test_badge_create_rejects_non_object_json(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.post("/api/badge/create", data="null", content_type="application/json")

    assert response.status_code == 400
    assert response.get_json() == {"success": False, "error": "JSON object required"}


def test_badge_create_rejects_malformed_json(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.post("/api/badge/create", data="{", content_type="application/json")

    assert response.status_code == 400
    assert response.get_json() == {"success": False, "error": "JSON object required"}


def test_badge_create_preserves_valid_request(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/badge/create",
        json={
            "username": "cerredz",
            "wallet": "",
            "badge_type": "developer",
            "custom_message": "Audit Fixer",
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "markdown" in data
    assert "Audit%20Fixer" in data["shield_url"]
