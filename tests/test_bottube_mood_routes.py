# SPDX-License-Identifier: MIT
import tempfile

import pytest
from flask import Flask

import bottube_mood_engine as mood

MOOD_SIGNAL_KEY = "mood-signal-secret"
MOOD_SIGNAL_HEADERS = {"X-BotTube-Mood-Key": MOOD_SIGNAL_KEY}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("BOTTUBE_MOOD_SIGNAL_KEY", MOOD_SIGNAL_KEY)
    monkeypatch.delenv("BOTTUBE_API_KEY", raising=False)
    app = Flask(__name__)
    db_file = tempfile.NamedTemporaryFile(delete=True)
    db_file.close()
    app.config["DB_PATH"] = db_file.name
    app.register_blueprint(mood.mood_bp)
    return app.test_client()


@pytest.mark.parametrize(
    ("weight", "error"),
    (
        (["bad"], "weight must be a number"),
        ("bad", "weight must be a number"),
        (True, "weight must be a number"),
    ),
)
def test_mood_signal_rejects_non_numeric_weight(client, weight, error):
    response = client.post(
        "/api/v1/agents/bot/mood/signal",
        json={
            "signal_type": "video_views",
            "value": {"views": 1},
            "weight": weight,
        },
        headers=MOOD_SIGNAL_HEADERS,
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": error}


def test_mood_signal_accepts_numeric_weight(client):
    response = client.post(
        "/api/v1/agents/bot/mood/signal",
        json={
            "signal_type": "video_views",
            "value": {"views": 1},
            "weight": 0.5,
        },
        headers=MOOD_SIGNAL_HEADERS,
    )

    assert response.status_code == 200
    assert response.get_json()["agent_id"] == "bot"


def test_mood_signal_fails_closed_when_key_unconfigured(client, monkeypatch):
    monkeypatch.delenv("BOTTUBE_MOOD_SIGNAL_KEY", raising=False)
    monkeypatch.delenv("BOTTUBE_API_KEY", raising=False)

    response = client.post(
        "/api/v1/agents/bot/mood/signal",
        json={"signal_type": "video_views", "value": {"views": 1}},
        headers=MOOD_SIGNAL_HEADERS,
    )

    assert response.status_code == 503
    assert response.get_json() == {"error": "BOTTUBE_MOOD_SIGNAL_KEY not configured"}
    assert client.get("/api/v1/agents/bot/mood/statistics").get_json()["signals_processed"] == 0


@pytest.mark.parametrize(
    "headers",
    (
        {},
        {"X-BotTube-Mood-Key": "wrong"},
        {"X-API-Key": "wrong"},
        {"Authorization": "Bearer wrong"},
        {"X-BotTube-Mood-Key": "\u00e9"},
    ),
)
def test_mood_signal_rejects_missing_or_wrong_key(client, headers):
    response = client.post(
        "/api/v1/agents/bot/mood/signal",
        json={"signal_type": "video_views", "value": {"views": 1}},
        headers=headers,
    )

    assert response.status_code == 401
    assert response.get_json() == {"error": "Unauthorized mood signal"}
    assert client.get("/api/v1/agents/bot/mood/statistics").get_json()["signals_processed"] == 0


@pytest.mark.parametrize(
    "headers",
    (
        {"X-BotTube-Mood-Key": MOOD_SIGNAL_KEY},
        {"X-API-Key": MOOD_SIGNAL_KEY},
        {"Authorization": f"Bearer {MOOD_SIGNAL_KEY}"},
    ),
)
def test_mood_signal_accepts_supported_auth_headers(client, headers):
    response = client.post(
        "/api/v1/agents/bot/mood/signal",
        json={"signal_type": "video_views", "value": {"views": 1}},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.get_json()["recent_signals_count"] == 1
