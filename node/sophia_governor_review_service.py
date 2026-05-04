#!/usr/bin/env python3
"""
Sophia Governor Review Service
==============================

Lightweight production receiver for forwarded RustChain governor escalations.
It stores incoming reviews locally and asks a larger model for a concise
recommendation, without depending on the full Sophia agent stack.
"""

from __future__ import annotations

import json
import os
import hmac
import re
import sqlite3
import time
from typing import Any

from flask import Flask, jsonify, request

try:
    import requests
except ImportError:  # pragma: no cover - expected in production
    requests = None

app = Flask(__name__)

DB_PATH = os.getenv("SOPHIA_GOVERNOR_REVIEW_DB", "/tmp/sophia_governor_review.db")
OLLAMA_URL = os.getenv("SOPHIA_GOVERNOR_OLLAMA_URL", "http://192.168.0.160:11434")
OLLAMA_MODEL = os.getenv("SOPHIA_GOVERNOR_REVIEW_MODEL", "glm-4.7-flash:latest")
SCOTT_NOTIFICATION_QUEUE_URL = os.getenv("SCOTT_NOTIFICATION_QUEUE_URL", "").strip()
SCOTT_NOTIFICATION_SERVICE_TOKEN = os.getenv("SCOTT_NOTIFICATION_SERVICE_TOKEN", "elya2025").strip()
TRUE_VALUES = {"1", "true", "yes", "on"}
SECTION_PATTERN = re.compile(
    r"(?is)(?:\*\*|\b)(assessment|analysis(?: of the event)?|reasoning|risk|next step|next steps|recommended action|action|decision)\s*:\s*"
)

REVIEW_SCHEMA = """
CREATE TABLE IF NOT EXISTS sophia_governor_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inbox_id INTEGER,
    event_type TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    stance TEXT NOT NULL,
    source TEXT NOT NULL,
    remote_agent TEXT,
    remote_instance TEXT,
    summary TEXT,
    request_json TEXT NOT NULL,
    review_text TEXT,
    recommended_resolution_json TEXT DEFAULT '{}',
    model_used TEXT,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sophia_governor_reviews_inbox
    ON sophia_governor_reviews(inbox_id, created_at DESC);
"""


def init_db(db_path: str | None = None) -> None:
    with sqlite3.connect(db_path or DB_PATH) as conn:
        conn.executescript(REVIEW_SCHEMA)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(sophia_governor_reviews)")}
        if "recommended_resolution_json" not in columns:
            conn.execute("ALTER TABLE sophia_governor_reviews ADD COLUMN recommended_resolution_json TEXT DEFAULT '{}'")
        conn.commit()


def _now() -> int:
    return int(time.time())


def _safe_json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _text_excerpt(text: Any, limit: int = 800) -> str:
    if text is None:
        return ""
    value = " ".join(str(text).split()).strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _clean_review_text(text: Any, limit: int = 280) -> str:
    if text is None:
        return ""
    value = str(text)
    value = re.sub(r"[`*#>]+", "", value)
    value = re.sub(r"\s+", " ", value).strip(" \t\r\n-:")
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _first_sentences(text: str, count: int = 2, limit: int = 260) -> str:
    cleaned = _clean_review_text(text, limit=max(limit * 2, 4000))
    if not cleaned:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    selected: list[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        candidate = " ".join(selected + [part]).strip()
        if len(candidate) > limit and selected:
            break
        selected.append(part)
        if len(selected) >= count:
            break
    return _clean_review_text(" ".join(selected) or cleaned, limit=limit)


def _compact_action_text(text: str, limit: int = 220) -> str:
    cleaned = _clean_review_text(text, limit=max(limit * 3, 1200))
    if not cleaned:
        return ""
    cleaned = re.sub(r"^\d+\.\s*", "", cleaned)
    fragments = re.split(
        r"\s+(?:\d+\.\s+|Committee Review:\s+|Verify Intent:\s+|Investigate:\s+|Decision:\s+|Rationale:?\s+|Next Steps?:\s+|Since\b|If the transaction\b|If confirmed\b)",
        cleaned,
        maxsplit=1,
    )
    return _first_sentences(fragments[0], count=1, limit=limit)


def _env_truthy(name: str, default: str = "false") -> bool:
    return str(os.getenv(name, default)).strip().lower() in TRUE_VALUES


def _bearer_tokens() -> set[str]:
    raw = os.getenv("SOPHIA_GOVERNOR_REVIEW_BEARER", "").strip()
    if not raw:
        return set()
    return {token.strip() for token in raw.split(",") if token.strip()}


def _is_authorized(req) -> bool:
    required_admin = os.getenv("RC_ADMIN_KEY", "").strip()
    if required_admin:
        provided_admin = (req.headers.get("X-Admin-Key") or req.headers.get("X-API-Key") or "").strip()
        if provided_admin and hmac.compare_digest(provided_admin, required_admin):
            return True

    auth_header = (req.headers.get("Authorization") or "").strip()
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        if token and token in _bearer_tokens():
            return True

    return False


def _relay_scott_notification(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if requests is None:
        return 503, {"status": "error", "error": "requests_unavailable"}
    if not SCOTT_NOTIFICATION_QUEUE_URL:
        return 503, {"status": "error", "error": "scott_notification_queue_not_configured"}
    try:
        response = requests.post(
            SCOTT_NOTIFICATION_QUEUE_URL,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {SCOTT_NOTIFICATION_SERVICE_TOKEN}",
                "X-Sophia-Governor": "review-service",
            },
            timeout=(4, 20),
        )
    except Exception as exc:
        return 502, {"status": "error", "error": _text_excerpt(exc, 300)}

    try:
        body = response.json()
    except Exception:
        body = {"status": "error", "error": _text_excerpt(response.text, 600)}
    return response.status_code, body if isinstance(body, dict) else {"status": "error", "error": "invalid_response"}


def _coerce_entry(data: dict[str, Any]) -> dict[str, Any]:
    entry = data.get("entry")
    return entry if isinstance(entry, dict) else {}


def _review_summary(data: dict[str, Any], entry: dict[str, Any], event_type: str) -> str:
    if data.get("summary"):
        return str(data["summary"]).strip()
    decision = entry.get("decision")
    if isinstance(decision, dict):
        if decision.get("llm_summary"):
            return str(decision["llm_summary"]).strip()
        if decision.get("local_summary"):
            return str(decision["local_summary"]).strip()
    return f"{event_type} needs bigger-Sophia review."


def _default_next_step(stance: str) -> str:
    if stance == "allow":
        return "Allow with logging and keep the event in the audit trail."
    if stance == "hold":
        return "Hold execution until the event is reviewed by an operator."
    if stance == "watch":
        return "Keep the event under watch and require extra verification before confirmation."
    if stance == "escalate":
        return "Escalate immediately and require a human decision before confirmation."
    return "Escalate to human/operator review and preserve the audit trail."


def _resolution_type_from_action(next_step: str, stance: str) -> str:
    lowered = str(next_step or "").lower()
    if any(term in lowered for term in ("dismiss", "ignore", "false positive", "no action", "resolved test")):
        return "dismiss"
    if any(term in lowered for term in ("hold", "block", "freeze", "quarantine", "pause", "stop")):
        return "hold"
    if any(term in lowered for term in ("escalate", "committee", "human", "operator", "oversight", "review")):
        return "escalate"
    if any(term in lowered for term in ("allow", "approve", "proceed", "release", "confirm")):
        return "approve"
    if any(term in lowered for term in ("watch", "monitor", "verify", "scrutiny", "observe")):
        return "watch"
    return {
        "allow": "approve",
        "hold": "hold",
        "watch": "watch",
        "escalate": "escalate",
    }.get(stance, "escalate")


def _extract_sections(review_text: str) -> dict[str, str]:
    matches = list(SECTION_PATTERN.finditer(review_text or ""))
    if not matches:
        return {}

    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(review_text)
        content = _clean_review_text(review_text[start:end], limit=1200)
        heading = match.group(1).lower()
        if not content:
            continue
        if heading.startswith("assessment") or heading.startswith("analysis"):
            key = "assessment"
        elif heading == "reasoning":
            key = "assessment" if "assessment" not in sections else "risk"
        elif heading == "risk":
            key = "risk"
        else:
            key = "next_step"
        if key in sections:
            sections[key] = _clean_review_text(f"{sections[key]} {content}", limit=1200)
        else:
            sections[key] = content
    return sections


def _normalize_review_text(review_text: str, data: dict[str, Any]) -> str:
    entry = _coerce_entry(data)
    event_type = str(data.get("event_type") or entry.get("event_type") or "unknown").strip()
    risk_level = str(data.get("risk_level") or entry.get("risk_level") or "unknown").strip().lower()
    stance = str(data.get("stance") or entry.get("stance") or "watch").strip().lower()
    summary = _clean_review_text(_review_summary(data, entry, event_type), limit=240)
    raw = str(review_text or "").strip()
    sections = _extract_sections(raw)

    assessment = _first_sentences(sections.get("assessment", ""), count=1, limit=220)
    event_token = re.sub(r"[^a-z0-9]+", "", event_type.lower())
    assessment_token = re.sub(r"[^a-z0-9]+", "", assessment.lower())
    if (
        not assessment
        or assessment.lower().startswith("based on the event details")
        or (event_token and assessment_token.startswith(event_token))
        or assessment[:1].isdigit()
        or len(assessment) > 180
    ):
        assessment = summary or _first_sentences(raw, count=1, limit=220)
    assessment = _clean_review_text(assessment or summary or f"{event_type} reviewed.", limit=220)

    risk = sections.get("risk") or ""
    if risk:
        risk = _first_sentences(risk, count=1, limit=180)
        if risk_level and risk_level not in risk.lower():
            risk = f"{risk_level.capitalize()}. {risk}"
    else:
        risk = f"{risk_level.capitalize()}. {_default_next_step(stance)}"
        if stance in {"watch", "escalate"}:
            risk = f"{risk_level.capitalize()}. Event requires higher scrutiny before confirmation."

    next_step = _compact_action_text(sections.get("next_step", ""), limit=220)
    if not next_step:
        next_step = _default_next_step(stance)
    next_step = _clean_review_text(next_step, limit=240)

    return (
        f"Assessment: {assessment}\n"
        f"Risk: {risk}\n"
        f"Next step: {next_step}"
    )


def _build_recommended_resolution(review_text: str, data: dict[str, Any]) -> dict[str, Any]:
    entry = _coerce_entry(data)
    event_type = str(data.get("event_type") or entry.get("event_type") or "unknown").strip()
    risk_level = str(data.get("risk_level") or entry.get("risk_level") or "unknown").strip().lower()
    stance = str(data.get("stance") or entry.get("stance") or "watch").strip().lower()
    sections = _extract_sections(review_text)
    assessment = _clean_review_text(
        sections.get("assessment") or _review_summary(data, entry, event_type),
        limit=240,
    )
    next_step = _clean_review_text(
        sections.get("next_step") or _default_next_step(stance),
        limit=240,
    )
    resolution_type = _resolution_type_from_action(next_step, stance)
    target_status = "dismissed" if resolution_type == "dismiss" else "resolved"
    requires_human = (
        resolution_type in {"watch", "hold", "escalate"}
        or risk_level in {"high", "critical"}
        or any(term in next_step.lower() for term in ("committee", "human", "operator", "oversight"))
    )
    auto_apply = resolution_type in {"approve", "dismiss"} and not requires_human and risk_level in {"low", "medium"}
    return {
        "target_inbox_status": target_status,
        "resolution_type": resolution_type,
        "requires_human": requires_human,
        "auto_apply": auto_apply,
        "operator_action": next_step,
        "summary": assessment,
    }


def _build_prompt(data: dict[str, Any]) -> str:
    review_prompt = data.get("review_prompt")
    if review_prompt:
        return str(review_prompt).strip()

    entry = _coerce_entry(data)
    event_type = str(data.get("event_type") or entry.get("event_type") or "unknown").strip()
    risk_level = str(data.get("risk_level") or entry.get("risk_level") or "unknown").strip()
    stance = str(data.get("stance") or entry.get("stance") or "watch").strip()
    source = str(entry.get("source") or data.get("source") or "governor-inbox").strip()
    summary = _review_summary(data, entry, event_type)
    return (
        "You are Sophia Elya reviewing a RustChain governor escalation.\n"
        "Be concise, safety-minded, and practical.\n"
        "Return exactly 3 short lines and nothing else.\n"
        "Use this exact format:\n"
        "Assessment: <one short sentence>\n"
        "Risk: <one short sentence>\n"
        "Next step: <one short sentence>\n\n"
        f"Event type: {event_type}\n"
        f"Risk level: {risk_level}\n"
        f"Stance: {stance}\n"
        f"Source: {source}\n"
        f"Summary: {summary}\n"
        f"Payload: {_safe_json_dumps(entry.get('payload') or data.get('payload') or {})}"
    )


def _fallback_review_text(data: dict[str, Any]) -> str:
    entry = _coerce_entry(data)
    event_type = str(data.get("event_type") or entry.get("event_type") or "unknown").strip()
    risk_level = str(data.get("risk_level") or entry.get("risk_level") or "unknown").strip()
    stance = str(data.get("stance") or entry.get("stance") or "watch").strip()
    summary = _text_excerpt(_review_summary(data, entry, event_type), 500)
    next_step = _default_next_step(stance)
    return (
        f"Assessment: {summary}\n"
        f"Risk: {risk_level}.\n"
        f"Next step: {next_step}"
    )


def _call_ollama(prompt: str) -> tuple[str, str]:
    if requests is None:
        raise RuntimeError("requests library unavailable")

    response = requests.post(
        f"{OLLAMA_URL.rstrip('/')}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "think": _env_truthy("SOPHIA_GOVERNOR_REVIEW_ENABLE_THINKING", "false"),
            "options": {"temperature": 0.2, "num_predict": 350},
        },
        timeout=(5, 90),
    )
    response.raise_for_status()
    body = response.json()
    review_text = _text_excerpt(body.get("response", ""), 4000)
    if review_text:
        return review_text, OLLAMA_MODEL

    if _text_excerpt(body.get("thinking", ""), 2000):
        raise RuntimeError(f"Ollama returned thinking without final answer for model {OLLAMA_MODEL}")

    raise RuntimeError(f"Ollama returned no final text for model {OLLAMA_MODEL}")


def _store_review(
    data: dict[str, Any],
    review_text: str,
    model_used: str,
    recommended_resolution: dict[str, Any] | None = None,
    db_path: str | None = None,
) -> int:
    db = db_path or DB_PATH
    init_db(db)
    entry = _coerce_entry(data)
    with sqlite3.connect(db) as conn:
        cur = conn.execute(
            """
            INSERT INTO sophia_governor_reviews
            (inbox_id, event_type, risk_level, stance, source,
             remote_agent, remote_instance, summary, request_json, recommended_resolution_json,
             review_text, model_used, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data.get("inbox_id") or entry.get("inbox_id"),
                str(data.get("event_type") or entry.get("event_type") or "unknown").strip(),
                str(data.get("risk_level") or entry.get("risk_level") or "unknown").strip(),
                str(data.get("stance") or entry.get("stance") or "watch").strip(),
                str(entry.get("source") or data.get("source") or "governor-inbox").strip(),
                str(entry.get("remote_agent") or "").strip(),
                str(entry.get("remote_instance") or "").strip(),
                _text_excerpt(data.get("summary"), 1000),
                _safe_json_dumps(data),
                _safe_json_dumps(recommended_resolution or {}),
                review_text,
                model_used,
                _now(),
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def _recent_reviews(limit: int = 10, db_path: str | None = None) -> list[dict[str, Any]]:
    db = db_path or DB_PATH
    init_db(db)
    limit = max(1, min(int(limit), 100))
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, inbox_id, event_type, risk_level, stance, source,
                   remote_agent, remote_instance, summary, review_text,
                   recommended_resolution_json,
                   model_used, created_at
            FROM sophia_governor_reviews
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    results = []
    for row in rows:
        item = dict(row)
        try:
            item["recommended_resolution"] = json.loads(item.pop("recommended_resolution_json") or "{}")
        except Exception:
            item["recommended_resolution"] = {}
            item.pop("recommended_resolution_json", None)
        results.append(item)
    return results


def _reviews_missing_text(limit: int = 25, db_path: str | None = None) -> list[dict[str, Any]]:
    db = db_path or DB_PATH
    init_db(db)
    limit = max(1, min(int(limit), 200))
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, request_json
            FROM sophia_governor_reviews
            WHERE COALESCE(TRIM(review_text), '') = ''
            ORDER BY id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def _update_review_record(
    review_id: int,
    review_text: str,
    model_used: str,
    recommended_resolution: dict[str, Any] | None = None,
    db_path: str | None = None,
) -> None:
    db = db_path or DB_PATH
    init_db(db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            UPDATE sophia_governor_reviews
            SET review_text = ?, model_used = ?, recommended_resolution_json = ?
            WHERE id = ?
            """,
            (review_text, model_used, _safe_json_dumps(recommended_resolution or {}), int(review_id)),
        )
        conn.commit()


def _rebuild_review_row(review_id: int, request_json: str, db_path: str | None = None) -> dict[str, Any]:
    data = json.loads(request_json)
    prompt = _build_prompt(data)
    try:
        raw_review_text, model_used = _call_ollama(prompt)
        review_text = _normalize_review_text(raw_review_text, data)
    except Exception as exc:
        review_text = _normalize_review_text(_fallback_review_text(data), data)
        model_used = f"{OLLAMA_MODEL}@error"
    recommended_resolution = _build_recommended_resolution(review_text, data)
    _update_review_record(
        review_id,
        review_text,
        model_used,
        recommended_resolution,
        db_path=db_path,
    )
    return {
        "review_id": int(review_id),
        "model_used": model_used,
        "review_text": review_text,
        "recommended_resolution": recommended_resolution,
    }


def backfill_missing_reviews(limit: int = 25, db_path: str | None = None) -> list[dict[str, Any]]:
    missing = _reviews_missing_text(limit=limit, db_path=db_path)
    return [
        _rebuild_review_row(int(row["id"]), str(row["request_json"]), db_path=db_path)
        for row in missing
    ]


def _recent_review_rows(limit: int = 25, db_path: str | None = None) -> list[dict[str, Any]]:
    db = db_path or DB_PATH
    init_db(db)
    limit = max(1, min(int(limit), 200))
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, request_json, review_text, model_used
            FROM sophia_governor_reviews
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def normalize_existing_reviews(limit: int = 25, db_path: str | None = None) -> list[dict[str, Any]]:
    rows = _recent_review_rows(limit=limit, db_path=db_path)
    updated: list[dict[str, Any]] = []
    for row in rows:
        data = json.loads(str(row["request_json"]))
        source_text = str(row["review_text"] or "").strip() or _fallback_review_text(data)
        normalized = _normalize_review_text(source_text, data)
        model_used = str(row["model_used"] or OLLAMA_MODEL).strip() or OLLAMA_MODEL
        recommended_resolution = _build_recommended_resolution(normalized, data)
        _update_review_record(int(row["id"]), normalized, model_used, recommended_resolution, db_path=db_path)
        updated.append(
            {
                "review_id": int(row["id"]),
                "model_used": model_used,
                "review_text": normalized,
                "recommended_resolution": recommended_resolution,
            }
        )
    return updated


@app.route("/health", methods=["GET"])
@app.route("/api/sophia/governor/health", methods=["GET"])
def health():
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        total = conn.execute("SELECT COUNT(*) FROM sophia_governor_reviews").fetchone()[0]
    return jsonify(
        {
            "status": "ok",
            "service": "sophia-governor-review-service",
            "ollama_url": OLLAMA_URL,
            "model": OLLAMA_MODEL,
            "auth": {
                "admin_key_configured": bool(os.getenv("RC_ADMIN_KEY", "").strip()),
                "bearer_configured": bool(_bearer_tokens()),
            },
            "totals": {"reviews": int(total)},
        }
    )


@app.route("/recent", methods=["GET"])
@app.route("/api/sophia/governor/recent", methods=["GET"])
def recent():
    if not _is_authorized(request):
        return jsonify({"error": "Unauthorized -- admin key or bearer required"}), 401
    limit = request.args.get("limit", 10, type=int)
    return jsonify({"ok": True, "reviews": _recent_reviews(limit=limit)})


@app.route("/review/backfill-missing", methods=["POST"])
@app.route("/api/sophia/governor/review/backfill-missing", methods=["POST"])
def backfill_missing():
    if not _is_authorized(request):
        return jsonify({"error": "Unauthorized -- admin key or bearer required"}), 401
    data = request.get_json(silent=True) or {}
    limit = data.get("limit", 25) if isinstance(data, dict) else 25
    results = backfill_missing_reviews(limit=limit)
    return jsonify({"ok": True, "updated": results, "count": len(results)})


@app.route("/review/normalize-existing", methods=["POST"])
@app.route("/api/sophia/governor/review/normalize-existing", methods=["POST"])
def normalize_existing():
    if not _is_authorized(request):
        return jsonify({"error": "Unauthorized -- admin key or bearer required"}), 401
    data = request.get_json(silent=True) or {}
    limit = data.get("limit", 25) if isinstance(data, dict) else 25
    results = normalize_existing_reviews(limit=limit)
    return jsonify({"ok": True, "updated": results, "count": len(results)})


@app.route("/review", methods=["POST"])
@app.route("/api/sophia/governor/review", methods=["POST"])
def review():
    if not _is_authorized(request):
        return jsonify({"error": "Unauthorized -- admin key or bearer required"}), 401

    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "JSON object required"}), 400

    prompt = _build_prompt(data)
    try:
        raw_review_text, model_used = _call_ollama(prompt)
        review_text = _normalize_review_text(raw_review_text, data)
    except Exception:
        review_text = _normalize_review_text(_fallback_review_text(data), data)
        model_used = f"{OLLAMA_MODEL}@error"
    recommended_resolution = _build_recommended_resolution(review_text, data)

    review_id = _store_review(data, review_text, model_used, recommended_resolution)
    return jsonify(
        {
            "ok": True,
            "service": "sophia-governor-review-service",
            "review_id": review_id,
            "inbox_id": data.get("inbox_id") or _coerce_entry(data).get("inbox_id"),
            "event_type": data.get("event_type") or _coerce_entry(data).get("event_type"),
            "risk_level": data.get("risk_level") or _coerce_entry(data).get("risk_level"),
            "model_used": model_used,
            "review_prompt": prompt,
            "review": review_text,
            "recommended_resolution": recommended_resolution,
        }
    )


@app.route("/scott-notifications/queue", methods=["POST"])
@app.route("/api/sophia/governor/scott-notifications/queue", methods=["POST"])
def queue_scott_notification():
    if not _is_authorized(request):
        return jsonify({"error": "Unauthorized -- admin key or bearer required"}), 401

    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "JSON object required"}), 400

    status_code, body = _relay_scott_notification(data)
    return jsonify(body), status_code


def main():
    init_db()
    port = int(os.getenv("SOPHIA_GOVERNOR_REVIEW_PORT", "8091"))
    host = os.getenv("SOPHIA_GOVERNOR_REVIEW_HOST", "0.0.0.0")
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
