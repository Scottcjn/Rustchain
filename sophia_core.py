"""
sophia_core.py -- SophiaCore Attestation Inspector.
RIP-306: AI-powered validation layer using Sophia Elya (Ollama LLM)
to inspect hardware fingerprint attestations.

Rustchain bounty #2261 (150 RTC).
"""

import json
import logging
import requests
import time

from sophia_db import (
    get_connection, store_inspection, enqueue_review, get_latest_inspection,
    DB_PATH
)

logger = logging.getLogger("sophia_core")

MODEL = "elyan-sophia:7b-q4_K_M"
OLLAMA_MAX_ATTEMPTS = 3
OLLAMA_BACKOFF_BASE_SECONDS = 0.5

OLLAMA_FAILOVER_CHAIN = [
    "http://localhost:11434",
    "http://100.75.100.89:11434",
]

VERDICTS = {
    "APPROVED":   "\u2728",
    "CAUTIOUS":   "\u26a0\ufe0f",
    "SUSPICIOUS": "\U0001f50d",
    "REJECTED":   "\u274c",
}

PROMPT_TEMPLATE = """Analyze this hardware fingerprint attestation for mining integrity.

Fingerprint: {json_fingerprint}

Evaluate:
1. Correlation between claimed CPU and performance metrics
2. Anomalies (too perfect values, impossible combinations)
3. Signs of emulation or virtualization
4. Consistency with historical attestations

Respond EXACTLY:
VERDICT: [APPROVED|CAUTIOUS|SUSPICIOUS|REJECTED]
CONFIDENCE: [0.0-1.0]
REASONING: [explanation]"""


def _build_analysis_prompt(fingerprint):
    """Build the prompt for Sophia Elya using the RIP-306 template.
    Input is sanitized to prevent prompt injection.
    """
    # Sanitize fingerprint values to prevent prompt injection (newlines/delimiters)
    sanitized_fp = {}
    for k, v in fingerprint.items():
        if isinstance(v, str):
            sanitized_fp[k] = v.replace("\n", " ").replace("VERDICT:", "[V]")
        elif isinstance(v, dict):
            sanitized_fp[k] = {sk: (sv.replace("\n", " ") if isinstance(sv, str) else sv) for sk, sv in v.items()}
        else:
            sanitized_fp[k] = v

    return PROMPT_TEMPLATE.format(
        json_fingerprint=json.dumps(sanitized_fp, indent=2)
    )


def _parse_ollama_response(raw_text):
    """Parse the VERDICT/CONFIDENCE/REASONING response from Ollama."""
    verdict = None
    confidence = None
    reasoning = None

    for line in raw_text.strip().splitlines():
        line = line.strip()
        if line.upper().startswith("VERDICT:"):
            v = line.split(":", 1)[1].strip().upper()
            if v in VERDICTS:
                verdict = v
        elif line.upper().startswith("CONFIDENCE:"):
            try:
                c = float(line.split(":", 1)[1].strip())
                if 0.0 <= c <= 1.0:
                    confidence = c
            except ValueError:
                pass
        elif line.upper().startswith("REASONING:"):
            reasoning = line.split(":", 1)[1].strip()

    if not verdict or confidence is None or not reasoning:
        raise ValueError(
            f"Incomplete Ollama response — verdict={verdict}, "
            f"confidence={confidence}, reasoning={reasoning}"
        )

    return {
        "verdict": verdict,
        "confidence": confidence,
        "reasoning": reasoning,
    }


def _query_ollama(prompt, endpoint, max_attempts=OLLAMA_MAX_ATTEMPTS,
                  backoff_base=OLLAMA_BACKOFF_BASE_SECONDS):
    """Send a generate request to an Ollama endpoint. Returns parsed dict."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    url = f"{endpoint}/api/generate"
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 512},
    }

    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            body = resp.json()
            raw = body.get("response", "")

            return _parse_ollama_response(raw)
        except Exception as exc:
            last_exc = exc
            if attempt >= max_attempts:
                break

            delay = backoff_base * (2 ** (attempt - 1))
            logger.warning(
                "Ollama endpoint %s attempt %d/%d failed: %s; retrying in %.1fs",
                endpoint, attempt, max_attempts, exc, delay
            )
            time.sleep(delay)

    raise last_exc


def _rule_based_fallback(fingerprint):
    """Deterministic rule-based analysis when Ollama is unavailable.
    Uses tightened thresholds and anomaly detection to prevent trivial bypass.
    """
    score = 0
    reasons = []
    
    # 1. Clock drift CV - tighten thresholds
    cv = fingerprint.get("clock_drift_cv")
    if cv is not None:
        if cv < 0.0005: # Lowered from 0.001
            score -= 4
            reasons.append("Clock drift CV suspiciously low (emulator detected)")
        elif 0.001 < cv < 0.008:
            score += 1
            reasons.append("Clock drift CV within tight normal range")
        elif cv > 0.15:
            score -= 2
            reasons.append("Clock drift CV abnormally high")
        else:
            score += 0
            reasons.append("Clock drift CV acceptable")

    # 2. Cache hierarchy - check for 'too perfect' values
    cache = fingerprint.get("cache_hierarchy", {})
    l1, l2, l3 = cache.get("l1_latency_ns"), cache.get("l2_latency_ns"), cache.get("l3_latency_ns")
    if l1 is not None and l2 is not None and l3 is not None:
        if not (l1 < l2 < l3):
            score -= 5
            reasons.append("Cache hierarchy ordering violation")
        elif l1 == 10 and l2 == 20 and l3 == 30: # Block common 'placeholder' values
            score -= 5
            reasons.append("Generic placeholder cache latencies detected")
        else:
            score += 1
            reasons.append("Cache hierarchy valid")
        
        if l1 == l2 or l2 == l3:
            score -= 4
            reasons.append("Uniform cache latencies indicate emulation")

    # 3. SIMD - verify a minimum set of extensions
    simd = fingerprint.get("simd_identity", {})
    if simd:
        supported = [k for k, v in simd.items() if v]
        if len(supported) < 2: # Require at least 2 extensions for approval
            score -= 1
            reasons.append("Insufficient SIMD extensions reported")
        else:
            score += 1
            reasons.append(f"SIMD extensions verified: {', '.join(supported)}")
    else:
        score -= 2
        reasons.append("No SIMD data provided")

    # 4. Thermal profile - check for static temperatures
    thermal = fingerprint.get("thermal", {})
    temp = thermal.get("cpu_temp_c")
    if temp is not None:
        if temp < 10 or temp > 110:
            score -= 3
            reasons.append("Impossible CPU temperature")
        elif 30 <= temp <= 75:
            score += 1
            reasons.append("CPU temperature normal")
        else:
            score += 0
            reasons.append("CPU temperature marginal")

    # 5. Stability - reject perfect scores
    stability = fingerprint.get("stability_score")
    if stability is not None:
        if stability > 0.999: # Tighter than 0.99
            score -= 3
            reasons.append("Stability score too perfect (synthetic)")
        elif stability > 0.85:
            score += 1
            reasons.append("Stability healthy")
        elif stability < 0.4:
            score -= 2
            reasons.append("Stability critically low")

    # Map score to verdict (Tightened thresholds)
    if score >= 4:
        verdict = "APPROVED"
        confidence = min(0.8, 0.5 + score * 0.05)
    elif score >= 2:
        verdict = "CAUTIOUS"
        confidence = 0.4 + score * 0.05
    elif score >= -1:
        verdict = "SUSPICIOUS"
        confidence = 0.3 + abs(score) * 0.05
    else:
        verdict = "REJECTED"
        confidence = min(0.9, 0.5 + abs(score) * 0.05)

    return {
        "verdict": verdict,
        "confidence": round(confidence, 4),
        "reasoning": "; ".join(reasons) if reasons else "Insufficient data",
    }


class SophiaCoreInspector:
    """Main attestation inspector -- queries Sophia Elya via Ollama
    with rule-based fallback."""

    def __init__(self, db_path=None, ollama_endpoints=None):
        self.db_path = db_path or DB_PATH
        self.ollama_endpoints = list(OLLAMA_FAILOVER_CHAIN) if ollama_endpoints is None else ollama_endpoints
        self._last_model_used = None

    def inspect(self, miner_id, fingerprint, inspection_type="on-demand"):
        """Inspect a fingerprint bundle. Returns the inspection result dict."""
        prompt = _build_analysis_prompt(fingerprint)

        result = None
        model_used = None

        # Try Ollama failover chain
        for endpoint in self.ollama_endpoints:
            try:
                result = _query_ollama(prompt, endpoint)
                model_used = f"{MODEL}@{endpoint}"
                logger.info("Ollama responded from %s", endpoint)
                break
            except Exception as exc:
                logger.warning("Ollama endpoint %s failed: %s", endpoint, exc)
                continue

        # Fall back to rule-based analysis
        if result is None:
            result = _rule_based_fallback(fingerprint)
            model_used = "rule-based-fallback-v1"
            logger.info("Using rule-based fallback for miner %s", miner_id)

        self._last_model_used = model_used

        # Store in DB
        conn = get_connection(self.db_path)
        try:
            inspection_id = store_inspection(
                conn, miner_id,
                result["verdict"], result["confidence"],
                result["reasoning"], model_used,
                fingerprint, inspection_type=inspection_type
            )
            result["inspection_id"] = inspection_id
            result["miner_id"] = miner_id
            result["model_used"] = model_used
            result["emoji"] = VERDICTS.get(result["verdict"], "?")

            # Auto-queue CAUTIOUS and SUSPICIOUS for human review
            if result["verdict"] in ("CAUTIOUS", "SUSPICIOUS"):
                enqueue_review(conn, inspection_id, miner_id,
                               verdict=result["verdict"])
                result["queued_for_review"] = True
        finally:
            conn.close()

        return result

    def get_status(self, miner_id):
        """Get the latest inspection and history for a miner."""
        conn = get_connection(self.db_path)
        try:
            row = get_latest_inspection(conn, miner_id)
            if row:
                row["emoji"] = VERDICTS.get(row["verdict"], "?")
            return row
        finally:
            conn.close()
