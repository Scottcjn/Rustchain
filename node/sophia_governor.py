#!/usr/bin/env python3
"""
RIP-307: Sophia RustChain Governor
==================================

Small, local Sophia governance layer for RustChain.

The governor is intentionally two-tiered:
  1. Deterministic local triage for speed and safety.
  2. Optional "phone home" escalation to bigger Sophia/Elyan agents.

This keeps routine chain decisions cheap and portable while preserving a
clear path upward for high-risk proposals, suspicious transfers, or other
events that deserve a larger mind.
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

from flask import jsonify, request

try:
    import requests
except ImportError:  # pragma: no cover - dependency is expected in production
    requests = None

try:
    from sophianet.core import build_portable_continuity_packet
except Exception:  # pragma: no cover - keep governor portable
    build_portable_continuity_packet = None

log = logging.getLogger("sophia-governor")
if not log.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("[GOVERNOR] %(asctime)s %(levelname)s %(message)s"))
    log.addHandler(_handler)
    log.setLevel(logging.INFO)

DB_PATH = os.getenv("RUSTCHAIN_DB_PATH", "/root/rustchain/rustchain_v2.db")
DEFAULT_CONTINUITY_PACKET_PATH = Path(
    os.getenv(
        "SOPHIA_GOVERNOR_CONTINUITY_PACKET",
        "/home/scott/chatgpt-live-analysis/portable/sophiacore_portable_packet.json",
    )
)

ROUTE_LOCAL_ONLY = "local_only"
ROUTE_LOCAL_THEN_PHONE_HOME = "local_then_phone_home"
ROUTE_IMMEDIATE_PHONE_HOME = "immediate_phone_home"

RISK_LEVELS = ("low", "medium", "high", "critical")
STANCE_VALUES = ("allow", "watch", "hold", "escalate")
TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}

GOVERNOR_SCHEMA = """
CREATE TABLE IF NOT EXISTS sophia_governor_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    source TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    route TEXT NOT NULL,
    stance TEXT NOT NULL,
    needs_escalation INTEGER DEFAULT 0,
    escalation_status TEXT DEFAULT 'not_needed',
    payload_json TEXT NOT NULL,
    decision_json TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sophia_governor_event_type
    ON sophia_governor_events(event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sophia_governor_escalation
    ON sophia_governor_events(needs_escalation, created_at DESC);

CREATE TABLE IF NOT EXISTS sophia_governor_phone_home (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    target TEXT NOT NULL,
    transport TEXT NOT NULL,
    request_json TEXT NOT NULL,
    status TEXT NOT NULL,
    response_code INTEGER,
    response_body TEXT,
    created_at INTEGER NOT NULL,
    FOREIGN KEY(event_id) REFERENCES sophia_governor_events(id)
);
CREATE INDEX IF NOT EXISTS idx_sophia_governor_phone_home_event
    ON sophia_governor_phone_home(event_id, created_at DESC);
"""


def init_sophia_governor_schema(db_path: str | None = None) -> None:
    """Create governor tables if they do not exist."""
    with sqlite3.connect(db_path or DB_PATH) as conn:
        conn.executescript(GOVERNOR_SCHEMA)
        conn.commit()


def _now() -> int:
    return int(time.time())


def _safe_json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _env_truthy(name: str, default: str = "false") -> bool:
    return str(os.getenv(name, default)).strip().lower() in TRUE_VALUES


def _governor_llm_mode() -> str:
    return str(os.getenv("SOPHIA_GOVERNOR_ENABLE_LLM", "auto")).strip().lower()


def _llm_enabled() -> bool:
    mode = _governor_llm_mode()
    if mode in TRUE_VALUES:
        return True
    if mode in FALSE_VALUES:
        return False
    return bool(os.getenv("SOPHIA_GOVERNOR_LLM_URL") or os.getenv("SOPHIACORE_URL"))


def _transfer_warning_rtc() -> float:
    return float(os.getenv("SOPHIA_GOVERNOR_TRANSFER_WARNING_RTC", "1000"))


def _transfer_critical_rtc() -> float:
    return float(os.getenv("SOPHIA_GOVERNOR_TRANSFER_CRITICAL_RTC", "10000"))


def _max_recent_rows() -> int:
    return max(1, min(int(os.getenv("SOPHIA_GOVERNOR_MAX_RECENT", "50")), 200))


def _parse_csv_env(name: str) -> list[str]:
    raw = os.getenv(name, "")
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _phone_home_targets() -> list[str]:
    targets = _parse_csv_env("SOPHIA_GOVERNOR_PHONE_HOME_TARGETS")
    if targets:
        return targets
    inbox_url = os.getenv("SOPHIA_GOVERNOR_INBOX_URL", "").strip()
    if inbox_url:
        return [inbox_url]
    return _parse_csv_env("SOPHIA_GOVERNOR_PHONE_HOME_URLS")


def _phone_home_timeouts() -> tuple[float, float]:
    connect_timeout = float(os.getenv("SOPHIA_GOVERNOR_PHONE_HOME_CONNECT_TIMEOUT_SEC", "4"))
    read_timeout = float(os.getenv("SOPHIA_GOVERNOR_PHONE_HOME_READ_TIMEOUT_SEC", "120"))
    return max(1.0, connect_timeout), max(5.0, read_timeout)


def _text_excerpt(text: Any, limit: int = 260) -> str:
    if text is None:
        return ""
    value = re.sub(r"\s+", " ", str(text)).strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _payload_text(payload: dict[str, Any]) -> str:
    parts = []
    for key in ("title", "description", "reason", "message", "summary", "status"):
        value = payload.get(key)
        if value:
            parts.append(str(value))
    return " ".join(parts).strip()


def _detect_terms(text: str, terms: list[str]) -> list[str]:
    lowered = text.lower()
    return [term for term in terms if term in lowered]


def _risk_rank(value: str) -> int:
    try:
        return RISK_LEVELS.index(value)
    except ValueError:
        return 0


def _strongest_risk(left: str, right: str) -> str:
    return left if _risk_rank(left) >= _risk_rank(right) else right


def _load_continuity_packet() -> dict[str, Any]:
    packet_path = DEFAULT_CONTINUITY_PACKET_PATH
    if packet_path.exists():
        try:
            return json.loads(packet_path.read_text(encoding="utf-8"))
        except Exception as exc:
            log.warning("Failed to read continuity packet %s: %s", packet_path, exc)

    if build_portable_continuity_packet is None:
        return {}

    try:
        packet = build_portable_continuity_packet(topic="RustChain governance", limit=4)
        return packet.to_dict()
    except Exception as exc:
        log.warning("Failed to build continuity packet on demand: %s", exc)
        return {}


def _continuity_context() -> dict[str, Any]:
    packet = _load_continuity_packet()
    if not packet:
        return {"loaded": False}

    return {
        "loaded": True,
        "topic": packet.get("topic", ""),
        "bootstrap_block": _text_excerpt(packet.get("bootstrap_block", ""), 800),
        "elyan_prime_brief": _text_excerpt(packet.get("elyan_prime_brief", ""), 600),
        "runtime_governance_brief": _text_excerpt(packet.get("runtime_governance_brief", ""), 600),
    }


def _build_llm_prompt(event_type: str, payload: dict[str, Any], heuristic: dict[str, Any]) -> str:
    continuity = _continuity_context()
    prompt_lines = [
        "You are Sophia RustChain Governor, a small local Sophia process.",
        "Protect RustChain first. Stay concise, practical, and safety-minded.",
        "If the event is high-risk, ask for escalation instead of improvising.",
        "Return JSON only with keys: stance, risk_level, needs_escalation, message.",
        "",
        f"Event type: {event_type}",
        f"Deterministic baseline route: {heuristic['route']}",
        f"Deterministic baseline risk: {heuristic['risk_level']}",
        f"Deterministic baseline stance: {heuristic['stance']}",
        f"Event payload: {_safe_json_dumps(payload)}",
    ]
    if continuity.get("loaded"):
        prompt_lines.extend([
            "",
            "Continuity anchors:",
            continuity["bootstrap_block"],
            continuity["elyan_prime_brief"],
            continuity["runtime_governance_brief"],
        ])
    return "\n".join(line for line in prompt_lines if line)


def _local_llm_endpoints() -> list[str]:
    endpoints = []
    for env_name in ("SOPHIA_GOVERNOR_LLM_URL", "SOPHIACORE_URL"):
        value = os.getenv(env_name, "").strip()
        if value:
            endpoints.append(value)
    # Avoid surprise dial-outs in "auto" mode. Operators can enable explicitly.
    seen: set[str] = set()
    unique = []
    for endpoint in endpoints:
        if endpoint not in seen:
            seen.add(endpoint)
            unique.append(endpoint)
    return unique


def _extract_json_object(text: str) -> dict[str, Any] | None:
    text = (text or "").strip()
    if not text:
        return None

    for candidate in (text, _text_excerpt(text, 4000)):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _try_ollama_generate(base_url: str, prompt: str) -> tuple[str | None, str | None]:
    if requests is None:
        return None, None
    model = os.getenv("SOPHIA_GOVERNOR_MODEL", "elyan-sophia:7b-q4_K_M")
    response = requests.post(
        f"{base_url.rstrip('/')}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 180},
        },
        timeout=(4, 12),
    )
    if response.status_code == 200:
        body = response.json()
        return body.get("response", ""), model
    return None, None


def _try_llama_completion(base_url: str, prompt: str) -> tuple[str | None, str | None]:
    if requests is None:
        return None, None
    model = os.getenv("SOPHIA_GOVERNOR_MODEL", "elyan-sophia:7b-q4_K_M")
    response = requests.post(
        f"{base_url.rstrip('/')}/completion",
        json={"prompt": prompt, "temperature": 0.2, "n_predict": 180},
        timeout=(4, 12),
    )
    if response.status_code == 200:
        body = response.json()
        return body.get("content", ""), model
    return None, None


def _try_openai_completion(base_url: str, prompt: str) -> tuple[str | None, str | None]:
    if requests is None:
        return None, None
    model = os.getenv("SOPHIA_GOVERNOR_MODEL", "elyan-sophia:7b-q4_K_M")
    response = requests.post(
        f"{base_url.rstrip('/')}/v1/completions",
        json={
            "model": model,
            "prompt": prompt,
            "temperature": 0.2,
            "max_tokens": 180,
        },
        timeout=(4, 12),
    )
    if response.status_code == 200:
        body = response.json()
        choices = body.get("choices") or []
        if choices:
            return choices[0].get("text", ""), model
    return None, None


def _query_local_llm(event_type: str, payload: dict[str, Any], heuristic: dict[str, Any]) -> dict[str, Any] | None:
    if not _llm_enabled():
        return None
    if requests is None:
        return None

    endpoints = _local_llm_endpoints()
    if not endpoints:
        return None

    prompt = _build_llm_prompt(event_type, payload, heuristic)
    for endpoint in endpoints:
        try:
            for caller in (_try_llama_completion, _try_ollama_generate, _try_openai_completion):
                raw_text, model = caller(endpoint, prompt)
                if not raw_text:
                    continue
                parsed = _extract_json_object(raw_text)
                if not parsed:
                    continue
                return {
                    "provider": endpoint,
                    "model": model,
                    "stance": str(parsed.get("stance", "")).strip().lower(),
                    "risk_level": str(parsed.get("risk_level", "")).strip().lower(),
                    "needs_escalation": bool(parsed.get("needs_escalation")),
                    "message": _text_excerpt(parsed.get("message", raw_text), 500),
                }
        except Exception as exc:
            log.warning("Local governor LLM failed via %s: %s", endpoint, exc)
    return None


def _heuristic_review(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    payload = payload or {}
    text = _payload_text(payload).lower()
    risk_level = "low"
    route = ROUTE_LOCAL_ONLY
    stance = "allow"
    signals: list[str] = []
    recommended_actions: list[str] = []

    if event_type == "governance_proposal":
        critical_terms = [
            "freeze",
            "halt",
            "override",
            "bypass",
            "mint",
            "supply",
            "admin key",
            "withdraw",
            "bridge",
            "drain",
            "disable",
            "consensus",
        ]
        medium_terms = [
            "multiplier",
            "reward",
            "epoch",
            "parameter",
            "veto",
            "threshold",
            "quorum",
            "feature",
        ]
        critical_hits = _detect_terms(text, critical_terms)
        medium_hits = _detect_terms(text, medium_terms)
        if critical_hits:
            risk_level = "critical"
            route = ROUTE_IMMEDIATE_PHONE_HOME
            stance = "hold"
            signals.extend(critical_hits)
            recommended_actions.extend([
                "pause autonomous execution for this proposal",
                "request big-Sophia review before endorsement or rollout",
            ])
        elif medium_hits:
            risk_level = "medium"
            route = ROUTE_LOCAL_THEN_PHONE_HOME
            stance = "watch"
            signals.extend(medium_hits)
            recommended_actions.extend([
                "log the proposal in governor memory",
                "send a summary upstairs for architectural review",
            ])
        else:
            recommended_actions.append("keep proposal on local watchlist")

    elif event_type == "pending_transfer":
        amount_rtc = float(payload.get("amount_rtc") or 0.0)
        if not amount_rtc and payload.get("amount_i64") is not None:
            amount_rtc = float(payload["amount_i64"]) / 1_000_000.0
        reason_text = str(payload.get("reason", "")).lower()
        if amount_rtc >= _transfer_critical_rtc():
            risk_level = "critical"
            route = ROUTE_IMMEDIATE_PHONE_HOME
            stance = "hold"
            signals.append(f"amount>={_transfer_critical_rtc():.2f}rtc")
            recommended_actions.extend([
                "retain transfer in pending state",
                "page bigger Sophia agents immediately",
            ])
        elif amount_rtc >= _transfer_warning_rtc():
            risk_level = "high"
            route = ROUTE_LOCAL_THEN_PHONE_HOME
            stance = "watch"
            signals.append(f"amount>={_transfer_warning_rtc():.2f}rtc")
            recommended_actions.extend([
                "keep extra audit trail for the transfer",
                "send upstream summary before confirmation window closes",
            ])
        if any(term in reason_text for term in ("override", "manual", "hotfix", "urgent", "bridge")):
            risk_level = _strongest_risk(risk_level, "high")
            route = ROUTE_LOCAL_THEN_PHONE_HOME if route == ROUTE_LOCAL_ONLY else route
            stance = "watch" if stance == "allow" else stance
            signals.append("sensitive_reason")
            recommended_actions.append("review operator reason text")
        if not recommended_actions:
            recommended_actions.append("record the transfer and continue local monitoring")

    elif event_type == "attestation_verdict":
        verdict = str(payload.get("verdict", "")).upper()
        if verdict in {"REJECTED", "SUSPICIOUS"}:
            risk_level = "high" if verdict == "SUSPICIOUS" else "critical"
            route = ROUTE_IMMEDIATE_PHONE_HOME
            stance = "escalate"
            signals.append(verdict.lower())
            recommended_actions.extend([
                "lock deeper review onto the affected miner",
                "notify higher Sophia security agents",
            ])
        elif verdict == "CAUTIOUS":
            risk_level = "medium"
            route = ROUTE_LOCAL_THEN_PHONE_HOME
            stance = "watch"
            signals.append("cautious")
            recommended_actions.append("queue batch reinspection")
        else:
            recommended_actions.append("attestation looks routine")

    elif event_type == "node_health":
        status = str(payload.get("status", "unknown")).lower()
        if status not in {"ok", "healthy", "alive"}:
            risk_level = "high"
            route = ROUTE_LOCAL_THEN_PHONE_HOME
            stance = "watch"
            signals.append(status or "degraded")
            recommended_actions.extend([
                "collect fresh node diagnostics",
                "notify bigger Sophia agents if outage persists",
            ])
        else:
            recommended_actions.append("health looks normal")

    else:
        risk_level = "medium"
        route = ROUTE_LOCAL_THEN_PHONE_HOME
        stance = "watch"
        recommended_actions.append("unclassified event - keep local log and forward summary")

    needs_escalation = route != ROUTE_LOCAL_ONLY
    summary = f"{event_type} reviewed at {risk_level} risk with {stance} stance."
    if signals:
        summary += f" Signals: {', '.join(signals[:6])}."

    return {
        "event_type": event_type,
        "risk_level": risk_level,
        "route": route,
        "stance": stance,
        "needs_escalation": needs_escalation,
        "signals": signals,
        "recommended_actions": recommended_actions,
        "local_summary": summary,
    }


def _merge_llm_review(heuristic: dict[str, Any], llm_review: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(heuristic)
    if not llm_review:
        merged["llm_review"] = None
        return merged

    llm_risk = llm_review.get("risk_level")
    if llm_risk in RISK_LEVELS:
        merged["risk_level"] = _strongest_risk(merged["risk_level"], llm_risk)
    if llm_review.get("stance") in STANCE_VALUES:
        merged["stance"] = llm_review["stance"]
    if llm_review.get("needs_escalation"):
        merged["needs_escalation"] = True
        if merged["route"] == ROUTE_LOCAL_ONLY:
            merged["route"] = ROUTE_LOCAL_THEN_PHONE_HOME
    if llm_review.get("message"):
        merged["llm_summary"] = llm_review["message"]
    if llm_review.get("model"):
        merged["llm_model"] = llm_review["model"]
    if llm_review.get("provider"):
        merged["llm_provider"] = llm_review["provider"]
    merged["llm_review"] = llm_review
    return merged


def _store_event(
    db_path: str,
    *,
    event_type: str,
    source: str,
    payload: dict[str, Any],
    decision: dict[str, Any],
) -> int:
    now = _now()
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO sophia_governor_events
            (event_type, source, risk_level, route, stance, needs_escalation, escalation_status,
             payload_json, decision_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_type,
                source,
                decision["risk_level"],
                decision["route"],
                decision["stance"],
                1 if decision.get("needs_escalation") else 0,
                "pending" if decision.get("needs_escalation") else "not_needed",
                _safe_json_dumps(payload),
                _safe_json_dumps(decision),
                now,
                now,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def _update_event_escalation(db_path: str, event_id: int, escalation_status: str, decision: dict[str, Any]) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE sophia_governor_events
            SET escalation_status = ?, decision_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (escalation_status, _safe_json_dumps(decision), _now(), event_id),
        )
        conn.commit()


def _record_phone_home_attempt(
    db_path: str,
    *,
    event_id: int,
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
            INSERT INTO sophia_governor_phone_home
            (event_id, target, transport, request_json, status, response_code, response_body, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
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


def _phone_home_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    bearer = os.getenv("SOPHIA_GOVERNOR_PHONE_HOME_BEARER", "").strip()
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    admin_key = os.getenv("RC_ADMIN_KEY", "").strip()
    if admin_key:
        headers["X-Admin-Key"] = admin_key
    return headers


def _build_phone_home_envelope(event_id: int, event_type: str, source: str, payload: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "source": source,
        "created_at": _now(),
        "decision": decision,
        "payload": payload,
        "continuity": _continuity_context(),
        "governor": {
            "agent": "sophia-rustchain-governor",
            "instance": os.getenv("HOSTNAME", "rustchain-node"),
        },
    }


def _deliver_http_target(target: str, envelope: dict[str, Any]) -> tuple[str, int | None, str]:
    if requests is None:
        return "requests_unavailable", None, "requests library unavailable"
    connect_timeout, read_timeout = _phone_home_timeouts()
    response = requests.post(
        target,
        json=envelope,
        headers=_phone_home_headers(),
        timeout=(connect_timeout, read_timeout),
    )
    body = _text_excerpt(response.text, 600)
    status = "delivered" if response.status_code < 400 else "failed"
    return status, response.status_code, body


def _deliver_beacon_target(target: str, envelope: dict[str, Any]) -> tuple[str, int | None, str]:
    beacon_url = os.getenv("SOPHIA_GOVERNOR_BEACON_MESSAGE_URL", "").strip()
    if not beacon_url:
        return "not_configured", None, "SOPHIA_GOVERNOR_BEACON_MESSAGE_URL missing"
    agent_id = target.split("://", 1)[1]
    relay_payload = {
        "from": os.getenv("SOPHIA_GOVERNOR_BEACON_FROM", "bcn_sophia_rustchain_governor"),
        "to": agent_id,
        "type": "governance_review",
        "content": _safe_json_dumps(
            {
                "event_id": envelope["event_id"],
                "event_type": envelope["event_type"],
                "risk_level": envelope["decision"]["risk_level"],
                "stance": envelope["decision"]["stance"],
                "summary": envelope["decision"].get("llm_summary") or envelope["decision"].get("local_summary"),
            }
        ),
        "payload": envelope,
    }
    return _deliver_http_target(beacon_url, relay_payload)


def _phone_home(
    db_path: str,
    *,
    event_id: int,
    event_type: str,
    source: str,
    payload: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    targets = _phone_home_targets()
    if not targets:
        return {"status": "not_configured", "attempts": []}

    envelope = _build_phone_home_envelope(event_id, event_type, source, payload, decision)
    attempts: list[dict[str, Any]] = []
    delivered = False

    for target in targets:
        transport = "beacon" if target.startswith("beacon://") else "http"
        try:
            if transport == "beacon":
                status, response_code, response_body = _deliver_beacon_target(target, envelope)
            else:
                status, response_code, response_body = _deliver_http_target(target, envelope)
        except Exception as exc:
            status = "failed"
            response_code = None
            response_body = _text_excerpt(exc, 600)

        attempt = {
            "target": target,
            "transport": transport,
            "status": status,
            "response_code": response_code,
            "response_body": response_body,
        }
        attempts.append(attempt)
        _record_phone_home_attempt(
            db_path,
            event_id=event_id,
            target=target,
            transport=transport,
            request_payload=envelope,
            status=status,
            response_code=response_code,
            response_body=response_body,
        )
        if status == "delivered":
            delivered = True

    return {
        "status": "delivered" if delivered else attempts[-1]["status"],
        "attempts": attempts,
    }


def review_rustchain_event(
    *,
    event_type: str,
    source: str,
    payload: dict[str, Any],
    db_path: str | None = None,
    auto_phone_home: bool = True,
) -> dict[str, Any]:
    """Review a RustChain event locally and optionally escalate it."""
    db = db_path or DB_PATH
    init_sophia_governor_schema(db)

    heuristic = _heuristic_review(event_type, payload)
    llm_review = _query_local_llm(event_type, payload, heuristic)
    decision = _merge_llm_review(heuristic, llm_review)

    event_id = _store_event(
        db,
        event_type=event_type,
        source=source,
        payload=payload,
        decision=decision,
    )

    escalation = {"status": "not_needed", "attempts": []}
    if decision.get("needs_escalation") and auto_phone_home:
        escalation = _phone_home(
            db,
            event_id=event_id,
            event_type=event_type,
            source=source,
            payload=payload,
            decision=decision,
        )
    elif decision.get("needs_escalation"):
        escalation = {"status": "queued", "attempts": []}

    decision["event_id"] = event_id
    decision["source"] = source
    decision["escalation"] = escalation
    _update_event_escalation(db, event_id, escalation["status"], decision)
    return decision


def get_governor_event(event_id: int, db_path: str | None = None) -> dict[str, Any] | None:
    db = db_path or DB_PATH
    init_sophia_governor_schema(db)
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM sophia_governor_events WHERE id = ?",
            (event_id,),
        ).fetchone()
        if not row:
            return None
        payload = json.loads(row["payload_json"])
        decision = json.loads(row["decision_json"])
        decision["event_id"] = row["id"]
        decision["source"] = row["source"]
        return {
            "event_id": row["id"],
            "event_type": row["event_type"],
            "source": row["source"],
            "risk_level": row["risk_level"],
            "route": row["route"],
            "stance": row["stance"],
            "needs_escalation": bool(row["needs_escalation"]),
            "escalation_status": row["escalation_status"],
            "payload": payload,
            "decision": decision,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


def get_recent_governor_events(db_path: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    db = db_path or DB_PATH
    init_sophia_governor_schema(db)
    limit = max(1, min(int(limit), _max_recent_rows()))
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, event_type, source, risk_level, route, stance,
                   needs_escalation, escalation_status, decision_json,
                   created_at, updated_at
            FROM sophia_governor_events
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    events = []
    for row in rows:
        decision = json.loads(row["decision_json"])
        events.append(
            {
                "event_id": row["id"],
                "event_type": row["event_type"],
                "source": row["source"],
                "risk_level": row["risk_level"],
                "route": row["route"],
                "stance": row["stance"],
                "needs_escalation": bool(row["needs_escalation"]),
                "escalation_status": row["escalation_status"],
                "local_summary": decision.get("local_summary"),
                "llm_summary": decision.get("llm_summary"),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
    return events


def get_governor_status(db_path: str | None = None) -> dict[str, Any]:
    db = db_path or DB_PATH
    init_sophia_governor_schema(db)
    with sqlite3.connect(db) as conn:
        total = conn.execute("SELECT COUNT(*) FROM sophia_governor_events").fetchone()[0]
        escalated = conn.execute(
            "SELECT COUNT(*) FROM sophia_governor_events WHERE needs_escalation = 1"
        ).fetchone()[0]
        delivered = conn.execute(
            "SELECT COUNT(*) FROM sophia_governor_events WHERE escalation_status = 'delivered'"
        ).fetchone()[0]
        recent_rows = conn.execute(
            """
            SELECT risk_level, COUNT(*) AS count
            FROM sophia_governor_events
            GROUP BY risk_level
            """
        ).fetchall()

    return {
        "service": "sophia-rustchain-governor",
        "status": "ok",
        "llm_enabled": _llm_enabled(),
        "llm_mode": _governor_llm_mode(),
        "llm_endpoints": _local_llm_endpoints(),
        "phone_home_targets": _phone_home_targets(),
        "continuity_loaded": bool(_continuity_context().get("loaded")),
        "totals": {
            "events": int(total),
            "escalated": int(escalated),
            "delivered": int(delivered),
        },
        "risk_summary": {row[0]: int(row[1]) for row in recent_rows},
    }


def retry_phone_home(event_id: int, db_path: str | None = None) -> dict[str, Any]:
    record = get_governor_event(event_id, db_path=db_path)
    if record is None:
        raise KeyError(f"Governor event {event_id} not found")

    escalation = _phone_home(
        db_path or DB_PATH,
        event_id=event_id,
        event_type=record["event_type"],
        source=record["source"],
        payload=record["payload"],
        decision=record["decision"],
    )
    updated_decision = dict(record["decision"])
    updated_decision["escalation"] = escalation
    _update_event_escalation(db_path or DB_PATH, event_id, escalation["status"], updated_decision)
    return {"event_id": event_id, "escalation": escalation}


def register_sophia_governor_endpoints(app, db_path: str | None = None) -> None:
    """Register Flask endpoints for the RustChain governor."""
    db = db_path or DB_PATH
    init_sophia_governor_schema(db)

    def _is_admin(req) -> bool:
        required = os.getenv("RC_ADMIN_KEY", "").strip()
        if not required:
            return False
        provided = (req.headers.get("X-Admin-Key") or req.headers.get("X-API-Key") or "").strip()
        return bool(provided and hmac.compare_digest(provided, required))

    @app.route("/sophia/governor/status", methods=["GET"])
    def sophia_governor_status():
        return jsonify(get_governor_status(db))

    @app.route("/sophia/governor/recent", methods=["GET"])
    def sophia_governor_recent():
        raw_limit = request.args.get("limit", "20")
        try:
            limit = int(raw_limit)
        except (ValueError, TypeError):
            return jsonify({"error": "limit must be a positive integer"}), 400
        if limit < 1:
            return jsonify({"error": "limit must be a positive integer"}), 400
        return jsonify({
            "ok": True,
            "events": get_recent_governor_events(db_path=db, limit=limit),
        })

    @app.route("/sophia/governor/review", methods=["POST"])
    def sophia_governor_review():
        if not _is_admin(request):
            return jsonify({"error": "Unauthorized -- admin key required"}), 401
        data = request.get_json(silent=True) or {}
        event_type = str(data.get("event_type", "")).strip()
        source = str(data.get("source", "manual")).strip() or "manual"
        payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
        if not event_type:
            return jsonify({"error": "event_type required"}), 400
        result = review_rustchain_event(
            event_type=event_type,
            source=source,
            payload=payload,
            db_path=db,
            auto_phone_home=True,
        )
        return jsonify({"ok": True, "review": result})

    @app.route("/sophia/governor/retry/<int:event_id>", methods=["POST"])
    def sophia_governor_retry(event_id: int):
        if not _is_admin(request):
            return jsonify({"error": "Unauthorized -- admin key required"}), 401
        try:
            result = retry_phone_home(event_id, db_path=db)
        except KeyError:
            return jsonify({"error": "event_not_found"}), 404
        return jsonify({"ok": True, "result": result})
