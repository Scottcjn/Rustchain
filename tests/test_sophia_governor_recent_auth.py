import sys
from pathlib import Path

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "node"))

from sophia_governor import (  # noqa: E402
    register_sophia_governor_endpoints,
    review_rustchain_event,
)


def _make_client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "governor.db")
    monkeypatch.setenv("RC_ADMIN_KEY", "expected-admin")
    monkeypatch.setenv("SOPHIA_GOVERNOR_ENABLE_LLM", "false")

    review_rustchain_event(
        event_type="pending_transfer",
        source="test-suite",
        payload={
            "amount_rtc": 25_000,
            "reason": "manual bridge override",
            "miner_id": "miner-sensitive",
        },
        db_path=db_path,
        auto_phone_home=False,
    )

    app = Flask(__name__)
    app.config["TESTING"] = True
    register_sophia_governor_endpoints(app, db_path=db_path)
    return app.test_client()


def test_governor_recent_requires_admin_key(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    missing = client.get("/sophia/governor/recent")
    wrong = client.get(
        "/sophia/governor/recent",
        headers={"X-Admin-Key": "wrong-admin"},
    )

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert missing.get_json()["error"] == "Unauthorized -- admin key required"
    assert wrong.get_json()["error"] == "Unauthorized -- admin key required"


def test_governor_recent_returns_events_with_admin_key(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    response = client.get(
        "/sophia/governor/recent",
        headers={"X-Admin-Key": "expected-admin"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert len(body["events"]) == 1
    assert body["events"][0]["source"] == "test-suite"
    assert body["events"][0]["risk_level"] == "critical"


def test_governor_recent_validates_limit_after_auth(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)

    unauthorized = client.get("/sophia/governor/recent?limit=bad")
    authorized = client.get(
        "/sophia/governor/recent?limit=bad",
        headers={"X-Admin-Key": "expected-admin"},
    )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 400
    assert authorized.get_json()["error"] == "limit must be an integer"
