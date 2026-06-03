# SPDX-License-Identifier: MIT

import sqlite3

import pytest

import profile_badge_generator as badges


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "badges.db"
    monkeypatch.setattr(badges, "DB_PATH", str(db_path))
    badges.app.config["TESTING"] = True
    badges.init_badge_db()
    return badges.app.test_client()


def _badge_count():
    with sqlite3.connect(badges.DB_PATH) as conn:
        return conn.execute("SELECT COUNT(*) FROM profile_badges").fetchone()[0]


@pytest.mark.parametrize("payload", ["null", '["not", "an", "object"]', "{"])
def test_create_badge_rejects_bad_json_bodies(client, payload):
    response = client.post(
        "/api/badge/create",
        data=payload,
        content_type="application/json",
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert _badge_count() == 0


def test_create_badge_accepts_valid_json_object(client):
    response = client.post(
        "/api/badge/create",
        json={
            "username": "jamilahmadzai",
            "wallet": "RTCd1acb2189e9f36df2b5393c3c27a867c3c32b116",
            "badge_type": "bounty-hunter",
            "custom_message": "Bug Hunter",
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "Bug%20Hunter" in data["shield_url"]
    assert _badge_count() == 1


@pytest.mark.parametrize(
    ("field", "value", "expected_error"),
    [
        ("username", ["not", "text"], "username must be a string"),
        ("wallet", {"address": "RTCstructured"}, "wallet must be a string"),
        ("badge_type", ["developer"], "badge_type must be a string"),
        ("custom_message", {"label": "Bug Hunter"}, "custom_message must be a string"),
    ],
)
def test_create_badge_rejects_non_string_fields(client, field, value, expected_error):
    payload = {
        "username": "jasperdevs",
        "wallet": "RTCe361734a691c56c825af0faba890807c05fa35ef",
        "badge_type": "bounty-hunter",
        "custom_message": "Bug Hunter",
    }
    payload[field] = value

    response = client.post("/api/badge/create", json=payload)

    assert response.status_code == 400
    assert response.get_json() == {"success": False, "error": expected_error}
    assert _badge_count() == 0


def test_create_badge_updates_existing_github_username(client):
    first = client.post(
        "/api/badge/create",
        json={
            "username": "dupuser",
            "wallet": "RTCfirst",
            "badge_type": "contributor",
            "custom_message": "One",
        },
    )
    second = client.post(
        "/api/badge/create",
        json={
            "username": "dupuser",
            "wallet": "RTCsecond",
            "badge_type": "developer",
            "custom_message": "Two",
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    stats = client.get("/api/badge/stats").get_json()
    listing = client.get("/api/badge/list").get_json()["badges"]

    assert stats["total_badges"] == 1
    assert stats["total_bounties_earned"] == 3.0
    assert len(listing) == 1
    assert listing[0]["username"] == "dupuser"
    assert listing[0]["type"] == "developer"
    assert listing[0]["custom_message"] == "Two"
