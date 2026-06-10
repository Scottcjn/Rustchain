# SPDX-License-Identifier: MIT
import tempfile

import pytest
from flask import Flask

import bottube_mood_engine as mood

MOOD_SIGNAL_KEY = "test-mood-signal-key"
MOOD_SIGNAL_HEADERS = {"X-Mood-Signal-Key": MOOD_SIGNAL_KEY}


@pytest.fixture
def client():
    app = Flask(__name__)
    db_file = tempfile.NamedTemporaryFile(delete=True)
    db_file.close()
    app.config["DB_PATH"] = db_file.name
    app.config[mood.MOOD_SIGNAL_API_KEY_ENV] = MOOD_SIGNAL_KEY
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
        headers=MOOD_SIGNAL_HEADERS,
        json={
            "signal_type": "video_views",
            "value": {"views": 1},
            "weight": weight,
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": error}


def test_mood_signal_accepts_numeric_weight(client):
    response = client.post(
        "/api/v1/agents/bot/mood/signal",
        headers=MOOD_SIGNAL_HEADERS,
        json={
            "signal_type": "video_views",
            "value": {"views": 1},
            "weight": 0.5,
        },
    )

    assert response.status_code == 200
    assert response.get_json()["agent_id"] == "bot"


def test_mood_signal_fails_closed_when_api_key_unconfigured(monkeypatch):
    monkeypatch.delenv(mood.MOOD_SIGNAL_API_KEY_ENV, raising=False)
    app = Flask(__name__)
    db_file = tempfile.NamedTemporaryFile(delete=True)
    db_file.close()
    app.config["DB_PATH"] = db_file.name
    app.register_blueprint(mood.mood_bp)

    response = app.test_client().post(
        "/api/v1/agents/bot/mood/signal",
        json={"signal_type": "video_views", "value": {"views": 1}},
    )

    assert response.status_code == 503
    assert response.get_json() == {"error": f"{mood.MOOD_SIGNAL_API_KEY_ENV} not configured"}


@pytest.mark.parametrize(
    "headers",
    (
        {},
        {"X-Mood-Signal-Key": "wrong-key"},
        {"X-API-Key": "wrong-key"},
        {"Authorization": "Bearer wrong-key"},
    ),
)
def test_mood_signal_rejects_missing_or_wrong_api_key(client, headers):
    response = client.post(
        "/api/v1/agents/bot/mood/signal",
        headers=headers,
        json={"signal_type": "video_views", "value": {"views": 1}},
    )

    assert response.status_code == 401
    assert response.get_json() == {"error": "Unauthorized"}


def test_mood_signal_accepts_bearer_api_key(client):
    response = client.post(
        "/api/v1/agents/bot/mood/signal",
        headers={"Authorization": f"Bearer {MOOD_SIGNAL_KEY}"},
        json={"signal_type": "video_views", "value": {"views": 1}},
    )

    assert response.status_code == 200
    assert response.get_json()["agent_id"] == "bot"
