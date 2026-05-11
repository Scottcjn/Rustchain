import gc
import os
import tempfile
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import sophia_governor_review_service as review_service


@pytest.fixture
def client(monkeypatch):
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as handle:
        db_path = handle.name
    monkeypatch.setenv("SOPHIA_GOVERNOR_REVIEW_DB", db_path)
    monkeypatch.setenv("RC_ADMIN_KEY", "test-admin")
    monkeypatch.delenv("SCOTT_NOTIFICATION_QUEUE_URL", raising=False)
    monkeypatch.delenv("SCOTT_NOTIFICATION_SERVICE_TOKEN", raising=False)
    review_service.DB_PATH = db_path
    review_service.SCOTT_NOTIFICATION_QUEUE_URL = ""
    review_service.SCOTT_NOTIFICATION_SERVICE_TOKEN = "elya2025"
    review_service.app.config["TESTING"] = True
    try:
        yield review_service.app.test_client()
    finally:
        try:
            gc.collect()
            os.unlink(db_path)
        except FileNotFoundError:
            pass


def _payload():
    return {
        "inbox_id": 12,
        "event_type": "pending_transfer",
        "risk_level": "high",
        "stance": "watch",
        "summary": "Large manual bridge override requested.",
        "entry": {
            "source": "wallet.transfer",
            "remote_agent": "sophia-rustchain-governor",
            "remote_instance": "node-1",
            "payload": {"amount_rtc": 2500, "reason": "manual bridge override"},
        },
    }


def test_review_requires_auth(client):
    response = client.post("/review", json=_payload())
    assert response.status_code == 401


def test_review_endpoint_calls_model_and_stores(client, monkeypatch):
    monkeypatch.setattr(
        review_service,
        "_call_ollama",
        lambda prompt: ("**Assessment** hold transfer.\n**Risk** high exposure.\n**Next step** escalate to committee.", "glm-test"),
    )
    response = client.post("/review", headers={"X-Admin-Key": "test-admin"}, json=_payload())
    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["model_used"] == "glm-test"
    assert body["review"].startswith("Assessment:")
    assert "\nRisk:" in body["review"]
    assert "\nNext step:" in body["review"]
    assert body["recommended_resolution"]["target_inbox_status"] == "resolved"
    assert body["recommended_resolution"]["resolution_type"] in {"watch", "hold", "approve", "escalate", "dismiss"}

    recent = client.get("/recent?limit=5", headers={"X-Admin-Key": "test-admin"})
    assert recent.status_code == 200
    recent_body = recent.get_json()
    assert recent_body["ok"] is True
    assert len(recent_body["reviews"]) == 1
    assert recent_body["reviews"][0]["recommended_resolution"]["target_inbox_status"] == "resolved"


def test_health_reports_status(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.get_json()
    assert body["service"] == "sophia-governor-review-service"
    assert body["status"] == "ok"


def test_call_ollama_sends_top_level_think_false(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": "Assessment: ok.\nRisk: medium.\nNext step: watch."}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(review_service, "requests", SimpleNamespace(post=fake_post))
    monkeypatch.delenv("SOPHIA_GOVERNOR_REVIEW_ENABLE_THINKING", raising=False)

    review_text, model_used = review_service._call_ollama("prompt")

    assert "Assessment" in review_text
    assert model_used == review_service.OLLAMA_MODEL
    assert captured["json"]["think"] is False


def test_review_endpoint_falls_back_when_model_returns_thinking_only(client, monkeypatch):
    def fake_call(prompt):
        raise RuntimeError("Ollama returned thinking without final answer for model glm-test")

    monkeypatch.setattr(review_service, "_call_ollama", fake_call)

    response = client.post("/review", headers={"X-Admin-Key": "test-admin"}, json=_payload())
    assert response.status_code == 200
    body = response.get_json()
    assert body["model_used"].endswith("@error")
    assert "Assessment:" in body["review"]
    assert "Next step:" in body["review"]


def test_backfill_missing_updates_blank_reviews(client, monkeypatch):
    review_id = review_service._store_review(_payload(), "", "glm-test-empty")

    monkeypatch.setattr(
        review_service,
        "_call_ollama",
        lambda prompt: ("Assessment: repaired.\nRisk: high.\nNext step: monitor.", "glm-test"),
    )

    response = client.post(
        "/api/sophia/governor/review/backfill-missing",
        headers={"X-Admin-Key": "test-admin"},
        json={"limit": 5},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["count"] == 1
    assert body["updated"][0]["review_id"] == review_id
    assert "Assessment: repaired." in body["updated"][0]["review_text"]
    assert body["updated"][0]["recommended_resolution"]["target_inbox_status"] == "resolved"

    recent = client.get("/recent?limit=5", headers={"X-Admin-Key": "test-admin"})
    recent_body = recent.get_json()
    repaired = next(item for item in recent_body["reviews"] if item["id"] == review_id)
    assert "Assessment: repaired." in repaired["review_text"]


def test_backfill_missing_rejects_invalid_limit(client):
    for limit in ("bad", 0, -1):
        response = client.post(
            "/api/sophia/governor/review/backfill-missing",
            headers={"X-Admin-Key": "test-admin"},
            json={"limit": limit},
        )

        assert response.status_code == 400
        assert response.get_json()["error"] == "invalid_limit"


def test_review_normalizes_verbose_action_reasoning(client, monkeypatch):
    monkeypatch.setattr(
        review_service,
        "_call_ollama",
        lambda prompt: (
            "Based on the event details provided, here is the recommended course of action. "
            "**Action:** Escalate to the Core Security Committee. "
            "**Reasoning:** The transfer crossed the threshold and needs human verification. "
            "**Next Steps:** Hold final confirmation until the committee reviews the source legitimacy.",
            "glm-test",
        ),
    )

    response = client.post("/review", headers={"X-Admin-Key": "test-admin"}, json=_payload())
    assert response.status_code == 200
    body = response.get_json()
    assert body["review"].startswith("Assessment:")
    assert "Core Security Committee" not in body["review"].splitlines()[0]
    assert "Risk:" in body["review"]
    assert "Next step: Escalate to the Core Security Committee." in body["review"]


def test_normalize_existing_route_rewrites_recent_rows(client, monkeypatch):
    payload = _payload()
    raw_review = (
        "Based on the event details provided, here is the recommended course of action. "
        "**Action:** Escalate to the Core Security Committee. "
        "**Reasoning:** The transfer crossed the threshold and needs human verification."
    )
    review_id = review_service._store_review(payload, raw_review, "glm-test-raw")

    response = client.post(
        "/api/sophia/governor/review/normalize-existing",
        headers={"X-Admin-Key": "test-admin"},
        json={"limit": 5},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["count"] >= 1
    normalized = next(item for item in body["updated"] if item["review_id"] == review_id)
    assert normalized["review_text"].startswith("Assessment:")
    assert "\nRisk:" in normalized["review_text"]
    assert "\nNext step:" in normalized["review_text"]
    assert normalized["recommended_resolution"]["target_inbox_status"] == "resolved"


def test_normalize_existing_rejects_invalid_limit(client):
    for limit in ("bad", 0, -1):
        response = client.post(
            "/api/sophia/governor/review/normalize-existing",
            headers={"X-Admin-Key": "test-admin"},
            json={"limit": limit},
        )

        assert response.status_code == 400
        assert response.get_json()["error"] == "invalid_limit"


def test_normalize_review_text_compacts_numbered_reasoning():
    payload = _payload()
    raw_review = (
        "**Action:** Escalate to the Core Security Committee "
        "Committee Review: Verify the transaction source before approval. "
        "**Reasoning:** 1. Threshold breach requires human verification. 2. High risk classification indicates anomaly."
    )

    normalized = review_service._normalize_review_text(raw_review, payload)

    assert normalized.startswith("Assessment: Large manual bridge override requested.")
    assert "\nRisk: High." in normalized
    assert "\nNext step: Escalate to the Core Security Committee" in normalized


def test_normalize_review_text_prefers_summary_over_mangled_event_name():
    payload = _payload()
    raw_review = (
        "Assessment: pendingtransfer reviewed at high risk with watch stance. "
        "Risk: High. Event requires higher scrutiny before confirmation. "
        "Next step: Escalate to Core Governance Committee Rationale: threshold breach."
    )

    normalized = review_service._normalize_review_text(raw_review, payload)

    assert normalized.startswith("Assessment: Large manual bridge override requested.")
    assert "\nNext step: Escalate to Core Governance Committee" in normalized
    assert "Rationale" not in normalized


def test_recommended_resolution_prefers_explicit_escalation_over_verify_words():
    payload = _payload()
    review_text = (
        "Assessment: Large manual bridge override requested.\n"
        "Risk: High. Event requires higher scrutiny before confirmation.\n"
        "Next step: Escalate to the Core Security Committee and verify intent before approval."
    )

    recommendation = review_service._build_recommended_resolution(review_text, payload)

    assert recommendation["resolution_type"] == "escalate"
    assert recommendation["requires_human"] is True


def test_recommended_resolution_dismiss_sets_dismissed_target_and_auto_apply():
    payload = _payload()
    payload["risk_level"] = "low"
    payload["stance"] = "allow"
    review_text = (
        "Assessment: Routine duplicate test event.\n"
        "Risk: Low. No anomaly remains after review.\n"
        "Next step: Dismiss as resolved test event."
    )

    recommendation = review_service._build_recommended_resolution(review_text, payload)

    assert recommendation["resolution_type"] == "dismiss"
    assert recommendation["target_inbox_status"] == "dismissed"
    assert recommendation["requires_human"] is False
    assert recommendation["auto_apply"] is True


def test_scott_notification_queue_relay_endpoint(client, monkeypatch):
    class FakeResponse:
        status_code = 200
        text = '{"status":"ok","notification":{"notification_id":"SN-RELAY0001"}}'

        def json(self):
            return {"status": "ok", "notification": {"notification_id": "SN-RELAY0001"}}

    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(review_service, "requests", SimpleNamespace(post=fake_post))
    monkeypatch.setenv("SCOTT_NOTIFICATION_QUEUE_URL", "http://100.121.203.9:18790/scott-notifications/queue")
    monkeypatch.setenv("SCOTT_NOTIFICATION_SERVICE_TOKEN", "relay-token")
    review_service.SCOTT_NOTIFICATION_QUEUE_URL = "http://100.121.203.9:18790/scott-notifications/queue"
    review_service.SCOTT_NOTIFICATION_SERVICE_TOKEN = "relay-token"

    response = client.post(
        "/api/sophia/governor/scott-notifications/queue",
        headers={"X-Admin-Key": "test-admin"},
        json={
            "title": "RustChain inbox 7 needs review",
            "summary": "pending_transfer came in at high risk.",
            "related_type": "rustchain_governor_inbox",
            "related_id": "7",
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["notification"]["notification_id"] == "SN-RELAY0001"
    assert captured["url"] == "http://100.121.203.9:18790/scott-notifications/queue"
    assert captured["headers"]["Authorization"] == "Bearer relay-token"
