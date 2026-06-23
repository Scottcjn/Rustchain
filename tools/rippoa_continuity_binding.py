#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Reference contract for the RIP-PoA crystal continuity signal.

This helper intentionally models continuity, not identity. It can answer
"does this later measurement look like the enrolled box?", but it must not be
used as a per-unit fingerprint or replacement for assigned hardware IDs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Tuple


SCHEMA_VERSION = 1
RAW_TSC_PROBE = "rdtsc_raw"
DEFAULT_PPM_TOLERANCE = 0.30
MIN_BASELINE_MINUTES = 30.0
MIN_SAMPLE_COUNT = 120


@dataclass(frozen=True)
class ContinuityReading:
    """A temperature-corrected crystal-rate reading for one box."""

    arch: str
    probe: str
    ppm: float
    temperature_c: float
    duration_minutes: float
    samples: int
    source: str = ""


def _reading_from_mapping(data: Mapping[str, Any]) -> ContinuityReading:
    return ContinuityReading(
        arch=str(data.get("arch", "")).strip().lower(),
        probe=str(data.get("probe", "")).strip().lower(),
        ppm=float(data["ppm"]),
        temperature_c=float(data.get("temperature_c", 0.0)),
        duration_minutes=float(data.get("duration_minutes", 0.0)),
        samples=int(data.get("samples", 0)),
        source=str(data.get("source", "")).strip(),
    )


def canonical_reading(reading: ContinuityReading | Mapping[str, Any]) -> Dict[str, Any]:
    """Return the stable schema stored inside hardware_binding.continuity."""

    parsed = reading if isinstance(reading, ContinuityReading) else _reading_from_mapping(reading)
    return {
        "version": SCHEMA_VERSION,
        "arch": parsed.arch,
        "probe": parsed.probe,
        "ppm": round(parsed.ppm, 6),
        "temperature_c": round(parsed.temperature_c, 3),
        "duration_minutes": round(parsed.duration_minutes, 3),
        "samples": parsed.samples,
        "source": parsed.source,
    }


def continuity_commitment(reading: ContinuityReading | Mapping[str, Any]) -> str:
    """Hash a reading without claiming it is globally unique."""

    payload = json.dumps(canonical_reading(reading), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _valid_baseline(reading: ContinuityReading) -> Tuple[bool, str]:
    if reading.probe != RAW_TSC_PROBE:
        return False, "probe_not_raw_rdtsc"
    if reading.duration_minutes < MIN_BASELINE_MINUTES:
        return False, "baseline_too_short"
    if reading.samples < MIN_SAMPLE_COUNT:
        return False, "insufficient_samples"
    return True, "ok"


def evaluate_continuity(
    baseline: ContinuityReading | Mapping[str, Any],
    candidate: ContinuityReading | Mapping[str, Any],
    *,
    ppm_tolerance: float = DEFAULT_PPM_TOLERANCE,
) -> Dict[str, Any]:
    """Compare enrollment and later readings as a continuity check."""

    base = baseline if isinstance(baseline, ContinuityReading) else _reading_from_mapping(baseline)
    later = candidate if isinstance(candidate, ContinuityReading) else _reading_from_mapping(candidate)

    baseline_ok, baseline_reason = _valid_baseline(base)
    candidate_ok, candidate_reason = _valid_baseline(later)
    delta_ppm = abs(later.ppm - base.ppm)

    result = {
        "version": SCHEMA_VERSION,
        "same_box": False,
        "delta_ppm": round(delta_ppm, 6),
        "ppm_tolerance": ppm_tolerance,
        "identity_claim": False,
        "reason": "",
    }

    if not baseline_ok:
        result["reason"] = "invalid_baseline:" + baseline_reason
        return result
    if not candidate_ok:
        result["reason"] = "invalid_candidate:" + candidate_reason
        return result
    if base.arch != later.arch:
        result["reason"] = "arch_mismatch"
        return result
    if base.probe != later.probe:
        result["reason"] = "probe_mismatch"
        return result

    if delta_ppm <= ppm_tolerance:
        result["same_box"] = True
        result["reason"] = "within_tolerance"
    else:
        result["reason"] = "possible_hardware_swap"

    return result


def hardware_binding_continuity_evidence(
    wallet_or_miner_id: str,
    assigned_hardware_id: str,
    reading: ContinuityReading | Mapping[str, Any],
) -> Dict[str, Any]:
    """Build a hardware_binding extension that keeps assigned IDs authoritative."""

    canonical = canonical_reading(reading)
    return {
        "version": SCHEMA_VERSION,
        "wallet_or_miner_id": wallet_or_miner_id,
        "assigned_hardware_id": assigned_hardware_id,
        "identity_source": "assigned_hardware_id",
        "continuity": canonical,
        "continuity_commitment": continuity_commitment(canonical),
        "non_goals": [
            "per_unit_physical_identity",
            "same_model_box_discrimination",
        ],
    }
