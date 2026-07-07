# SPDX-License-Identifier: MIT
import os
import tempfile

import pytest
from flask import Flask

import bottube_mood_engine as mood


@pytest.fixture
def client():
    app = Flask(__name__)
    db_file = tempfile.NamedTemporaryFile(delete=True)
    db_file.close()
    app.config["DB_PATH"] = db_file.name
    app.register_blueprint(mood.mood_bp)
    return app.test_client()


@pytest.fixture(autouse=True)
def _clear_env():
    """Ensure MOOD_SIGNAL_API_KEY is not set before each test."""
    saved = os.environ.pop(mood.MOOD_SIGNAL_API_KEY_ENV, None)
    yield
    if saved is not None:
        os.environ[mood.MOOD_SIGNAL_API_KEY_ENV] = saved


# ── Auth tests ──────────────────────────────────────────────────────────── #


def test_mood_signal_rejects_when_key_not_configured(client):
    """Fail-closed: no env var → 503."""
    os.environ.pop(mood.MOOD_SIGNAL_API_KEY_ENV, None)  # ensure absent

    response = client.post(
        "/api/v1/agents/bot/mood/signal",
        json={"signal_type": "video_views", "value": {"views": 1}},
    )
    assert response.status_code == 503
    assert response.get_json() == {"error": "Mood signal API key not configured"}


def test_mood_signal_rejects_missing_header(client):
    """Key configured but no header → 401."""
    os.environ[mood.MOOD_SIGNAL_API_KEY_ENV] = "test-secret"

    response = client.post(
        "/api/v1/agents/bot/mood/signal",
        json={"signal_type": "video_views", "value": {"views": 1}},
    )
    assert response.status_code == 401
    assert response.get_json() == {"error": "X-Api-Key header required for mood signal writes"}


def test_mood_signal_rejects_bad_key(client):
    """Key configured, wrong header value → 403."""
    os.environ[mood.MOOD_SIGNAL_API_KEY_ENV] = "test-secret"

    response = client.post(
        "/api/v1/agents/bot/mood/signal",
        headers={"X-Api-Key": "wrong-key"},
        json={"signal_type": "video_views", "value": {"views": 1}},
    )
    assert response.status_code == 403
    assert response.get_json() == {"error": "Invalid mood signal API key"}


def test_mood_signal_accepts_valid_key(client):
    """Correct key → 200."""
    os.environ[mood.MOOD_SIGNAL_API_KEY_ENV] = "test-secret"

    response = client.post(
        "/api/v1/agents/bot/mood/signal",
        headers={"X-Api-Key": "test-secret"},
        json={"signal_type": "video_views", "value": {"views": 1}},
    )
    assert response.status_code == 200
    assert response.get_json()["agent_id"] == "bot"


# ── Public endpoints (no auth) ──────────────────────────────────────────── #


def test_mood_signal_rejects_non_numeric_weight(client):
    os.environ[mood.MOOD_SIGNAL_API_KEY_ENV] = "test-secret"

    for weight, error in (
        (["bad"], "weight must be a number"),
        ("bad", "weight must be a number"),
        (True, "weight must be a number"),
    ):
        response = client.post(
            "/api/v1/agents/bot/mood/signal",
            headers={"X-Api-Key": "test-secret"},
            json={"signal_type": "video_views", "value": {"views": 1}, "weight": weight},
        )
        assert response.status_code == 400
        assert response.get_json() == {"error": error}


def test_mood_get_requires_no_auth(client):
    """GET /mood is read-only and does NOT require auth."""
    response = client.get("/api/v1/agents/bot/mood")
    assert response.status_code in (200, 500)  # 500 = mood service unavailable (no DB)


def test_mood_title_requires_no_auth(client):
    """POST /mood/title is read-only and does NOT require auth."""
    response = client.post(
        "/api/v1/agents/bot/mood/title",
        json={"topic": "test"},
    )
    assert response.status_code in (200, 500)
