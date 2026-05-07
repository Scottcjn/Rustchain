#!/usr/bin/env python3
"""
RIP-306: SophiaCore Attestation Inspector
Sophia Elya validates hardware fingerprints via semantic coherence analysis.

Three-layer security:
  Layer 1: Algorithmic (6-point fingerprint checks) -- existing, every attestation
  Layer 2: SophiaCore Agent (this module) -- batch + on-demand
  Layer 3: Human spot-check -- admin dashboard (separate)
"""

import os
import hmac
import sys
import json
import time
import sqlite3
import hashlib
import argparse
import logging
import traceback
from typing import Optional, Tuple, Dict, List

try:
    import requests
except ImportError:
    requests = None  # Deferred — only needed at call time

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Ollama endpoints -- failover chain
OLLAMA_ENDPOINTS = [
    os.getenv("SOPHIACORE_URL", "http://localhost:11434"),       # Local Ollama
    "http://100.75.100.89:8080",                                 # POWER8 S824 llama-server
    "http://100.75.100.89:11434",                                # POWER8 S824 Ollama
    "http://192.168.0.160:11434",                                # Sophia NAS
]

# Dual-model strategy on POWER8:
#   - Regular inspections: elyan-sophia:7b (fast, 1-2s, batch-friendly)
#   - Deep analysis on SUSPICIOUS: GPT-OSS 120B MXFP4 (thorough, 30-60s)
MODEL = os.getenv("SOPHIACORE_MODEL", "elyan-sophia:7b-q4_K_M")
MODEL_DEEP = os.getenv("SOPHIACORE_MODEL_DEEP", "gpt-oss-120b")  # For SUSPICIOUS escalation
POWER8_SERVER_URL = os.getenv("POWER8_LLM_URL", "http://100.75.100.89:8080")

DB_PATH = os.getenv("RUSTCHAIN_DB_PATH", "/root/rustchain/rustchain_v2.db")

OLLAMA_TIMEOUT = 120   # seconds — POWER8 GPT-OSS 120B at ~2-5 tok/s needs generous timeout
DEEP_TIMEOUT = 180     # seconds for GPT-OSS 120B deep analysis (escalation)
BATCH_DELAY = 1.0      # seconds between inspections to avoid hammering

# Verdict constants
VERDICT_APPROVED = "APPROVED"
VERDICT_CAUTIOUS = "CAUTIOUS"
VERDICT_SUSPICIOUS = "SUSPICIOUS"
VERDICT_REJECTED = "REJECTED"

VERDICT_EMOJI = {
    VERDICT_APPROVED: "\u2728",    # sparkles
    VERDICT_CAUTIOUS: "\u26a0\ufe0f",   # warning
    VERDICT_SUSPICIOUS: "\U0001f50d",    # magnifying glass
    VERDICT_REJECTED: "\u274c",    # cross mark
}

VALID_VERDICTS = frozenset([VERDICT_APPROVED, VERDICT_CAUTIOUS, VERDICT_SUSPICIOUS, VERDICT_REJECTED])

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

log = logging.getLogger("sophia-inspector")
if not log.handlers:
    _h = logging.StreamHandler(sys.stderr)
    _h.setFormatter(logging.Formatter("[SOPHIA] %(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def ensure_schema(db_path: str = None):
    """Create sophia_inspections and sophia_overrides tables if they don't exist."""
    db_path = db_path or DB_PATH
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sophia_inspections (
                miner TEXT NOT NULL,
                inspection_ts INTEGER NOT NULL,
                verdict TEXT NOT NULL,
                confidence REAL NOT NULL,
                reasoning TEXT,
                model_version TEXT,
                fingerprint_hash TEXT,
                PRIMARY KEY (miner, inspection_ts)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sophia_insp_miner ON sophia_inspections(miner, inspection_ts DESC)"
        )
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sophia_overrides (
                miner TEXT NOT NULL,
                override_ts INTEGER NOT NULL,
                original_verdict TEXT NOT NULL,
                override_verdict TEXT NOT NULL,
                override_reason TEXT NOT NULL,
                admin_id TEXT NOT NULL,
                PRIMARY KEY (miner, override_ts)
            )
        """)
        conn.commit()

# ---------------------------------------------------------------------------
# Ollama interaction
# ---------------------------------------------------------------------------

def _try_ollama_api(ep: str, prompt: str) -> Optional[str]:
    """Try Ollama /api/generate endpoint."""
    url = f"{ep.rstrip('/')}/api/generate"
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 150},
    }
    resp = requests.post(url, json=payload, timeout=(10, OLLAMA_TIMEOUT))
    if resp.status_code == 200:
        return resp.json().get("response", "")
    return None


def _try_llamaserver_api(ep: str, prompt: str) -> Optional[str]:
    """Try llama-server native /completion endpoint (POWER8).

    GPT-OSS 120B runs at ~2-5 tok/s on POWER8 so we limit to 150 tokens
    and use a generous read timeout. The prompt asks for concise JSON so
    150 tokens is plenty for verdict + confidence + 2 sentence reasoning.
    """
    url = f"{ep.rstrip('/')}/completion"
    payload = {
        "prompt": prompt,
        "n_predict": 150,
        "temperature": 0.3,
    }
    resp = requests.post(url, json=payload, timeout=(10, OLLAMA_TIMEOUT))
    if resp.status_code == 200:
        return resp.json().get("content", "")
    return None


def _try_openai_api(ep: str, prompt: str) -> Optional[str]:
    """Try OpenAI-compatible /v1/completions endpoint."""
    url = f"{ep.rstrip('/')}/v1/completions"
    payload = {
        "prompt": prompt,
        "max_tokens": 300,
        "temperature": 0.3,
    }
    resp = requests.post(url, json=payload, timeout=OLLAMA_TIMEOUT)
    if resp.status_code == 200:
        choices = resp.json().get("choices", [])
        if choices:
            return choices[0].get("text", "")
    return None


def _call_ollama(prompt: str, endpoint: str = None) -> Optional[str]:
    """
    Send a generate request, trying each endpoint in the failover chain.
    Supports both Ollama API (/api/generate) and OpenAI-compatible (/v1/completions).
    Returns the response text or None if all endpoints fail.
    """
    if requests is None:
        log.error("requests library not available -- cannot call LLM")
        return None

    endpoints = [endpoint] if endpoint else list(OLLAMA_ENDPOINTS)

    for ep in endpoints:
        try:
            log.debug("Trying LLM at %s", ep)
            # Try llama-server native /completion first (POWER8)
            text = _try_llamaserver_api(ep, prompt)
            if text:
                log.info("Got response from %s via llama-server (%d chars)", ep, len(text))
                return text

            # Try Ollama API
            text = _try_ollama_api(ep, prompt)
            if text:
                log.info("Got response from %s via Ollama API (%d chars)", ep, len(text))
                return text

            # Fall back to OpenAI-compatible API
            text = _try_openai_api(ep, prompt)
            if text:
                log.info("Got response from %s via OpenAI API (%d chars)", ep, len(text))
                return text

            log.warning("LLM %s: no response from any API", ep)
        except requests.exceptions.Timeout:
            log.warning("LLM %s timed out after %ds", ep, OLLAMA_TIMEOUT)
        except requests.exceptions.ConnectionError:
            log.warning("LLM %s connection refused", ep)
        except Exception as exc:
            log.warning("LLM %s error: %s", ep, exc)

    log.error("All LLM endpoints failed -- SophiaCore unavailable")
    return None


def _call_deep_model(prompt: str) -> Optional[str]:
    """Call GPT-OSS 120B on POWER8 for deep analysis of SUSPICIOUS miners.

    The 120B model runs on the POWER8 S824 (512GB RAM) via llama-server.
    Used for escalation — when regular Sophia flags something as SUSPICIOUS,
    the big model gets a second opinion with deeper reasoning.
    """
    if requests is None:
        return None

    # POWER8 llama-server uses OpenAI-compatible /v1/completions
    url = f"{POWER8_SERVER_URL.rstrip('/')}/v1/completions"
    payload = {
        "model": MODEL_DEEP,
        "prompt": prompt,
        "max_tokens": 500,
        "temperature": 0.2,  # Even lower for analytical precision
    }

    try:
        log.info("Escalating to GPT-OSS 120B on POWER8 for deep analysis...")
        resp = requests.post(url, json=payload, timeout=DEEP_TIMEOUT)
        if resp.status_code == 200:
            body = resp.json()
            # llama-server returns choices[0].text for /v1/completions
            choices = body.get("choices", [])
            if choices:
                text = choices[0].get("text", "")
                if text:
                    log.info("Deep analysis complete (%d chars)", len(text))
                    return text
        log.warning("POWER8 deep model returned HTTP %d", resp.status_code)
    except requests.exceptions.Timeout:
        log.warning("POWER8 deep model timed out after %ds", DEEP_TIMEOUT)
    except Exception as exc:
        log.warning("POWER8 deep model error: %s", exc)

    return None


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def _build_inspection_prompt(miner_id: str, device: dict, fingerprint: dict, history: list = None) -> str:
    """Build the inspection prompt for Sophia Elya."""
    device = device or {}
    fingerprint = fingerprint or {}

    device_family = device.get("device_family") or device.get("family", "unknown")
    device_arch = device.get("device_arch") or device.get("arch", "unknown")
    cpu_brand = device.get("cpu_brand") or device.get("model", "unknown")
    machine = device.get("machine", "unknown")

    # Pretty-print fingerprint data (truncate if huge)
    fp_str = json.dumps(fingerprint, indent=2, default=str)
    if len(fp_str) > 3000:
        fp_str = fp_str[:3000] + "\n... (truncated)"

    history_section = ""
    if history:
        history_lines = []
        for entry in history[-5:]:  # last 5 entries
            ts = entry.get("ts", 0)
            profile = entry.get("profile", {})
            ts_str = time.strftime("%Y-%m-%d %H:%M", time.gmtime(ts)) if ts else "?"
            history_lines.append(f"  {ts_str}: clock_cv={profile.get('clock_drift_cv', '?')}, "
                                 f"thermal_var={profile.get('thermal_variance', '?')}, "
                                 f"jitter_cv={profile.get('jitter_cv', '?')}, "
                                 f"cache_ratio={profile.get('cache_hierarchy_ratio', '?')}")
        history_section = "Previous attestation history (most recent last):\n" + "\n".join(history_lines)

    prompt = f"""You are Sophia Elya, the attestation inspector for RustChain.
You are examining hardware fingerprint data from miner "{miner_id}".

Device claims: {device_family} / {device_arch}
CPU: {cpu_brand}
Machine: {machine}

Fingerprint data:
{fp_str}

{history_section}

Evaluate the COHERENCE of this fingerprint bundle.
Does the hardware evidence match the claimed architecture?
Are the timing/thermal/SIMD characteristics consistent with real {device_arch} silicon?

Look for:
- Impossible values (negative drift, zero variance)
- Uncorrelated metrics (old CPU but modern timing)
- Feature mismatch (claims G4 but has AVX)
- Too-perfect data (real hardware is messy)
- Sudden changes from previous attestations

Reply with a single line of JSON. No other text. Use these exact keys:
verdict (APPROVED or CAUTIOUS or SUSPICIOUS or REJECTED), confidence (0.0 to 1.0), reasoning (one sentence).

{{"verdict": "APPROVED", "confidence": """

    return prompt

# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _parse_verdict(response_text: str) -> Tuple[str, float, str]:
    """
    Parse Sophia's response.  Extract verdict, confidence, reasoning from JSON.
    Handle malformed responses gracefully -- default to CAUTIOUS with 0.5 confidence.
    """
    if not response_text:
        return VERDICT_CAUTIOUS, 0.5, "SophiaCore returned empty response"

    # Try to find JSON in the response (model may emit preamble text)
    text = response_text.strip()

    # The prompt ends with '{"verdict": "APPROVED", "confidence": ' so the model continues.
    # Prepend the prefix if the response doesn't start with '{'
    if not text.startswith("{"):
        text = '{"verdict": "APPROVED", "confidence": ' + text

    # Look for JSON object boundaries
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        json_str = text[start:end + 1]
        try:
            data = json.loads(json_str)

            verdict = str(data.get("verdict", VERDICT_CAUTIOUS)).upper().strip()
            if verdict not in VALID_VERDICTS:
                verdict = VERDICT_CAUTIOUS

            try:
                confidence = float(data.get("confidence", 0.5))
                confidence = max(0.0, min(1.0, confidence))
            except (ValueError, TypeError):
                confidence = 0.5

            reasoning = str(data.get("reasoning", "No reasoning provided"))
            return verdict, confidence, reasoning

        except json.JSONDecodeError:
            pass

    # Fallback: could not parse JSON
    log.warning("Could not parse Sophia's response as JSON: %.200s", text)
    return VERDICT_CAUTIOUS, 0.5, f"Unparseable response: {text[:200]}"

# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def _fetch_miner_data(miner_id: str, db_path: str = None) -> Tuple[dict, dict, list]:
    """
    Fetch device info, latest fingerprint snapshot, and history for a miner from the DB.
    Returns (device_dict, fingerprint_dict, history_list).
    """
    db_path = db_path or DB_PATH
    device = {}
    fingerprint = {}
    history = []

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            # Device info from miner_attest_recent
            row = conn.execute(
                "SELECT miner, device_family, device_arch, fingerprint_passed, ts_ok "
                "FROM miner_attest_recent WHERE miner = ?",
                (miner_id,)
            ).fetchone()
            if row:
                device = {
                    "device_family": row["device_family"],
                    "device_arch": row["device_arch"],
                    "fingerprint_passed": row["fingerprint_passed"],
                }

            # Latest fingerprint profile from history table (may not exist on all nodes)
            try:
                hist_rows = conn.execute(
                    "SELECT ts, profile_json FROM miner_fingerprint_history "
                    "WHERE miner = ? ORDER BY ts DESC LIMIT 10",
                    (miner_id,)
                ).fetchall()
            except Exception:
                hist_rows = []
            for hr in hist_rows:
                try:
                    profile = json.loads(hr["profile_json"] or "{}")
                    history.append({"ts": int(hr["ts"]), "profile": profile})
                except Exception:
                    continue

            # Use the most recent profile as "the fingerprint"
            if history:
                fingerprint = {"profile_summary": history[0]["profile"]}
                # Reverse so oldest is first for the prompt
                history = list(reversed(history))

    except Exception as exc:
        log.warning("Error fetching miner data for %s: %s", miner_id, exc)

    return device, fingerprint, history


def _compute_fingerprint_hash(fingerprint: dict) -> str:
    """Compute a stable hash of fingerprint data for deduplication."""
    canonical = json.dumps(fingerprint, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:32]

# ---------------------------------------------------------------------------
# Core inspection
# ---------------------------------------------------------------------------

def inspect_miner(miner_id: str, device: dict = None, fingerprint: dict = None,
                  db_path: str = None) -> Dict:
    """
    Main inspection function.

    If device/fingerprint not provided, fetch from the database.
    Build prompt, call Ollama, parse verdict, store result.
    Returns dict with verdict, confidence, reasoning, emoji, timestamp.
    """
    db_path = db_path or DB_PATH
    ensure_schema(db_path)

    # Fetch data if not provided
    history = []
    if device is None or fingerprint is None:
        fetched_device, fetched_fp, fetched_history = _fetch_miner_data(miner_id, db_path)
        device = device or fetched_device
        fingerprint = fingerprint or fetched_fp
        history = fetched_history

    if not device and not fingerprint:
        log.warning("No device or fingerprint data for miner %s", miner_id)
        return {
            "miner": miner_id,
            "verdict": VERDICT_CAUTIOUS,
            "confidence": 0.0,
            "reasoning": "No attestation data available for this miner",
            "emoji": VERDICT_EMOJI[VERDICT_CAUTIOUS],
            "model": MODEL,
            "timestamp": int(time.time()),
            "ollama_available": False,
        }

    fp_hash = _compute_fingerprint_hash(fingerprint)

    prompt = _build_inspection_prompt(miner_id, device, fingerprint, history)
    response_text = _call_ollama(prompt)

    if response_text is None:
        # Ollama unavailable -- return pending state, do not store
        return {
            "miner": miner_id,
            "verdict": VERDICT_CAUTIOUS,
            "confidence": 0.0,
            "reasoning": "SophiaCore unavailable -- inspection pending",
            "emoji": "\u23f3",  # hourglass
            "model": MODEL,
            "timestamp": int(time.time()),
            "ollama_available": False,
        }

    verdict, confidence, reasoning = _parse_verdict(response_text)
    used_model = MODEL

    # ESCALATION: If regular Sophia flags SUSPICIOUS, escalate to GPT-OSS 120B
    # on POWER8 for a deeper second opinion with the big model.
    if verdict == VERDICT_SUSPICIOUS and confidence < 0.6:
        deep_prompt = (
            f"You are a senior hardware forensics analyst reviewing an attestation flagged as SUSPICIOUS.\n\n"
            f"Miner: {miner_id}\n"
            f"Initial assessment: {reasoning}\n\n"
            f"Full fingerprint data:\n{json.dumps(fingerprint, indent=2, default=str)[:2000]}\n\n"
            f"Device: {json.dumps(device, default=str)}\n\n"
            f"Provide a detailed second opinion. Is this genuine hardware with quirks, "
            f"or actual spoofing? Look deeper at cross-correlations between all metrics.\n\n"
            f'Respond in JSON: {{"verdict": "APPROVED|CAUTIOUS|SUSPICIOUS|REJECTED", "confidence": 0.0-1.0, "reasoning": "detailed analysis"}}'
        )
        deep_response = _call_deep_model(deep_prompt)
        if deep_response:
            deep_verdict, deep_confidence, deep_reasoning = _parse_verdict(deep_response)
            log.info("Deep analysis (GPT-OSS 120B) for %s: %s %.0f%% — %s",
                     miner_id, deep_verdict, deep_confidence * 100, deep_reasoning[:80])
            # Deep model overrides if it's more confident
            if deep_confidence > confidence:
                verdict = deep_verdict
                confidence = deep_confidence
                reasoning = f"[Deep analysis] {deep_reasoning}"
                used_model = MODEL_DEEP

    now = int(time.time())

    # Store in DB
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO sophia_inspections "
                "(miner, inspection_ts, verdict, confidence, reasoning, model_version, fingerprint_hash) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (miner_id, now, verdict, confidence, reasoning, used_model, fp_hash)
            )
            conn.commit()
    except Exception as exc:
        log.error("Failed to store inspection result for %s: %s", miner_id, exc)

    result = {
        "miner": miner_id,
        "inspector": "Sophia Elya",
        "verdict": verdict,
        "confidence": confidence,
        "reasoning": reasoning,
        "emoji": VERDICT_EMOJI.get(verdict, "?"),
        "model": used_model,
        "fingerprint_hash": fp_hash,
        "timestamp": now,
        "ollama_available": True,
    }

    log.info("Inspected %s: %s %s (%.0f%%) -- %s",
             miner_id, VERDICT_EMOJI.get(verdict, "?"), verdict, confidence * 100, reasoning[:80])

    return result

# ---------------------------------------------------------------------------
# Batch inspection
# ---------------------------------------------------------------------------

def batch_inspect_all(db_path: str = None) -> List[Dict]:
    """
    Inspect ALL active miners (attested in last 24h).
    Returns list of inspection results.
    """
    db_path = db_path or DB_PATH
    ensure_schema(db_path)

    cutoff = int(time.time()) - 86400  # 24 hours
    miners = []

    try:
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                "SELECT miner FROM miner_attest_recent WHERE ts_ok > ? ORDER BY ts_ok DESC",
                (cutoff,)
            ).fetchall()
            miners = [r[0] for r in rows]
    except Exception as exc:
        log.error("Failed to query active miners: %s", exc)
        return []

    if not miners:
        log.info("No active miners found in last 24h")
        return []

    log.info("Batch inspecting %d active miners", len(miners))
    results = []

    for i, miner_id in enumerate(miners):
        log.info("[%d/%d] Inspecting %s", i + 1, len(miners), miner_id)
        try:
            result = inspect_miner(miner_id, db_path=db_path)
            results.append(result)
        except Exception as exc:
            log.error("Error inspecting %s: %s", miner_id, exc)
            results.append({
                "miner": miner_id,
                "verdict": VERDICT_CAUTIOUS,
                "confidence": 0.0,
                "reasoning": f"Inspection error: {exc}",
                "emoji": VERDICT_EMOJI[VERDICT_CAUTIOUS],
                "timestamp": int(time.time()),
                "ollama_available": False,
            })

        # Rate limit between inspections
        if i < len(miners) - 1:
            time.sleep(BATCH_DELAY)

    # Print summary
    summary = {}
    for r in results:
        v = r.get("verdict", "UNKNOWN")
        summary[v] = summary.get(v, 0) + 1

    log.info("Batch inspection complete: %d miners", len(results))
    for verdict, count in sorted(summary.items()):
        emoji = VERDICT_EMOJI.get(verdict, "?")
        log.info("  %s %s: %d", emoji, verdict, count)

    return results

# ---------------------------------------------------------------------------
# Query latest verdict
# ---------------------------------------------------------------------------

def get_latest_verdict(miner_id: str, db_path: str = None) -> Optional[Dict]:
    """
    Get the most recent Sophia inspection for a miner.
    Returns dict or None.
    """
    db_path = db_path or DB_PATH
    ensure_schema(db_path)

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT miner, inspection_ts, verdict, confidence, reasoning, model_version, fingerprint_hash "
                "FROM sophia_inspections WHERE miner = ? ORDER BY inspection_ts DESC LIMIT 1",
                (miner_id,)
            ).fetchone()
            if not row:
                return None
            return {
                "miner": row["miner"],
                "verdict": row["verdict"],
                "confidence": row["confidence"],
                "reasoning": row["reasoning"],
                "model": row["model_version"],
                "fingerprint_hash": row["fingerprint_hash"],
                "emoji": VERDICT_EMOJI.get(row["verdict"], "?"),
                "timestamp": row["inspection_ts"],
            }
    except Exception as exc:
        log.error("Error fetching verdict for %s: %s", miner_id, exc)
        return None


def get_all_latest_verdicts(db_path: str = None) -> List[Dict]:
    """Get the most recent verdict for every miner that has been inspected."""
    db_path = db_path or DB_PATH
    ensure_schema(db_path)

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT s.miner, s.inspection_ts, s.verdict, s.confidence,
                       s.reasoning, s.model_version, s.fingerprint_hash
                FROM sophia_inspections s
                INNER JOIN (
                    SELECT miner, MAX(inspection_ts) AS max_ts
                    FROM sophia_inspections GROUP BY miner
                ) latest ON s.miner = latest.miner AND s.inspection_ts = latest.max_ts
                ORDER BY s.miner
                """
            ).fetchall()
            return [
                {
                    "miner": r["miner"],
                    "verdict": r["verdict"],
                    "confidence": r["confidence"],
                    "reasoning": r["reasoning"],
                    "model": r["model_version"],
                    "fingerprint_hash": r["fingerprint_hash"],
                    "emoji": VERDICT_EMOJI.get(r["verdict"], "?"),
                    "timestamp": r["inspection_ts"],
                }
                for r in rows
            ]
    except Exception as exc:
        log.error("Error fetching all verdicts: %s", exc)
        return []

# ---------------------------------------------------------------------------
# Flask endpoint registration
# ---------------------------------------------------------------------------

def register_sophia_endpoints(app, db_path: str = None):
    """
    Register Flask endpoints on the app for Sophia attestation inspection.

    GET  /sophia/status/<miner_id>  -- latest verdict for one miner
    GET  /sophia/status             -- latest verdicts for ALL miners
    POST /sophia/inspect            -- trigger inspection (admin key required)
    POST /sophia/batch              -- batch inspection (admin key required)
    """
    from flask import request, jsonify

    db = db_path or DB_PATH

    def _is_admin(req):
        need = os.environ.get("RC_ADMIN_KEY", "")
        got = req.headers.get("X-Admin-Key", "") or req.headers.get("X-API-Key", "")
        return bool(need and got and hmac.compare_digest(need, got))

    @app.route("/sophia/status/<miner_id>", methods=["GET"])
    def sophia_status_miner(miner_id):
        result = get_latest_verdict(miner_id, db_path=db)
        if result is None:
            return jsonify({
                "miner": miner_id,
                "verdict": None,
                "message": "No inspection on record. Pending.",
                "emoji": "\u23f3",
            }), 404
        return jsonify(result)

    @app.route("/sophia/status", methods=["GET"])
    def sophia_status_all():
        verdicts = get_all_latest_verdicts(db_path=db)
        summary = {}
        for v in verdicts:
            vd = v.get("verdict", "UNKNOWN")
            summary[vd] = summary.get(vd, 0) + 1
        return jsonify({
            "miners": verdicts,
            "count": len(verdicts),
            "summary": summary,
        })

    @app.route("/sophia/inspect", methods=["POST"])
    def sophia_inspect():
        if not _is_admin(request):
            return jsonify({"error": "Unauthorized -- admin key required"}), 401
        data = request.get_json(force=True, silent=True) or {}
        miner_id = data.get("miner_id")
        if not miner_id:
            return jsonify({"error": "miner_id required"}), 400
        device = data.get("device")
        fingerprint = data.get("fingerprint")
        result = inspect_miner(miner_id, device=device, fingerprint=fingerprint, db_path=db)
        return jsonify(result)

    @app.route("/sophia/batch", methods=["POST"])
    def sophia_batch():
        if not _is_admin(request):
            return jsonify({"error": "Unauthorized -- admin key required"}), 401
        results = batch_inspect_all(db_path=db)
        summary = {}
        for r in results:
            vd = r.get("verdict", "UNKNOWN")
            summary[vd] = summary.get(vd, 0) + 1
        return jsonify({
            "inspected": len(results),
            "summary": summary,
            "results": results,
        })

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="RIP-306: SophiaCore Attestation Inspector",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python3 sophia_attestation_inspector.py --batch
  python3 sophia_attestation_inspector.py --miner dual-g4-125
  python3 sophia_attestation_inspector.py --status dual-g4-125
  python3 sophia_attestation_inspector.py --status-all
""",
    )
    parser.add_argument("--batch", action="store_true", help="Inspect all active miners (attested in last 24h)")
    parser.add_argument("--miner", type=str, help="Inspect a specific miner by ID")
    parser.add_argument("--status", type=str, help="Show latest verdict for a miner")
    parser.add_argument("--status-all", action="store_true", help="Show latest verdicts for all miners")
    parser.add_argument("--db", type=str, default=None, help=f"Database path (default: {DB_PATH})")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.verbose:
        log.setLevel(logging.DEBUG)

    db = args.db or DB_PATH

    if args.batch:
        results = batch_inspect_all(db_path=db)
        if not results:
            print("No active miners to inspect.")
        sys.exit(0)

    elif args.miner:
        result = inspect_miner(args.miner, db_path=db)
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0)

    elif args.status:
        result = get_latest_verdict(args.status, db_path=db)
        if result is None:
            print(f"No inspection on record for {args.status}")
            sys.exit(1)
        print(json.dumps(result, indent=2, default=str))
        sys.exit(0)

    elif args.status_all:
        verdicts = get_all_latest_verdicts(db_path=db)
        if not verdicts:
            print("No inspections on record.")
            sys.exit(0)
        for v in verdicts:
            print(f"  {v['emoji']} {v['miner']}: {v['verdict']} ({v['confidence']:.0%}) -- {v.get('reasoning', '')[:60]}")
        sys.exit(0)

    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
