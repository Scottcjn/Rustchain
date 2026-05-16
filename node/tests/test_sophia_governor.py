import gc
import os
import sqlite3
import tempfile
import time
import types

import pytest
from flask import Flask

import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import sophia_governor
from sophia_governor import (
    ROUTE_IMMEDIATE_PHONE_HOME,
    ROUTE_LOCAL_ONLY,
    get_governor_event,
    get_governor_status,
    get_recent_governor_events,
    init_sophia_governor_schema,
    register_sophia_governor_endpoints,
    review_rustchain_event,
)


@pytest.fixture(autouse=True)
def governor_env(monkeypatch):
    monkeypatch.setenv("SOPHIA_GOVERNOR_ENABLE_LLM", "0")
    monkeypatch.delenv("SOPHIA_GOVERNOR_PHONE_HOME_TARGETS", raising=False)
    monkeypatch.delenv("SOPHIA_GOVERNOR_PHONE_HOME_URLS", raising=False)
    monkeypatch.delenv("SOPHIA_GOVERNOR_PHONE_HOME_BEARER", raising=False)
    monkeypatch.delenv("SOPHIA_GOVERNOR_BEACON_MESSAGE_URL", raising=False)


@pytest.fixture
def tmp_db(tmp_path):
    db_path = str(tmp_path / "governor.db")
    init_sophia_governor_schema(db_path)
    yield db_path
    for _ in range(5):
        try:
            os.unlink(db_path)
            break
        except PermissionError:
            gc.collect()
            time.sleep(0.05)


@pytest.fixture
def app(tmp_db, monkeypatch):
    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin")
    app = Flask(__name__)
    register_sophia_governor_endpoints(app, tmp_db)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_low_risk_governance_stays_local(tmp_db):
    result = review_rustchain_event(
        event_type="governance_proposal",
        source="pytest",
        payload={
            "title": "Polish the governance UI copy",
            "description": "Clarify wording for proposal lifecycle text only.",
        },
        db_path=tmp_db,
    )

    assert result["route"] == ROUTE_LOCAL_ONLY
    assert result["risk_level"] == "low"
    assert result["stance"] == "allow"
    assert result["escalation"]["status"] == "not_needed"

    stored = get_governor_event(result["event_id"], db_path=tmp_db)
    assert stored is not None
    assert stored["event_type"] == "governance_proposal"


def test_critical_governance_proposal_escalates_without_targets(tmp_db):
    result = review_rustchain_event(
        event_type="governance_proposal",
        source="pytest",
        payload={
            "title": "Emergency freeze bridge withdrawals",
            "description": "Override the bridge guardrails and mint supply if needed.",
        },
        db_path=tmp_db,
    )

    assert result["route"] == ROUTE_IMMEDIATE_PHONE_HOME
    assert result["risk_level"] == "critical"
    assert result["needs_escalation"] is True
    assert result["escalation"]["status"] == "not_configured"


def test_phone_home_delivery_records_attempt(tmp_db, monkeypatch):
    calls = []

    class DummyResponse:
        status_code = 202
        text = "accepted"

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append(
            {
                "url": url,
                "json": json,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return DummyResponse()

    monkeypatch.setenv("SOPHIA_GOVERNOR_PHONE_HOME_TARGETS", "https://example.com/sophia")
    monkeypatch.setattr(
        "sophia_governor.requests",
        types.SimpleNamespace(post=fake_post),
        raising=False,
    )

    result = review_rustchain_event(
        event_type="pending_transfer",
        source="pytest",
        payload={"amount_rtc": 2500, "reason": "manual bridge override"},
        db_path=tmp_db,
    )

    assert result["needs_escalation"] is True
    assert result["escalation"]["status"] == "delivered"
    assert calls
    assert calls[0]["url"] == "https://example.com/sophia"

    with sqlite3.connect(tmp_db) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM sophia_governor_phone_home WHERE event_id = ?",
            (result["event_id"],),
        ).fetchone()
    assert row[0] == 1


def test_inbox_url_fallback_is_used_for_phone_home(tmp_db, monkeypatch):
    calls = []

    class DummyResponse:
        status_code = 202
        text = "accepted"

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append(url)
        return DummyResponse()

    monkeypatch.setenv("SOPHIA_GOVERNOR_INBOX_URL", "https://example.com/api/sophia/governor/ingest")
    monkeypatch.setattr(
        "sophia_governor.requests",
        types.SimpleNamespace(post=fake_post),
        raising=False,
    )

    result = review_rustchain_event(
        event_type="pending_transfer",
        source="pytest",
        payload={"amount_rtc": 1500, "reason": "manual review"},
        db_path=tmp_db,
    )

    assert result["escalation"]["status"] == "delivered"
    assert calls == ["https://example.com/api/sophia/governor/ingest"]


def test_governor_endpoints_require_admin_for_manual_review(client):
    response = client.post(
        "/sophia/governor/review",
        json={
            "event_type": "pending_transfer",
            "payload": {"amount_rtc": 50},
        },
    )
    assert response.status_code == 401


def test_governor_admin_auth_uses_constant_time_compare(client, monkeypatch):
    """Admin-gated governor endpoints compare configured keys with hmac.compare_digest."""
    calls = []

    def spy_compare_digest(provided, expected):
        calls.append((provided, expected))
        return provided == expected

    monkeypatch.setattr(sophia_governor.hmac, "compare_digest", spy_compare_digest)

    denied = client.post(
        "/sophia/governor/review",
        headers={"X-Admin-Key": "wrong-admin"},
        json={
            "event_type": "pending_transfer",
            "payload": {"amount_rtc": 50},
        },
    )
    assert denied.status_code == 401

    accepted_admin_header = client.post(
        "/sophia/governor/review",
        headers={"X-Admin-Key": "test-admin"},
        json={
            "event_type": "governance_proposal",
            "source": "pytest.admin",
            "payload": {"title": "routine review"},
        },
    )
    assert accepted_admin_header.status_code == 200

    accepted_api_header = client.post(
        "/sophia/governor/review",
        headers={"X-API-Key": "test-admin"},
        json={
            "event_type": "pending_transfer",
            "source": "pytest.manual",
            "payload": {"amount_rtc": 50},
        },
    )
    assert accepted_api_header.status_code == 200

    assert calls == [
        ("wrong-admin", "test-admin"),
        ("test-admin", "test-admin"),
        ("test-admin", "test-admin"),
    ]


def test_governor_endpoints_report_status_and_recent(client):
    review = client.post(
        "/sophia/governor/review",
        headers={"X-Admin-Key": "test-admin"},
        json={
            "event_type": "pending_transfer",
            "source": "pytest.manual",
            "payload": {"amount_rtc": 1200, "reason": "manual review"},
        },
    )
    assert review.status_code == 200
    review_body = review.get_json()
    assert review_body["ok"] is True

    status = client.get("/sophia/governor/status")
    assert status.status_code == 200
    status_body = status.get_json()
    assert status_body["service"] == "sophia-rustchain-governor"
    assert status_body["totals"]["events"] >= 1

    recent = client.get("/sophia/governor/recent?limit=5")
    assert recent.status_code == 200
    recent_body = recent.get_json()
    assert recent_body["ok"] is True
    assert len(recent_body["events"]) >= 1


def test_governor_status_helpers(tmp_db):
    review_rustchain_event(
        event_type="attestation_verdict",
        source="pytest",
        payload={"verdict": "CAUTIOUS", "miner": "g4-1"},
        db_path=tmp_db,
    )

    status = get_governor_status(tmp_db)
    recent = get_recent_governor_events(tmp_db, limit=5)

    assert status["status"] == "ok"
    assert status["totals"]["events"] == 1
    assert recent[0]["event_type"] == "attestation_verdict"
