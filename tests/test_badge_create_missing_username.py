"""
Regression tests for badge create returning 400 when username is missing.
Issue: #6198 — POST /api/badge/create returned 200 with error body instead of 400.
"""
import sqlite3
import pytest
import profile_badge_generator as badges


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "badges_missing_username.db"
    monkeypatch.setattr(badges, "DB_PATH", str(db_path))
    badges.app.config["TESTING"] = True
    badges.init_badge_db()
    return badges.app.test_client()


class TestBadgeCreateMissingUsername:
    """POST /api/badge/create should return 400 when username is missing."""

    def test_missing_username_returns_400(self, client):
        """Request with no username field should return 400, not 200."""
        resp = client.post("/api/badge/create", json={
            "wallet": "RTCabc123",
            "badge_type": "contributor"
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["success"] is False
        assert "Username required" in data["error"]

    def test_blank_username_returns_400(self, client):
        """Request with empty username string should return 400."""
        resp = client.post("/api/badge/create", json={
            "username": "",
            "wallet": "RTCabc123",
            "badge_type": "contributor"
        })
        assert resp.status_code == 400

    def test_whitespace_username_returns_400(self, client):
        """Request with whitespace-only username should return 400."""
        resp = client.post("/api/badge/create", json={
            "username": "   ",
            "wallet": "RTCabc123",
            "badge_type": "contributor"
        })
        assert resp.status_code == 400

    def test_valid_username_returns_200(self, client):
        """Valid request with username should still return 200."""
        resp = client.post("/api/badge/create", json={
            "username": "testuser",
            "wallet": "RTCabc123",
            "badge_type": "contributor"
        })
        assert resp.status_code == 200
