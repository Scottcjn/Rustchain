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
