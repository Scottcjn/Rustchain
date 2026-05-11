import gc
import os
import tempfile
import time

import pytest
from flask import Flask

import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import sophia_governor_inbox
from sophia_governor_inbox import (
    get_governor_inbox_entry,
    get_governor_inbox_status,
    ingest_governor_envelope,
    init_sophia_governor_inbox_schema,
    list_governor_inbox_entries,
    register_sophia_governor_inbox_endpoints,
)


@pytest.fixture
def tmp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as handle:
        db_path = handle.name
    init_sophia_governor_inbox_schema(db_path)
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
    monkeypatch.delenv("SOPHIA_GOVERNOR_INBOX_BEARER", raising=False)
    monkeypatch.delenv("SOPHIA_GOVERNOR_INBOX_FORWARD_TARGETS", raising=False)
    monkeypatch.delenv("SOPHIA_GOVERNOR_INBOX_FORWARD_URLS", raising=False)
    monkeypatch.delenv("SOPHIA_GOVERNOR_INBOX_AUTO_FORWARD", raising=False)
    monkeypatch.delenv("SOPHIA_GOVERNOR_SCOTT_NOTIFY_QUEUE_URL", raising=False)
    monkeypatch.delenv("SCOTT_NOTIFICATION_QUEUE_URL", raising=False)
    monkeypatch.delenv("SOPHIA_GOVERNOR_SCOTT_NOTIFY_BEARER", raising=False)
    monkeypatch.delenv("SCOTT_NOTIFICATION_SERVICE_TOKEN", raising=False)
    app = Flask(__name__)
    register_sophia_governor_inbox_endpoints(app, tmp_db)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _sample_envelope():
    return {
        "event_id": 42,
        "event_type": "pending_transfer",
        "source": "wallet.transfer",
        "created_at": 1_774_000_000,
        "decision": {
            "risk_level": "high",
            "stance": "watch",
            "route": "local_then_phone_home",
            "local_summary": "Pending transfer reviewed at high risk.",
        },
        "payload": {
            "amount_rtc": 2500,
            "reason": "manual bridge override",
            "from_miner": "g4-alpha",
            "to_miner": "node2-hot-wallet",
        },
        "continuity": {
            "loaded": True,
            "topic": "RustChain governance",
            "bootstrap_block": "Sophia protects RustChain first.",
        },
        "governor": {
            "agent": "sophia-rustchain-governor",
            "instance": "node-1",
        },
    }


def test_ingest_helper_persists_and_deduplicates(tmp_db):
    first = ingest_governor_envelope(_sample_envelope(), db_path=tmp_db)
    second = ingest_governor_envelope(_sample_envelope(), db_path=tmp_db)

    assert first["accepted"] is True
    assert first["duplicate"] is False
    assert second["accepted"] is True
    assert second["duplicate"] is True
    assert second["inbox"]["inbox_id"] == first["inbox"]["inbox_id"]

    entry = get_governor_inbox_entry(first["inbox"]["inbox_id"], db_path=tmp_db)
    assert entry is not None
    assert entry["risk_level"] == "high"
    assert entry["status"] == "received"


def test_ingest_endpoint_requires_admin(client):
    response = client.post("/api/sophia/governor/ingest", json=_sample_envelope())
    assert response.status_code == 401


def test_admin_auth_uses_constant_time_compare(client, monkeypatch):
    """Admin-gated inbox endpoints compare configured keys with hmac.compare_digest."""
    calls = []

    def spy_compare_digest(provided, expected):
        calls.append((provided, expected))
        return provided == expected

    monkeypatch.setattr(sophia_governor_inbox.hmac, "compare_digest", spy_compare_digest)

    denied = client.post(
        "/api/sophia/governor/ingest",
        headers={"X-Admin-Key": "wrong-admin"},
        json=_sample_envelope(),
    )
    assert denied.status_code == 401

    accepted = client.post(
        "/api/sophia/governor/ingest",
        headers={"X-API-Key": "test-admin"},
        json=_sample_envelope(),
    )
    assert accepted.status_code == 202

    assert calls == [
        ("wrong-admin", "test-admin"),
        ("test-admin", "test-admin"),
    ]


def test_ingest_and_list_endpoints(client):
    response = client.post(
        "/api/sophia/governor/ingest",
        headers={"X-Admin-Key": "test-admin"},
        json=_sample_envelope(),
    )
    assert response.status_code == 202
    body = response.get_json()
    assert body["ok"] is True
    inbox_id = body["inbox"]["inbox_id"]

    listing = client.get(
        "/api/sophia/governor/inbox?limit=5&risk_level=high",
        headers={"X-Admin-Key": "test-admin"},
    )
    assert listing.status_code == 200
    listing_body = listing.get_json()
    assert listing_body["ok"] is True
    assert len(listing_body["entries"]) == 1
    assert listing_body["entries"][0]["inbox_id"] == inbox_id

    detail = client.get(
        f"/api/sophia/governor/inbox/{inbox_id}",
        headers={"X-Admin-Key": "test-admin"},
    )
    assert detail.status_code == 200
    detail_body = detail.get_json()
    assert detail_body["entry"]["remote_instance"] == "node-1"


def test_update_status_endpoint(client):
    ingest = client.post(
        "/api/sophia/governor/ingest",
        headers={"X-Admin-Key": "test-admin"},
        json=_sample_envelope(),
    )
    inbox_id = ingest.get_json()["inbox"]["inbox_id"]

    updated = client.post(
        f"/api/sophia/governor/inbox/{inbox_id}/status",
        headers={"X-Admin-Key": "test-admin"},
        json={
            "status": "reviewing",
            "assigned_agent": "elya-codex-xhigh",
            "review_notes": "Escalated for bigger-agent review.",
            "recommended_resolution": {
                "target_inbox_status": "resolved",
                "resolution_type": "watch",
                "requires_human": True,
                "auto_apply": False,
                "operator_action": "Keep the event under watch until manual confirmation.",
                "summary": "Pending transfer needs operator review.",
            },
        },
    )
    assert updated.status_code == 200
    updated_body = updated.get_json()
    assert updated_body["entry"]["status"] == "reviewing"
    assert updated_body["entry"]["assigned_agent"] == "elya-codex-xhigh"
    assert updated_body["entry"]["recommended_resolution"]["target_inbox_status"] == "resolved"
    assert updated_body["entry"]["recommended_resolution"]["resolution_type"] == "watch"


def test_status_helper_reports_totals(tmp_db):
    ingest_governor_envelope(_sample_envelope(), db_path=tmp_db)
    status = get_governor_inbox_status(tmp_db)
    entries = list_governor_inbox_entries(tmp_db, limit=5)

    assert status["service"] == "sophia-governor-inbox"
    assert status["totals"]["entries"] == 1
    assert entries[0]["event_type"] == "pending_transfer"


def test_status_helper_includes_review_relay_health(tmp_db, monkeypatch):
    class DummyResponse:
        status_code = 200
        text = '{"service":"sophia-governor-review-service","model":"glm-4.7-flash:latest","totals":{"reviews":4}}'

        def json(self):
            return {
                "service": "sophia-governor-review-service",
                "model": "glm-4.7-flash:latest",
                "totals": {"reviews": 4},
                "auth": {"bearer_configured": True},
            }

    def fake_get(url, headers=None, timeout=None):
        assert url == "http://127.0.0.1:18091/api/sophia/governor/health"
        return DummyResponse()

    monkeypatch.setenv("SOPHIA_GOVERNOR_INBOX_FORWARD_TARGETS", "http://127.0.0.1:18091/api/sophia/governor/review")
    monkeypatch.setattr(
        "sophia_governor_inbox.requests",
        type("DummyRequests", (), {"get": staticmethod(fake_get)}),
        raising=False,
    )

    status = get_governor_inbox_status(tmp_db)

    assert status["review_relay"]["configured"] is True
    assert status["review_relay"]["reachable"] is True
    assert status["review_relay"]["service"] == "sophia-governor-review-service"
    assert status["review_relay"]["totals"]["reviews"] == 4


def test_ingest_can_queue_scott_notification(client, monkeypatch):
    calls = []

    class DummyResponse:
        status_code = 200

        def json(self):
            return {"status": "ok", "notification": {"notification_id": "SN-GOV-INBOX-1"}}

        text = '{"status":"ok","notification":{"notification_id":"SN-GOV-INBOX-1"}}'

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return DummyResponse()

    monkeypatch.setenv("SOPHIA_GOVERNOR_SCOTT_NOTIFY_QUEUE_URL", "https://example.com/scott-notifications/queue")
    monkeypatch.setenv("SCOTT_NOTIFICATION_SERVICE_TOKEN", "relay-token")
    monkeypatch.setattr(
        "sophia_governor_inbox.requests",
        type("DummyRequests", (), {"post": staticmethod(fake_post)}),
        raising=False,
    )

    response = client.post(
        "/api/sophia/governor/ingest",
        headers={"X-Admin-Key": "test-admin"},
        json=_sample_envelope(),
    )
    assert response.status_code == 202
    body = response.get_json()
    assert body["scott_notification"]["status"] == "queued"
    assert body["scott_notification"]["notification_id"] == "SN-GOV-INBOX-1"
    assert calls[0]["url"] == "https://example.com/scott-notifications/queue"
    assert calls[0]["headers"]["Authorization"] == "Bearer relay-token"
    assert calls[0]["json"]["related_type"] == "rustchain_governor_inbox"
    assert calls[0]["json"]["related_id"] == str(body["inbox"]["inbox_id"])


def test_ingest_does_not_queue_scott_notification_without_token(client, monkeypatch):
    calls = []

    def fake_post(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        raise AssertionError("notification queue should not be called without a token")

    monkeypatch.setenv("SOPHIA_GOVERNOR_SCOTT_NOTIFY_QUEUE_URL", "https://example.com/scott-notifications/queue")
    monkeypatch.delenv("SCOTT_NOTIFICATION_SERVICE_TOKEN", raising=False)
    monkeypatch.delenv("SOPHIA_GOVERNOR_SCOTT_NOTIFY_BEARER", raising=False)
    monkeypatch.setattr(
        "sophia_governor_inbox.requests",
        type("DummyRequests", (), {"post": staticmethod(fake_post)}),
        raising=False,
    )

    response = client.post(
        "/api/sophia/governor/ingest",
        headers={"X-Admin-Key": "test-admin"},
        json=_sample_envelope(),
    )

    assert response.status_code == 202
    body = response.get_json()
    assert body["scott_notification"]["status"] == "token_not_configured"
    assert calls == []


def test_manual_forward_endpoint_records_attempt(client, monkeypatch):
    calls = []

    class ReviewResponse:
        status_code = 202
        text = (
            '{"service":"sophia-governor-review-service","review":"Assessment: hold. Risk: high. '
            'Next step: escalate.","recommended_resolution":{"target_inbox_status":"resolved",'
            '"resolution_type":"escalate","requires_human":true,"auto_apply":false,'
            '"operator_action":"Escalate immediately and require a human decision before confirmation.",'
            '"summary":"Large manual bridge override requested."}}'
        )

        def json(self):
            return {
                "service": "sophia-governor-review-service",
                "review": "Assessment: hold. Risk: high. Next step: escalate.",
                "recommended_resolution": {
                    "target_inbox_status": "resolved",
                    "resolution_type": "escalate",
                    "requires_human": True,
                    "auto_apply": False,
                    "operator_action": "Escalate immediately and require a human decision before confirmation.",
                    "summary": "Large manual bridge override requested.",
                },
            }

    class ScottResponse:
        status_code = 200
        text = '{"status":"ok","notification":{"notification_id":"SN-GOV-REVIEW-1"}}'

        def json(self):
            return {"status": "ok", "notification": {"notification_id": "SN-GOV-REVIEW-1"}}

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        if url.endswith("/sophia/review"):
            return ReviewResponse()
        return ScottResponse()

    monkeypatch.setenv("SOPHIA_GOVERNOR_INBOX_FORWARD_TARGETS", "https://example.com/sophia/review")
    monkeypatch.setenv("SOPHIA_GOVERNOR_SCOTT_NOTIFY_QUEUE_URL", "https://example.com/scott-notifications/queue")
    monkeypatch.setenv("SCOTT_NOTIFICATION_SERVICE_TOKEN", "relay-token")
    monkeypatch.setattr(
        "sophia_governor_inbox.requests",
        type("DummyRequests", (), {"post": staticmethod(fake_post)}),
        raising=False,
    )

    ingest = client.post(
        "/api/sophia/governor/ingest",
        headers={"X-Admin-Key": "test-admin"},
        json=_sample_envelope(),
    )
    inbox_id = ingest.get_json()["inbox"]["inbox_id"]

    forward = client.post(
        f"/api/sophia/governor/inbox/{inbox_id}/forward",
        headers={"X-Admin-Key": "test-admin"},
        json={},
    )
    assert forward.status_code == 200
    body = forward.get_json()
    assert body["result"]["status"] == "delivered"
    assert calls[0]["url"] == "https://example.com/scott-notifications/queue"
    assert calls[1]["url"] == "https://example.com/sophia/review"
    assert calls[2]["url"] == "https://example.com/scott-notifications/queue"
    assert body["entry"]["status"] == "forwarded"
    assert body["entry"]["assigned_agent"] == "sophia-governor-review-service"
    assert "Assessment: hold." in body["entry"]["review_notes"]
    assert body["entry"]["recommended_resolution"]["target_inbox_status"] == "resolved"
    assert body["entry"]["recommended_resolution"]["resolution_type"] == "escalate"
    assert len(body["entry"]["forward_attempts"]) == 1
    assert body["result"]["scott_notification"]["status"] == "queued"
    assert body["result"]["scott_notification"]["notification_id"] == "SN-GOV-REVIEW-1"


def test_auto_forward_on_ingest_uses_configured_targets(client, monkeypatch):
    calls = []

    class DummyResponse:
        status_code = 200
        text = (
            '{"service":"sophia-governor-review-service","review":"Assessment: watch. Risk: medium. '
            'Next step: verify.","recommended_resolution":{"target_inbox_status":"resolved",'
            '"resolution_type":"watch","requires_human":true,"auto_apply":false,'
            '"operator_action":"Verify intent before confirmation.","summary":"Pending transfer reviewed at high risk."}}'
        )

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append(url)
        return DummyResponse()

    monkeypatch.setenv("SOPHIA_GOVERNOR_INBOX_AUTO_FORWARD", "1")
    monkeypatch.setenv("SOPHIA_GOVERNOR_INBOX_FORWARD_TARGETS", "https://example.com/sophia/auto")
    monkeypatch.setattr(
        "sophia_governor_inbox.requests",
        type("DummyRequests", (), {"post": staticmethod(fake_post)}),
        raising=False,
    )

    ingest = client.post(
        "/api/sophia/governor/ingest",
        headers={"X-Admin-Key": "test-admin"},
        json=_sample_envelope(),
    )
    assert ingest.status_code == 202
    body = ingest.get_json()
    assert body["forward"]["status"] == "delivered"
    assert calls == ["https://example.com/sophia/auto"]
    assert body["inbox"]["assigned_agent"] == "sophia-governor-review-service"
    assert "Assessment: watch." in body["inbox"]["review_notes"]
    assert body["inbox"]["recommended_resolution"]["target_inbox_status"] == "resolved"
    assert body["inbox"]["recommended_resolution"]["resolution_type"] == "watch"


def test_forward_auto_applies_safe_approve_recommendation(client, monkeypatch):
    class DummyResponse:
        status_code = 200
        text = (
            '{"service":"sophia-governor-review-service","review":"Assessment: routine low-risk transfer. '
            'Risk: low. Next step: approve and log.","recommended_resolution":{"target_inbox_status":"resolved",'
            '"resolution_type":"approve","requires_human":false,"auto_apply":true,'
            '"operator_action":"Allow with logging.","summary":"Routine low-risk transfer."}}'
        )

    def fake_post(url, json=None, headers=None, timeout=None):
        return DummyResponse()

    envelope = _sample_envelope()
    envelope["decision"]["risk_level"] = "low"
    envelope["decision"]["stance"] = "allow"
    envelope["payload"]["amount_rtc"] = 25
    envelope["payload"]["reason"] = "routine sweep"

    monkeypatch.setenv("SOPHIA_GOVERNOR_INBOX_FORWARD_TARGETS", "https://example.com/sophia/review")
    monkeypatch.setattr(
        "sophia_governor_inbox.requests",
        type("DummyRequests", (), {"post": staticmethod(fake_post)}),
        raising=False,
    )

    ingest = client.post(
        "/api/sophia/governor/ingest",
        headers={"X-Admin-Key": "test-admin"},
        json=envelope,
    )
    inbox_id = ingest.get_json()["inbox"]["inbox_id"]

    forward = client.post(
        f"/api/sophia/governor/inbox/{inbox_id}/forward",
        headers={"X-Admin-Key": "test-admin"},
        json={},
    )
    assert forward.status_code == 200
    body = forward.get_json()
    assert body["result"]["status"] == "delivered"
    assert body["result"]["auto_applied"] is True
    assert body["entry"]["status"] == "resolved"
    assert body["entry"]["recommended_resolution"]["resolution_type"] == "approve"
    assert "Applied recommendation: Allow with logging." in body["entry"]["review_notes"]


def test_apply_recommended_resolution_endpoint_moves_entry_to_resolved(client, monkeypatch):
    class DummyResponse:
        status_code = 200
        text = (
            '{"service":"sophia-governor-review-service","review":"Assessment: watch. Risk: high. '
            'Next step: keep under watch.","recommended_resolution":{"target_inbox_status":"resolved",'
            '"resolution_type":"watch","requires_human":true,"auto_apply":false,'
            '"operator_action":"Keep the event under watch and require extra verification before confirmation.",'
            '"summary":"Large manual bridge override requested."}}'
        )

    def fake_post(url, json=None, headers=None, timeout=None):
        return DummyResponse()

    monkeypatch.setenv("SOPHIA_GOVERNOR_INBOX_FORWARD_TARGETS", "https://example.com/sophia/review")
    monkeypatch.setattr(
        "sophia_governor_inbox.requests",
        type("DummyRequests", (), {"post": staticmethod(fake_post)}),
        raising=False,
    )

    ingest = client.post(
        "/api/sophia/governor/ingest",
        headers={"X-Admin-Key": "test-admin"},
        json=_sample_envelope(),
    )
    inbox_id = ingest.get_json()["inbox"]["inbox_id"]

    forward = client.post(
        f"/api/sophia/governor/inbox/{inbox_id}/forward",
        headers={"X-Admin-Key": "test-admin"},
        json={},
    )
    assert forward.status_code == 200

    apply_response = client.post(
        f"/api/sophia/governor/inbox/{inbox_id}/apply-recommended-resolution",
        headers={"X-Admin-Key": "test-admin"},
        json={},
    )
    assert apply_response.status_code == 200
    body = apply_response.get_json()
    assert body["entry"]["status"] == "resolved"
    assert body["entry"]["recommended_resolution"]["target_inbox_status"] == "resolved"
    assert "Applied recommendation:" in body["entry"]["review_notes"]
