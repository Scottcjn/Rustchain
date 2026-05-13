#!/usr/bin/env python3
"""
Sophia Governor Inbox
=====================

Receives "phone home" governance escalations from smaller RustChain governors
and stores them in a durable inbox for bigger Sophia/Elyan agents.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import time
from typing import Any

from flask import jsonify, request

try:
    import requests
except ImportError:  # pragma: no cover - expected in production
    requests = None

DB_PATH = os.getenv("RUSTCHAIN_DB_PATH", "/root/rustchain/rustchain_v2.db")

INBOX_STATUSES = ("received", "reviewing", "forwarded", "resolved", "dismissed")
RISK_LEVELS = ("low", "medium", "high", "critical")
STANCE_VALUES = ("allow", "watch", "hold", "escalate")
TRUE_VALUES = {"1", "true", "yes", "on"}

INBOX_SCHEMA = """
CREATE TABLE IF NOT EXISTS sophia_governor_inbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint TEXT NOT NULL UNIQUE,
    remote_event_id INTEGER,
    remote_created_at INTEGER,
    event_type TEXT NOT NULL,
    source TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    stance TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'received',
    remote_agent TEXT,
    remote_instance TEXT,
    assigned_agent TEXT DEFAULT '',
    review_notes TEXT DEFAULT '',
    recommended_resolution_json TEXT DEFAULT '{}',
    envelope_json TEXT NOT NULL,
    decision_json TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    continuity_json TEXT NOT NULL,
    scott_notify_sent_at INTEGER,
    scott_review_notify_sent_at INTEGER,
    received_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sophia_governor_inbox_status
    ON sophia_governor_inbox(status, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_sophia_governor_inbox_risk
    ON sophia_governor_inbox(risk_level, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_sophia_governor_inbox_remote
    ON sophia_governor_inbox(remote_agent, remote_instance, remote_event_id);

CREATE TABLE IF NOT EXISTS sophia_governor_inbox_forward (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inbox_id INTEGER NOT NULL,
    target TEXT NOT NULL,
    transport TEXT NOT NULL,
    request_json TEXT NOT NULL,
    status TEXT NOT NULL,
    response_code INTEGER,
    response_body TEXT,
    created_at INTEGER NOT NULL,
    FOREIGN KEY(inbox_id) REFERENCES sophia_governor_inbox(id)
);
CREATE INDEX IF NOT EXISTS idx_sophia_governor_inbox_forward_inbox
    ON sophia_governor_inbox_forward(inbox_id, created_at DESC);
"""


def init_sophia_governor_inbox_schema(db_path: str | None = None) -> None:
    """Create inbox tables if they do not exist."""
    with sqlite3.connect(db_path or DB_PATH) as conn:
        conn.executescript(INBOX_SCHEMA)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(sophia_governor_inbox)")}
        if "recommended_resolution_json" not in columns:
            conn.execute("ALTER TABLE sophia_governor_inbox ADD COLUMN recommended_resolution_json TEXT DEFAULT '{}'")
        if "scott_notify_sent_at" not in columns:
            conn.execute("ALTER TABLE sophia_governor_inbox ADD COLUMN scott_notify_sent_at INTEGER")
        if "scott_review_notify_sent_at" not in columns:
            conn.execute("ALTER TABLE sophia_governor_inbox ADD COLUMN scott_review_notify_sent_at INTEGER")
        conn.commit()


def _now() -> int:
    return int(time.time())


def _safe_json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _env_truthy(name: str, default: str = "false") -> bool:
    return str(os.getenv(name, default)).strip().lower() in TRUE_VALUES


def _text_excerpt(text: Any, limit: int = 600) -> str:
    if text is None:
        return ""
    value = " ".join(str(text).split()).strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _normalize_risk_level(value: Any) -> str:
    risk_level = str(value or "medium").strip().lower()
    return risk_level if risk_level in RISK_LEVELS else "medium"


def _normalize_stance(value: Any) -> str:
    stance = str(value or "watch").strip().lower()
    return stance if stance in STANCE_VALUES else "watch"


def _normalize_status(value: Any) -> str:
    status = str(value or "received").strip().lower()
    if status not in INBOX_STATUSES:
        raise ValueError(f"invalid_status:{status}")
    return status


def _normalize_recommended_resolution(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, Any] = {}
    target_status = value.get("target_inbox_status")
    if target_status:
        normalized["target_inbox_status"] = _normalize_status(target_status)
    resolution_type = str(value.get("resolution_type") or "").strip().lower()
    if resolution_type:
        normalized["resolution_type"] = resolution_type
    if "requires_human" in value:
        normalized["requires_human"] = bool(value.get("requires_human"))
    if "auto_apply" in value:
        normalized["auto_apply"] = bool(value.get("auto_apply"))
    operator_action = _text_excerpt(value.get("operator_action"), limit=400)
    if operator_action:
        normalized["operator_action"] = operator_action
    summary = _text_excerpt(value.get("summary"), limit=240)
    if summary:
        normalized["summary"] = summary
    return normalized


def _should_auto_apply_recommended_resolution(value: Any) -> bool:
    recommendation = _normalize_recommended_resolution(value)
    if not recommendation or not _env_truthy("SOPHIA_GOVERNOR_INBOX_AUTO_APPLY_SAFE", "true"):
        return False
    if not recommendation.get("auto_apply"):
        return False
    if recommendation.get("requires_human"):
        return False
    resolution_type = recommendation.get("resolution_type")
    target_status = recommendation.get("target_inbox_status")
    return (
        resolution_type in {"approve", "dismiss"}
        and target_status in {"resolved", "dismissed"}
    )


def _parse_csv_env(name: str) -> list[str]:
    raw = os.getenv(name, "")
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _forward_targets() -> list[str]:
    targets = _parse_csv_env("SOPHIA_GOVERNOR_INBOX_FORWARD_TARGETS")
    if targets:
        return targets
    return _parse_csv_env("SOPHIA_GOVERNOR_INBOX_FORWARD_URLS")


def _auto_forward_enabled() -> bool:
    return _env_truthy("SOPHIA_GOVERNOR_INBOX_AUTO_FORWARD", "false")


def _forward_timeouts() -> tuple[float, float]:
    connect_timeout = float(os.getenv("SOPHIA_GOVERNOR_INBOX_FORWARD_CONNECT_TIMEOUT_SEC", "4"))
    read_timeout = float(os.getenv("SOPHIA_GOVERNOR_INBOX_FORWARD_READ_TIMEOUT_SEC", "90"))
    return max(1.0, connect_timeout), max(5.0, read_timeout)


def _review_health_targets() -> list[str]:
    candidates: list[str] = []
    for target in _forward_targets():
        value = str(target or "").strip()
        if not value:
            continue
        if value.endswith("/review"):
            candidates.append(value[: -len("/review")] + "/health")
        else:
            candidates.append(value.rstrip("/") + "/health")

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate not in seen:
            deduped.append(candidate)
            seen.add(candidate)
    return deduped


def _bearer_tokens() -> set[str]:
    raw = os.getenv("SOPHIA_GOVERNOR_INBOX_BEARER", "").strip()
    if not raw:
        return set()
    return {token.strip() for token in raw.split(",") if token.strip()}


def _is_authorized(req) -> bool:
    required_admin = os.getenv("RC_ADMIN_KEY", "").strip()
    required_bearers = _bearer_tokens()

    provided_admin = (req.headers.get("X-Admin-Key") or req.headers.get("X-API-Key") or "").strip()
    if required_admin and provided_admin and hmac.compare_digest(provided_admin, required_admin):
        return True

    auth_header = (req.headers.get("Authorization") or "").strip()
    if auth_header.lower().startswith("bearer "):
        provided_bearer = auth_header.split(" ", 1)[1].strip()
        if provided_bearer and provided_bearer in required_bearers:
            return True

    return False


def _coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(envelope, dict):
        raise ValueError("envelope_must_be_object")

    decision = envelope.get("decision")
    if not isinstance(decision, dict):
        decision = {}

    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        payload = {}

    continuity = envelope.get("continuity")
    if not isinstance(continuity, dict):
        continuity = {}

    governor = envelope.get("governor")
    if not isinstance(governor, dict):
        governor = {}

    event_type = str(envelope.get("event_type", "")).strip()
    source = str(envelope.get("source", "unknown")).strip() or "unknown"
    if not event_type:
        raise ValueError("event_type_required")

    remote_event_id = _coerce_int(envelope.get("event_id"))
    remote_created_at = _coerce_int(envelope.get("created_at"))
    risk_level = _normalize_risk_level(decision.get("risk_level"))
    stance = _normalize_stance(decision.get("stance"))
    remote_agent = str(governor.get("agent", "sophia-rustchain-governor")).strip() or "sophia-rustchain-governor"
    remote_instance = str(governor.get("instance", "unknown")).strip() or "unknown"

    fingerprint_seed = {
        "remote_event_id": remote_event_id,
        "event_type": event_type,
        "source": source,
        "remote_agent": remote_agent,
        "remote_instance": remote_instance,
        "risk_level": risk_level,
        "stance": stance,
        "payload": payload,
    }
    fingerprint = hashlib.sha256(_safe_json_dumps(fingerprint_seed).encode("utf-8")).hexdigest()

    return {
        "fingerprint": fingerprint,
        "remote_event_id": remote_event_id,
        "remote_created_at": remote_created_at,
        "event_type": event_type,
        "source": source,
        "risk_level": risk_level,
        "stance": stance,
        "status": "received",
        "remote_agent": remote_agent,
        "remote_instance": remote_instance,
        "assigned_agent": "",
        "review_notes": "",
        "recommended_resolution": _normalize_recommended_resolution(envelope.get("recommended_resolution")),
        "envelope": envelope,
        "decision": decision,
        "payload": payload,
        "continuity": continuity,
    }


def _row_to_entry(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "inbox_id": row["id"],
        "fingerprint": row["fingerprint"],
        "remote_event_id": row["remote_event_id"],
        "remote_created_at": row["remote_created_at"],
        "event_type": row["event_type"],
        "source": row["source"],
        "risk_level": row["risk_level"],
        "stance": row["stance"],
        "status": row["status"],
        "remote_agent": row["remote_agent"],
        "remote_instance": row["remote_instance"],
        "assigned_agent": row["assigned_agent"] or "",
        "review_notes": row["review_notes"] or "",
        "recommended_resolution": _normalize_recommended_resolution(
            json.loads(row["recommended_resolution_json"]) if "recommended_resolution_json" in row.keys() else {}
        ),
        "decision": json.loads(row["decision_json"]),
        "payload": json.loads(row["payload_json"]),
        "continuity": json.loads(row["continuity_json"]),
        "envelope": json.loads(row["envelope_json"]),
        "scott_notify_sent_at": row["scott_notify_sent_at"] if "scott_notify_sent_at" in row.keys() else None,
        "scott_review_notify_sent_at": (
            row["scott_review_notify_sent_at"] if "scott_review_notify_sent_at" in row.keys() else None
        ),
        "received_at": row["received_at"],
        "updated_at": row["updated_at"],
    }


def _forward_headers() -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "X-Sophia-Inbox": "sophia-governor-inbox",
    }
    forward_bearer = os.getenv("SOPHIA_GOVERNOR_INBOX_FORWARD_BEARER", "").strip()
    if forward_bearer:
        headers["Authorization"] = f"Bearer {forward_bearer}"
    admin_key = os.getenv("RC_ADMIN_KEY", "").strip()
    if admin_key:
        headers["X-Admin-Key"] = admin_key
    return headers


def _review_health_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "X-Sophia-Inbox": "sophia-governor-inbox",
    }
    forward_bearer = os.getenv("SOPHIA_GOVERNOR_INBOX_FORWARD_BEARER", "").strip()
    if forward_bearer:
        headers["Authorization"] = f"Bearer {forward_bearer}"
    admin_key = os.getenv("RC_ADMIN_KEY", "").strip()
    if admin_key:
        headers["X-Admin-Key"] = admin_key
    return headers


def _review_relay_status() -> dict[str, Any]:
    targets = _review_health_targets()
    status: dict[str, Any] = {
        "configured": bool(targets),
        "targets": targets,
        "reachable": False,
    }
    if not targets:
        return status
    if requests is None:
        status["error"] = "requests_unavailable"
        return status

    connect_timeout, read_timeout = _forward_timeouts()
    timeout = (max(1.0, min(connect_timeout, 2.0)), max(2.0, min(read_timeout, 6.0)))
    last_error = "unreachable"

    for url in targets:
        try:
            response = requests.get(url, headers=_review_health_headers(), timeout=timeout)
            body = response.text[:2000]
            parsed = response.json() if body else {}
        except Exception as exc:
            last_error = _text_excerpt(exc, 200)
            continue

        if response.status_code >= 400 or not isinstance(parsed, dict):
            last_error = f"http_{response.status_code}"
            continue

        status.update(
            {
                "reachable": True,
                "url": url,
                "service": str(parsed.get("service") or "").strip(),
                "model": str(parsed.get("model") or "").strip(),
                "totals": dict(parsed.get("totals") or {}),
                "auth": dict(parsed.get("auth") or {}),
            }
        )
        return status

    status["error"] = last_error
    return status


def _build_forward_prompt(entry: dict[str, Any]) -> str:
    decision = entry.get("decision") or {}
    continuity = entry.get("continuity") or {}
    summary = (
        decision.get("llm_summary")
        or decision.get("local_summary")
        or f"{entry['event_type']} came in at {entry['risk_level']} risk."
    )
    prompt_lines = [
        "Sophia Governor Inbox escalation received.",
        f"Inbox ID: {entry['inbox_id']}",
        f"Remote governor: {entry['remote_agent']} @ {entry['remote_instance']}",
        f"Event type: {entry['event_type']}",
        f"Risk level: {entry['risk_level']}",
        f"Stance: {entry['stance']}",
        f"Source: {entry['source']}",
        f"Summary: {summary}",
    ]
    bootstrap = continuity.get("bootstrap_block")
    if bootstrap:
        prompt_lines.append(f"Continuity anchor: {_text_excerpt(bootstrap, 400)}")
    prompt_lines.append("Review the event and decide what the bigger Sophia/Elyan layer should do next.")
    return "\n".join(prompt_lines)


def _build_forward_payload(entry: dict[str, Any]) -> dict[str, Any]:
    decision = entry.get("decision") or {}
    return {
        "source": "sophia-governor-inbox",
        "inbox_id": entry["inbox_id"],
        "event_type": entry["event_type"],
        "risk_level": entry["risk_level"],
        "stance": entry["stance"],
        "status": entry["status"],
        "summary": decision.get("llm_summary") or decision.get("local_summary"),
        "review_prompt": _build_forward_prompt(entry),
        "entry": entry,
    }


def _record_forward_attempt(
    db_path: str,
    *,
    inbox_id: int,
    target: str,
    transport: str,
    request_payload: dict[str, Any],
    status: str,
    response_code: int | None = None,
    response_body: str | None = None,
) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO sophia_governor_inbox_forward
            (inbox_id, target, transport, request_json, status, response_code, response_body, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                inbox_id,
                target,
                transport,
                _safe_json_dumps(request_payload),
                status,
                response_code,
                response_body,
                _now(),
            ),
        )
        conn.commit()


def _get_forward_attempts(inbox_id: int, db_path: str | None = None) -> list[dict[str, Any]]:
    db = db_path or DB_PATH
    init_sophia_governor_inbox_schema(db)
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, target, transport, status, response_code, response_body, created_at
            FROM sophia_governor_inbox_forward
            WHERE inbox_id = ?
            ORDER BY created_at DESC
            """,
            (inbox_id,),
        ).fetchall()
    return [
        {
            "attempt_id": row["id"],
            "target": row["target"],
            "transport": row["transport"],
            "status": row["status"],
            "response_code": row["response_code"],
            "response_body": row["response_body"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def _deliver_forward_http_target(target: str, payload: dict[str, Any]) -> tuple[str, int | None, str]:
    if requests is None:
        return "requests_unavailable", None, "requests library unavailable"
    connect_timeout, read_timeout = _forward_timeouts()
    response = requests.post(
        target,
        json=payload,
        headers=_forward_headers(),
        timeout=(connect_timeout, read_timeout),
    )
    try:
        body_text = _safe_json_dumps(response.json())
    except Exception:
        body_text = response.text
    body = _text_excerpt(body_text, 8000)
    status = "delivered" if response.status_code < 400 else "failed"
    return status, response.status_code, body


def _parse_forward_response(response_body: str | None) -> dict[str, Any]:
    if not response_body:
        return {}
    try:
        parsed = json.loads(response_body)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _scott_notification_queue_url() -> str:
    return (
        os.getenv("SOPHIA_GOVERNOR_SCOTT_NOTIFY_QUEUE_URL", "").strip()
        or os.getenv("SCOTT_NOTIFICATION_QUEUE_URL", "").strip()
    )


def _scott_notification_bearer() -> str:
    return (
        os.getenv("SOPHIA_GOVERNOR_SCOTT_NOTIFY_BEARER", "").strip()
        or os.getenv("SCOTT_NOTIFICATION_SERVICE_TOKEN", "").strip()
    )


def _scott_notification_headers() -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "X-Sophia-Inbox": "sophia-governor-inbox",
    }
    bearer = _scott_notification_bearer()
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    return headers


def _phase_notify_column(phase: str) -> str:
    return "scott_review_notify_sent_at" if phase == "review" else "scott_notify_sent_at"


def _priority_for_scott_notification(entry: dict[str, Any], phase: str) -> str:
    risk_level = str(entry.get("risk_level", "medium") or "medium").lower()
    resolution = _normalize_recommended_resolution(entry.get("recommended_resolution"))
    resolution_type = str(resolution.get("resolution_type", "") or "").lower()
    if risk_level == "critical" or resolution_type in {"hold", "escalate"}:
        return "urgent"
    if risk_level == "high" or resolution_type == "watch":
        return "high"
    return "normal"


def _should_queue_scott_notification(entry: dict[str, Any], phase: str) -> bool:
    if phase == "review":
        resolution = _normalize_recommended_resolution(entry.get("recommended_resolution"))
        resolution_type = str(resolution.get("resolution_type", "") or "").lower()
        return bool(
            resolution
            and (
                resolution.get("requires_human")
                or resolution_type in {"hold", "escalate", "watch"}
            )
        )

    return (
        str(entry.get("risk_level", "medium") or "medium").lower() in {"high", "critical"}
        or str(entry.get("stance", "watch") or "watch").lower() in {"hold", "escalate"}
    )


def _build_scott_notification_payload(entry: dict[str, Any], phase: str) -> dict[str, Any]:
    inbox_id = int(entry["inbox_id"])
    event_type = str(entry.get("event_type", "unknown") or "unknown")
    risk_level = str(entry.get("risk_level", "medium") or "medium").lower()
    stance = str(entry.get("stance", "watch") or "watch").lower()
    remote_instance = str(entry.get("remote_instance", "unknown") or "unknown")
    summary = ""
    decision = entry.get("decision") or {}
    payload = entry.get("payload") or {}
    resolution = _normalize_recommended_resolution(entry.get("recommended_resolution"))

    if phase == "review":
        resolution_type = str(resolution.get("resolution_type", "review") or "review").lower()
        summary = _text_excerpt(
            resolution.get("summary")
            or entry.get("review_notes")
            or decision.get("llm_summary")
            or decision.get("local_summary")
            or f"Bigger Sophia reviewed {event_type} and recommends {resolution_type}.",
            320,
        )
        title = f"RustChain inbox {inbox_id} recommends {resolution_type}"
    else:
        decision_summary = _text_excerpt(
            decision.get("llm_summary")
            or decision.get("local_summary")
            or f"{event_type} arrived for governor review.",
            240,
        )
        amount = payload.get("amount_rtc")
        amount_text = f" {amount} RTC." if amount not in (None, "") else ""
        summary = (
            f"{event_type} from {remote_instance} came in at {risk_level} risk with `{stance}` stance.{amount_text} "
            f"{decision_summary}"
        ).strip()
        title = f"RustChain inbox {inbox_id} needs review"

    return {
        "title": title,
        "summary": summary,
        "category": "rustchain_governor",
        "priority": _priority_for_scott_notification(entry, phase),
        "requires_ack": True,
        "speakable": False,
        "source": "sophia_governor_inbox",
        "source_id": f"{inbox_id}:{phase}",
        "related_type": "rustchain_governor_inbox",
        "related_id": str(inbox_id),
        "suggested_request_text": f"review governor inbox {inbox_id}",
        "metadata": {
            "inbox_id": inbox_id,
            "phase": phase,
            "event_type": event_type,
            "risk_level": risk_level,
            "stance": stance,
            "remote_agent": str(entry.get("remote_agent", "") or ""),
            "remote_instance": remote_instance,
            "recommended_resolution": resolution,
        },
    }


def _queue_scott_notification_for_entry(
    inbox_id: int,
    *,
    phase: str,
    db_path: str | None = None,
) -> dict[str, Any]:
    db = db_path or DB_PATH
    entry = get_governor_inbox_entry(inbox_id, db_path=db)
    if entry is None:
        return {"status": "missing"}
    if phase not in {"ingest", "review"}:
        return {"status": "invalid_phase", "phase": phase}
    if not _should_queue_scott_notification(entry, phase):
        return {"status": "not_needed", "phase": phase}

    queue_url = _scott_notification_queue_url()
    if not queue_url:
        return {"status": "not_configured", "phase": phase}
    if not _scott_notification_bearer():
        return {
            "status": "not_configured",
            "phase": phase,
            "error": "scott_notification_token_not_configured",
        }

    sent_column = _phase_notify_column(phase)
    if entry.get(sent_column):
        return {"status": "already_sent", "phase": phase}

    request_payload = _build_scott_notification_payload(entry, phase)
    if requests is None:
        return {"status": "requests_unavailable", "phase": phase}
    try:
        response = requests.post(
            queue_url,
            json=request_payload,
            headers=_scott_notification_headers(),
            timeout=(4, 20),
        )
    except Exception as exc:
        return {
            "status": "failed",
            "phase": phase,
            "error": _text_excerpt(exc, 400),
        }
    try:
        response_data = response.json()
    except Exception:
        response_data = {"raw": response.text}

    if response.status_code >= 400 or response_data.get("status") != "ok":
        return {
            "status": "failed",
            "phase": phase,
            "response_code": response.status_code,
            "response": response_data,
        }

    with sqlite3.connect(db) as conn:
        conn.execute(
            f"UPDATE sophia_governor_inbox SET {sent_column} = ?, updated_at = ? WHERE id = ?",
            (_now(), _now(), inbox_id),
        )
        conn.commit()

    return {
        "status": "queued",
        "phase": phase,
        "notification_id": str(
            dict(response_data.get("notification") or {}).get("notification_id", "") or ""
        ),
        "response_code": response.status_code,
    }


def ingest_governor_envelope(envelope: dict[str, Any], db_path: str | None = None) -> dict[str, Any]:
    """Persist an incoming governor escalation and return inbox metadata."""
    db = db_path or DB_PATH
    init_sophia_governor_inbox_schema(db)
    normalized = _normalize_envelope(envelope)

    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        existing = conn.execute(
            """
            SELECT * FROM sophia_governor_inbox
            WHERE fingerprint = ?
            """,
            (normalized["fingerprint"],),
        ).fetchone()
        if existing is not None:
            entry = _row_to_entry(existing)
            return {
                "accepted": True,
                "duplicate": True,
                "inbox": entry,
                "scott_notification": {"status": "duplicate"},
            }

        now = _now()
        cur = conn.execute(
            """
            INSERT INTO sophia_governor_inbox
            (fingerprint, remote_event_id, remote_created_at, event_type, source,
             risk_level, stance, status, remote_agent, remote_instance,
             assigned_agent, review_notes, recommended_resolution_json, envelope_json, decision_json,
             payload_json, continuity_json, received_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                normalized["fingerprint"],
                normalized["remote_event_id"],
                normalized["remote_created_at"],
                normalized["event_type"],
                normalized["source"],
                normalized["risk_level"],
                normalized["stance"],
                normalized["status"],
                normalized["remote_agent"],
                normalized["remote_instance"],
                normalized["assigned_agent"],
                normalized["review_notes"],
                _safe_json_dumps(normalized["recommended_resolution"]),
                _safe_json_dumps(normalized["envelope"]),
                _safe_json_dumps(normalized["decision"]),
                _safe_json_dumps(normalized["payload"]),
                _safe_json_dumps(normalized["continuity"]),
                now,
                now,
            ),
        )
        conn.commit()
        inbox_id = int(cur.lastrowid)

    entry = get_governor_inbox_entry(inbox_id, db_path=db)
    scott_notification = _queue_scott_notification_for_entry(
        inbox_id,
        phase="ingest",
        db_path=db,
    )
    return {
        "accepted": True,
        "duplicate": False,
        "inbox": entry,
        "scott_notification": scott_notification,
    }


def get_governor_inbox_entry(inbox_id: int, db_path: str | None = None) -> dict[str, Any] | None:
    db = db_path or DB_PATH
    init_sophia_governor_inbox_schema(db)
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM sophia_governor_inbox WHERE id = ?",
            (inbox_id,),
        ).fetchone()
    if row is None:
        return None
    entry = _row_to_entry(row)
    entry["forward_attempts"] = _get_forward_attempts(inbox_id, db_path=db)
    return entry


def list_governor_inbox_entries(
    db_path: str | None = None,
    *,
    limit: int = 20,
    status: str | None = None,
    risk_level: str | None = None,
) -> list[dict[str, Any]]:
    db = db_path or DB_PATH
    init_sophia_governor_inbox_schema(db)
    limit = max(1, min(int(limit), 200))

    clauses = []
    params: list[Any] = []
    if status:
        clauses.append("status = ?")
        params.append(_normalize_status(status))
    if risk_level:
        clauses.append("risk_level = ?")
        params.append(_normalize_risk_level(risk_level))

    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"""
        SELECT * FROM sophia_governor_inbox
        {where_clause}
        ORDER BY received_at DESC
        LIMIT ?
    """
    params.append(limit)

    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()

    return [_row_to_entry(row) for row in rows]


def update_governor_inbox_entry(
    inbox_id: int,
    *,
    status: str | None = None,
    assigned_agent: str | None = None,
    review_notes: str | None = None,
    recommended_resolution: dict[str, Any] | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    db = db_path or DB_PATH
    init_sophia_governor_inbox_schema(db)

    existing = get_governor_inbox_entry(inbox_id, db_path=db)
    if existing is None:
        raise KeyError(f"inbox_entry_not_found:{inbox_id}")

    next_status = _normalize_status(status or existing["status"])
    next_assigned_agent = str(assigned_agent if assigned_agent is not None else existing["assigned_agent"]).strip()
    next_review_notes = _text_excerpt(
        review_notes if review_notes is not None else existing["review_notes"],
        limit=2000,
    )
    next_recommended_resolution = (
        _normalize_recommended_resolution(recommended_resolution)
        if recommended_resolution is not None
        else existing["recommended_resolution"]
    )

    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            UPDATE sophia_governor_inbox
            SET status = ?, assigned_agent = ?, review_notes = ?, recommended_resolution_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                next_status,
                next_assigned_agent,
                next_review_notes,
                _safe_json_dumps(next_recommended_resolution),
                _now(),
                inbox_id,
            ),
        )
        conn.commit()

    updated = get_governor_inbox_entry(inbox_id, db_path=db)
    if updated is None:  # pragma: no cover - defensive
        raise KeyError(f"inbox_entry_not_found:{inbox_id}")
    return updated


def get_governor_inbox_status(db_path: str | None = None) -> dict[str, Any]:
    db = db_path or DB_PATH
    init_sophia_governor_inbox_schema(db)
    with sqlite3.connect(db) as conn:
        total = conn.execute("SELECT COUNT(*) FROM sophia_governor_inbox").fetchone()[0]
        recent_unresolved = conn.execute(
            """
            SELECT COUNT(*) FROM sophia_governor_inbox
            WHERE status IN ('received', 'reviewing', 'forwarded')
            """
        ).fetchone()[0]
        status_rows = conn.execute(
            """
            SELECT status, COUNT(*) AS count
            FROM sophia_governor_inbox
            GROUP BY status
            """
        ).fetchall()
        risk_rows = conn.execute(
            """
            SELECT risk_level, COUNT(*) AS count
            FROM sophia_governor_inbox
            GROUP BY risk_level
            """
        ).fetchall()
        forward_rows = conn.execute(
            """
            SELECT status, COUNT(*) AS count
            FROM sophia_governor_inbox_forward
            GROUP BY status
            """
        ).fetchall()

    return {
        "service": "sophia-governor-inbox",
        "status": "ok",
        "auth": {
            "admin_key_configured": bool(os.getenv("RC_ADMIN_KEY", "").strip()),
            "bearer_configured": bool(_bearer_tokens()),
        },
        "forwarding": {
            "auto_forward_enabled": _auto_forward_enabled(),
            "targets": _forward_targets(),
            "attempt_summary": {row[0]: int(row[1]) for row in forward_rows},
        },
        "review_relay": _review_relay_status(),
        "scott_notifications": {
            "queue_url": _scott_notification_queue_url(),
            "configured": bool(_scott_notification_queue_url() and _scott_notification_bearer()),
            "token_configured": bool(_scott_notification_bearer()),
        },
        "totals": {
            "entries": int(total),
            "unresolved": int(recent_unresolved),
        },
        "status_summary": {row[0]: int(row[1]) for row in status_rows},
        "risk_summary": {row[0]: int(row[1]) for row in risk_rows},
    }


def apply_recommended_resolution(inbox_id: int, db_path: str | None = None) -> dict[str, Any]:
    db = db_path or DB_PATH
    entry = get_governor_inbox_entry(inbox_id, db_path=db)
    if entry is None:
        raise KeyError(f"inbox_entry_not_found:{inbox_id}")
    recommendation = _normalize_recommended_resolution(entry.get("recommended_resolution"))
    if not recommendation:
        raise ValueError("recommended_resolution_missing")
    target_status = recommendation.get("target_inbox_status")
    if not target_status:
        raise ValueError("recommended_resolution_missing_target_status")
    review_notes = entry["review_notes"]
    action_note = recommendation.get("operator_action")
    if action_note and action_note not in review_notes:
        review_notes = _text_excerpt(f"{review_notes}\nApplied recommendation: {action_note}".strip(), limit=2000)
    return update_governor_inbox_entry(
        inbox_id,
        status=str(target_status),
        review_notes=review_notes,
        recommended_resolution=recommendation,
        db_path=db,
    )


def forward_governor_inbox_entry(
    inbox_id: int,
    *,
    db_path: str | None = None,
    targets: list[str] | None = None,
) -> dict[str, Any]:
    db = db_path or DB_PATH
    init_sophia_governor_inbox_schema(db)
    entry = get_governor_inbox_entry(inbox_id, db_path=db)
    if entry is None:
        raise KeyError(f"inbox_entry_not_found:{inbox_id}")

    resolved_targets = [target for target in (targets or _forward_targets()) if target]
    if not resolved_targets:
        return {"status": "not_configured", "attempts": []}

    payload = _build_forward_payload(entry)
    attempts: list[dict[str, Any]] = []
    delivered = False
    auto_applied = False
    scott_notification: dict[str, Any] = {"status": "not_attempted"}
    latest_review_notes = entry["review_notes"]
    latest_assigned_agent = entry["assigned_agent"]
    latest_recommended_resolution = entry["recommended_resolution"]

    for target in resolved_targets:
        transport = "http"
        try:
            status, response_code, response_body = _deliver_forward_http_target(target, payload)
        except Exception as exc:
            status = "failed"
            response_code = None
            response_body = _text_excerpt(exc, 800)

        attempt = {
            "target": target,
            "transport": transport,
            "status": status,
            "response_code": response_code,
            "response_body": response_body,
        }
        attempts.append(attempt)
        _record_forward_attempt(
            db,
            inbox_id=inbox_id,
            target=target,
            transport=transport,
            request_payload=payload,
            status=status,
            response_code=response_code,
            response_body=response_body,
        )
        if status == "delivered":
            delivered = True
            parsed_response = _parse_forward_response(response_body)
            review_text = _text_excerpt(parsed_response.get("review"), 2000)
            if review_text:
                latest_review_notes = review_text
            review_service = _text_excerpt(parsed_response.get("service"), 200)
            if review_service:
                latest_assigned_agent = review_service
            latest_recommended_resolution = _normalize_recommended_resolution(
                parsed_response.get("recommended_resolution")
            ) or latest_recommended_resolution

    if delivered:
        updated_entry = update_governor_inbox_entry(
            inbox_id,
            status="forwarded" if entry["status"] in {"received", "reviewing"} else entry["status"],
            assigned_agent=latest_assigned_agent,
            review_notes=latest_review_notes,
            recommended_resolution=latest_recommended_resolution,
            db_path=db,
        )
        if _should_auto_apply_recommended_resolution(updated_entry.get("recommended_resolution")):
            updated_entry = apply_recommended_resolution(inbox_id, db_path=db)
            auto_applied = True
        scott_notification = _queue_scott_notification_for_entry(
            inbox_id,
            phase="review",
            db_path=db,
        )

    return {
        "status": "delivered" if delivered else attempts[-1]["status"],
        "attempts": attempts,
        "auto_applied": auto_applied,
        "scott_notification": scott_notification,
    }


def register_sophia_governor_inbox_endpoints(app, db_path: str | None = None) -> None:
    """Register Flask endpoints for upstream governor escalations."""
    db = db_path or DB_PATH
    init_sophia_governor_inbox_schema(db)

    @app.route("/api/sophia/governor/bridge/status", methods=["GET"])
    def sophia_governor_bridge_status():
        return jsonify(get_governor_inbox_status(db))

    @app.route("/api/sophia/governor/ingest", methods=["POST"])
    def sophia_governor_ingest():
        if not _is_authorized(request):
            return jsonify({"error": "Unauthorized -- admin key or bearer required"}), 401

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "JSON object required"}), 400

        try:
            result = ingest_governor_envelope(data, db_path=db)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        forward_result = None
        if _auto_forward_enabled() and not result.get("duplicate"):
            forward_result = forward_governor_inbox_entry(
                result["inbox"]["inbox_id"],
                db_path=db,
            )
            refreshed_entry = get_governor_inbox_entry(result["inbox"]["inbox_id"], db_path=db)
            if refreshed_entry is not None:
                result["inbox"] = refreshed_entry

        return jsonify({"ok": True, **result, "forward": forward_result}), 202

    @app.route("/api/sophia/governor/inbox", methods=["GET"])
    def sophia_governor_inbox():
        if not _is_authorized(request):
            return jsonify({"error": "Unauthorized -- admin key or bearer required"}), 401

        limit = request.args.get("limit", 20, type=int)
        status = request.args.get("status")
        risk_level = request.args.get("risk_level")
        try:
            entries = list_governor_inbox_entries(
                db_path=db,
                limit=limit,
                status=status,
                risk_level=risk_level,
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        return jsonify({"ok": True, "entries": entries})

    @app.route("/api/sophia/governor/inbox/<int:inbox_id>", methods=["GET"])
    def sophia_governor_inbox_detail(inbox_id: int):
        if not _is_authorized(request):
            return jsonify({"error": "Unauthorized -- admin key or bearer required"}), 401

        entry = get_governor_inbox_entry(inbox_id, db_path=db)
        if entry is None:
            return jsonify({"error": "inbox_entry_not_found"}), 404
        return jsonify({"ok": True, "entry": entry})

    @app.route("/api/sophia/governor/inbox/<int:inbox_id>/status", methods=["POST"])
    def sophia_governor_inbox_update(inbox_id: int):
        if not _is_authorized(request):
            return jsonify({"error": "Unauthorized -- admin key or bearer required"}), 401

        data = request.get_json(silent=True) or {}
        try:
            updated = update_governor_inbox_entry(
                inbox_id,
                status=data.get("status"),
                assigned_agent=data.get("assigned_agent"),
                review_notes=data.get("review_notes"),
                recommended_resolution=data.get("recommended_resolution"),
                db_path=db,
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except KeyError:
            return jsonify({"error": "inbox_entry_not_found"}), 404

        return jsonify({"ok": True, "entry": updated})

    @app.route("/api/sophia/governor/inbox/<int:inbox_id>/forward", methods=["POST"])
    def sophia_governor_inbox_forward(inbox_id: int):
        if not _is_authorized(request):
            return jsonify({"error": "Unauthorized -- admin key or bearer required"}), 401

        data = request.get_json(silent=True) or {}
        targets = data.get("targets")
        if targets is not None and not isinstance(targets, list):
            return jsonify({"error": "targets must be a list of URLs"}), 400
        clean_targets = [str(target).strip() for target in (targets or []) if str(target).strip()]

        try:
            result = forward_governor_inbox_entry(
                inbox_id,
                db_path=db,
                targets=clean_targets or None,
            )
        except KeyError:
            return jsonify({"error": "inbox_entry_not_found"}), 404

        return jsonify({"ok": True, "result": result, "entry": get_governor_inbox_entry(inbox_id, db_path=db)})

    @app.route("/api/sophia/governor/inbox/<int:inbox_id>/apply-recommended-resolution", methods=["POST"])
    def sophia_governor_inbox_apply_recommended(inbox_id: int):
        if not _is_authorized(request):
            return jsonify({"error": "Unauthorized -- admin key or bearer required"}), 401
        try:
            updated = apply_recommended_resolution(inbox_id, db_path=db)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except KeyError:
            return jsonify({"error": "inbox_entry_not_found"}), 404
        return jsonify({"ok": True, "entry": updated})
