#!/usr/bin/env python3
"""Temporal entropy profile validation for RustChain attestations.

This module tracks per-miner fingerprint snapshots and flags profiles that are:
- frozen (variance ~ 0 across multiple attestations)
- noisy (variance too high, likely random spoofing)
- out-of-band drift (jumps outside expected ranges)
"""

from __future__ import annotations

import json
import math
import statistics
from typing import Dict, List, Optional

HISTORY_LIMIT = 10
MIN_SERIES = 3

# Expected absolute drift bands per metric between current sample and historical mean.
DRIFT_BANDS = {
    "clock_cv": 0.03,
    "entropy_score": 0.25,
    "thermal_score": 0.35,
}


def init_temporal_tables(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS miner_fingerprint_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            miner TEXT NOT NULL,
            ts_ok INTEGER NOT NULL,
            epoch INTEGER NOT NULL,
            clock_cv REAL DEFAULT 0.0,
            entropy_score REAL DEFAULT 0.0,
            thermal_score REAL DEFAULT 0.0,
            simd_identity TEXT DEFAULT '',
            source_ip TEXT,
            snapshot_json TEXT,
            UNIQUE(miner, ts_ok)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_miner_fingerprint_history_miner_ts
        ON miner_fingerprint_history(miner, ts_ok DESC)
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS miner_temporal_flags (
            miner TEXT PRIMARY KEY,
            last_ts INTEGER NOT NULL,
            consistency_score REAL NOT NULL,
            status TEXT NOT NULL,
            review_required INTEGER NOT NULL,
            reasons_json TEXT NOT NULL
        )
        """
    )


def _safe_float(v, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def build_temporal_snapshot(device: Dict, fingerprint: Dict, signals: Dict) -> Dict:
    """Build comparable metrics from attestation payload.

    We intentionally keep this schema compact so it can be used in SQL and tests.
    """
    checks = (fingerprint or {}).get("checks", {}) if isinstance(fingerprint, dict) else {}

    def check_data(name: str) -> Dict:
        raw = checks.get(name, {})
        if isinstance(raw, dict):
            return raw.get("data", {}) if isinstance(raw.get("data", {}), dict) else {}
        return {}

    clock = check_data("clock_drift")
    thermal = check_data("thermal_variance")
    simd = check_data("simd_identity")

    simd_identity = ""
    if isinstance(simd.get("profile_hash"), str):
        simd_identity = simd.get("profile_hash", "")
    elif isinstance(simd.get("cpu_flags_hash"), str):
        simd_identity = simd.get("cpu_flags_hash", "")

    if not simd_identity:
        simd_identity = str(device.get("device_arch", device.get("arch", "unknown")))

    snapshot = {
        "clock_cv": _safe_float(clock.get("cv", 0.0)),
        "entropy_score": _safe_float((signals or {}).get("entropy_score", 0.0)),
        "thermal_score": _safe_float(thermal.get("variance", 0.0)),
        "simd_identity": simd_identity[:128],
    }
    return snapshot


def _series_stats(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"mean": 0.0, "var": 0.0, "stdev": 0.0}
    mean = statistics.fmean(values)
    var = statistics.pvariance(values) if len(values) > 1 else 0.0
    stdev = math.sqrt(var)
    return {"mean": mean, "var": var, "stdev": stdev}


def _is_frozen(clock_vals: List[float], entropy_vals: List[float], thermal_vals: List[float]) -> bool:
    if min(len(clock_vals), len(entropy_vals), len(thermal_vals)) < MIN_SERIES:
        return False
    clock_var = statistics.pvariance(clock_vals)
    entropy_var = statistics.pvariance(entropy_vals)
    thermal_var = statistics.pvariance(thermal_vals)
    return clock_var <= 1e-10 and entropy_var <= 1e-8 and thermal_var <= 1e-8


def _is_noisy(clock_vals: List[float], entropy_vals: List[float], thermal_vals: List[float]) -> bool:
    if min(len(clock_vals), len(entropy_vals), len(thermal_vals)) < MIN_SERIES:
        return False

    def cv(vals: List[float]) -> float:
        if len(vals) < 2:
            return 0.0
        mean = abs(statistics.fmean(vals))
        if mean < 1e-9:
            return statistics.pstdev(vals)
        return statistics.pstdev(vals) / mean

    return cv(clock_vals) > 0.8 or cv(entropy_vals) > 0.6 or cv(thermal_vals) > 1.0


def validate_temporal_consistency(history_rows: List[Dict], current_snapshot: Dict) -> Dict:
    """Validate temporal consistency and return anomaly metadata."""
    rows = list(history_rows)
    if len(rows) < MIN_SERIES:
        return {
            "status": "insufficient_data",
            "consistency_score": 1.0,
            "review_required": False,
            "reasons": [],
        }

    clock_vals = [_safe_float(r.get("clock_cv", 0.0)) for r in rows]
    entropy_vals = [_safe_float(r.get("entropy_score", 0.0)) for r in rows]
    thermal_vals = [_safe_float(r.get("thermal_score", 0.0)) for r in rows]

    reasons: List[str] = []
    score = 1.0

    if _is_frozen(clock_vals, entropy_vals, thermal_vals):
        reasons.append("frozen_profile")
        score -= 0.55

    if _is_noisy(clock_vals, entropy_vals, thermal_vals):
        reasons.append("noisy_profile")
        score -= 0.45

    prev_rows = rows[:-1] if len(rows) > 1 else rows
    if prev_rows:
        prev_clock = _series_stats([_safe_float(r.get("clock_cv", 0.0)) for r in prev_rows])
        prev_entropy = _series_stats([_safe_float(r.get("entropy_score", 0.0)) for r in prev_rows])
        prev_thermal = _series_stats([_safe_float(r.get("thermal_score", 0.0)) for r in prev_rows])

        if abs(_safe_float(current_snapshot.get("clock_cv", 0.0)) - prev_clock["mean"]) > DRIFT_BANDS["clock_cv"]:
            reasons.append("clock_drift_out_of_band")
            score -= 0.2

        if abs(_safe_float(current_snapshot.get("entropy_score", 0.0)) - prev_entropy["mean"]) > DRIFT_BANDS["entropy_score"]:
            reasons.append("entropy_drift_out_of_band")
            score -= 0.2

        if abs(_safe_float(current_snapshot.get("thermal_score", 0.0)) - prev_thermal["mean"]) > DRIFT_BANDS["thermal_score"]:
            reasons.append("thermal_drift_out_of_band")
            score -= 0.2

    # SIMD identity should be stable. Rapid changes indicate suspicious spoofing.
    simd_values = [str(r.get("simd_identity", "")) for r in rows if str(r.get("simd_identity", ""))]
    if len(set(simd_values)) > 2:
        reasons.append("simd_identity_instability")
        score -= 0.25

    review_required = any(r in reasons for r in ("frozen_profile", "noisy_profile", "simd_identity_instability"))
    status = "ok" if not reasons else ("review" if review_required else "drift_warning")

    return {
        "status": status,
        "consistency_score": max(0.0, round(score, 4)),
        "review_required": review_required,
        "reasons": reasons,
    }


def record_and_validate_temporal(
    conn,
    miner: str,
    ts_ok: int,
    epoch: int,
    snapshot: Dict,
    source_ip: Optional[str] = None,
    history_limit: int = HISTORY_LIMIT,
) -> Dict:
    init_temporal_tables(conn)

    conn.execute(
        """
        INSERT OR REPLACE INTO miner_fingerprint_history
        (miner, ts_ok, epoch, clock_cv, entropy_score, thermal_score, simd_identity, source_ip, snapshot_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            miner,
            ts_ok,
            epoch,
            _safe_float(snapshot.get("clock_cv", 0.0)),
            _safe_float(snapshot.get("entropy_score", 0.0)),
            _safe_float(snapshot.get("thermal_score", 0.0)),
            str(snapshot.get("simd_identity", ""))[:128],
            source_ip,
            json.dumps(snapshot, separators=(",", ":")),
        ),
    )

    # Keep only last N snapshots per miner.
    conn.execute(
        """
        DELETE FROM miner_fingerprint_history
        WHERE miner = ? AND id NOT IN (
            SELECT id FROM miner_fingerprint_history
            WHERE miner = ? ORDER BY ts_ok DESC LIMIT ?
        )
        """,
        (miner, miner, history_limit),
    )

    rows = conn.execute(
        """
        SELECT clock_cv, entropy_score, thermal_score, simd_identity
        FROM miner_fingerprint_history
        WHERE miner = ?
        ORDER BY ts_ok ASC
        """,
        (miner,),
    ).fetchall()

    history_rows = [
        {
            "clock_cv": r[0],
            "entropy_score": r[1],
            "thermal_score": r[2],
            "simd_identity": r[3],
        }
        for r in rows
    ]

    result = validate_temporal_consistency(history_rows, snapshot)

    conn.execute(
        """
        INSERT INTO miner_temporal_flags(miner, last_ts, consistency_score, status, review_required, reasons_json)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(miner) DO UPDATE SET
            last_ts=excluded.last_ts,
            consistency_score=excluded.consistency_score,
            status=excluded.status,
            review_required=excluded.review_required,
            reasons_json=excluded.reasons_json
        """,
        (
            miner,
            ts_ok,
            float(result["consistency_score"]),
            result["status"],
            1 if result["review_required"] else 0,
            json.dumps(result["reasons"], separators=(",", ":")),
        ),
    )

    return result
