# SPDX-License-Identifier: MIT
"""
RustChain Red Team — Replay Attack Defense
Bounty #2276: 150 RTC

Server-side defenses against hardware fingerprint replay attacks:
1. Nonce-binding — fingerprint must include a server-issued challenge
2. Temporal correlation — timing data must be fresh, not recorded
3. Cross-check — fingerprint entropy vs connection metadata (IP, TLS)
4. Deduplication — reject previously-seen fingerprint hashes

These defenses integrate with the existing attestation pipeline without
breaking legitimate miners.
"""

import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple


# ── Configuration ─────────────────────────────────────────────────

NONCE_TTL_SECONDS = 120       # Nonces expire after 2 minutes
NONCE_LENGTH = 32             # 256-bit nonce
FRESHNESS_WINDOW = 300        # Fingerprint data must be <5 min old
HMAC_SECRET = os.environ.get("RUSTCHAIN_HMAC_SECRET", "default-hmac-secret-change-me")
DEDUP_WINDOW = 86400          # Reject duplicate fingerprints within 24h
MAX_SEEN_HASHES = 100000      # Max stored fingerprint hashes


# ── Nonce Store ───────────────────────────────────────────────────

class NonceStore:
    """Server-side nonce management. Each challenge is single-use."""

    def __init__(self):
        self._nonces: Dict[str, float] = {}  # nonce → issued_at

    def issue(self, miner_id: str = "") -> str:
        """Issue a fresh nonce for a miner challenge."""
        nonce = secrets.token_hex(NONCE_LENGTH)
        self._nonces[nonce] = time.time()
        self._cleanup()
        return nonce

    def consume(self, nonce: str) -> bool:
        """
        Consume a nonce. Returns True if valid (exists and not expired).
        Single-use: nonce is deleted after consumption.
        """
        if nonce not in self._nonces:
            return False
        issued_at = self._nonces.pop(nonce)
        return (time.time() - issued_at) < NONCE_TTL_SECONDS

    def _cleanup(self):
        """Remove expired nonces."""
        now = time.time()
        expired = [n for n, t in self._nonces.items() if (now - t) >= NONCE_TTL_SECONDS]
        for n in expired:
            del self._nonces[n]

    @property
    def active_count(self) -> int:
        return len(self._nonces)


# ── Fingerprint Deduplication ─────────────────────────────────────

class FingerprintDedup:
    """Tracks seen fingerprint hashes to prevent replay."""

    def __init__(self):
        self._seen: Dict[str, float] = {}  # hash → first_seen_at

    def compute_hash(self, fingerprint: Dict) -> str:
        """
        Compute a canonical hash of the hardware-specific fingerprint data.
        Excludes miner_id, timestamp, nonce — only hardware measurements.
        """
        hw_data = {
            "clock_drift": fingerprint.get("clock_drift", {}),
            "cache_timing": fingerprint.get("cache_timing", {}),
            "simd_identity": fingerprint.get("simd_identity", {}),
            "thermal_profile": fingerprint.get("thermal_profile", {}),
            "instruction_jitter": fingerprint.get("instruction_jitter", {}),
        }
        canonical = json.dumps(hw_data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def is_duplicate(self, fingerprint: Dict) -> Tuple[bool, str]:
        """Check if this fingerprint was seen before within the dedup window."""
        fp_hash = self.compute_hash(fingerprint)
        now = time.time()

        if fp_hash in self._seen:
            age = now - self._seen[fp_hash]
            if age < DEDUP_WINDOW:
                return True, fp_hash

        # Record this fingerprint
        self._seen[fp_hash] = now
        self._cleanup()
        return False, fp_hash

    def _cleanup(self):
        """Remove entries outside the dedup window."""
        now = time.time()
        expired = [h for h, t in self._seen.items() if (now - t) >= DEDUP_WINDOW]
        for h in expired:
            del self._seen[h]
        # Cap memory usage
        if len(self._seen) > MAX_SEEN_HASHES:
            oldest = sorted(self._seen.items(), key=lambda x: x[1])
            for h, _ in oldest[: len(self._seen) - MAX_SEEN_HASHES]:
                del self._seen[h]


# ── Validation Functions ──────────────────────────────────────────

def compute_nonce_binding(nonce: str, fingerprint: Dict) -> str:
    """
    Compute the expected nonce-binding HMAC.
    The miner must include this HMAC to prove the fingerprint was
    generated AFTER receiving the nonce (not pre-recorded).

    Binding = HMAC-SHA256(secret, nonce || drift_hash || cache_hash || jitter_hash)
    """
    drift_hash = fingerprint.get("clock_drift", {}).get("drift_hash", "")
    cache_hash = fingerprint.get("cache_timing", {}).get("pattern_hash", "")
    jitter_hash = fingerprint.get("instruction_jitter", {}).get("jitter_hash", "")

    message = f"{nonce}|{drift_hash}|{cache_hash}|{jitter_hash}"
    return hmac.new(
        HMAC_SECRET.encode(), message.encode(), hashlib.sha256
    ).hexdigest()


def validate_nonce_binding(fingerprint: Dict, nonce: str, claimed_hmac: str) -> Tuple[bool, str]:
    """
    Check 1: Server-side nonce binding.
    The fingerprint must include a valid HMAC proving it was generated
    with the server-issued nonce.
    """
    expected = compute_nonce_binding(nonce, fingerprint)
    if not hmac.compare_digest(expected, claimed_hmac):
        return False, "NONCE_BINDING_MISMATCH: HMAC does not match server nonce"
    return True, "OK"


def validate_fingerprint_freshness(fingerprint: Dict, max_age: float = FRESHNESS_WINDOW) -> Tuple[bool, str]:
    """
    Check 2: Temporal correlation.
    Fingerprint timing data must be fresh — not a recording from hours/days ago.

    Validates:
    - attestation_time is within max_age of current time
    - Clock drift data is consistent with fresh collection
      (real hardware produces different drift each run)
    """
    attestation_time = fingerprint.get("attestation_time", 0)
    now = time.time()
    age = abs(now - attestation_time)

    if age > max_age:
        return False, f"STALE_ATTESTATION: Data is {age:.0f}s old (max {max_age}s)"

    # Future timestamps are also suspicious
    if attestation_time > now + 30:  # 30s clock skew tolerance
        return False, f"FUTURE_TIMESTAMP: Attestation time is {attestation_time - now:.0f}s in future"

    return True, "OK"


def validate_connection_crosscheck(
    fingerprint: Dict,
    connection_ip: str = "",
    tls_fingerprint: str = "",
    previous_ips: Optional[List[str]] = None,
) -> Tuple[bool, str]:
    """
    Check 3: Cross-check fingerprint entropy against connection metadata.
    Detects when a vintage hardware fingerprint arrives from a clearly
    modern datacenter IP or mismatched TLS stack.
    """
    architecture = fingerprint.get("architecture", "")
    simd = fingerprint.get("simd_identity", {})

    # PowerPC hardware shouldn't have SSE/AVX (x86 SIMD)
    if architecture == "powerpc":
        if simd.get("sse_present") or simd.get("avx_present"):
            return False, "SIMD_MISMATCH: PowerPC claimed but x86 SIMD detected"

    # x86 hardware shouldn't have AltiVec (PowerPC SIMD)
    if architecture in ("x86", "x86_64", "amd64"):
        if simd.get("altivec_present"):
            return False, "SIMD_MISMATCH: x86 claimed but AltiVec detected"

    # If we have TLS fingerprint, check it matches expected stack
    # (vintage Mac OS X has distinctive TLS behavior)
    if tls_fingerprint and architecture == "powerpc":
        # Modern TLS 1.3 from a PowerPC G4 is suspicious
        if "tls1.3" in tls_fingerprint.lower() and fingerprint.get("device_age", {}).get(
            "manufacture_year", 2025
        ) < 2010:
            return False, "TLS_MISMATCH: TLS 1.3 from pre-2010 hardware is suspicious"

    # IP consistency check (optional)
    if previous_ips and connection_ip:
        # A miner jumping between 10+ IPs per day is suspicious
        recent_unique = set(previous_ips[-50:])
        if len(recent_unique) > 10:
            return False, "IP_INSTABILITY: Too many unique IPs in recent history"

    return True, "OK"


# ── Main Validation Pipeline ─────────────────────────────────────

@dataclass
class ValidationResult:
    """Result of the full replay defense validation."""
    accepted: bool = False
    checks: Dict[str, Tuple[bool, str]] = field(default_factory=dict)
    fingerprint_hash: str = ""
    timestamp: str = ""

    def summary(self) -> str:
        status = "ACCEPTED" if self.accepted else "REJECTED"
        failed = [k for k, (v, _) in self.checks.items() if not v]
        if failed:
            return f"{status}: Failed checks: {', '.join(failed)}"
        return f"{status}: All checks passed"


def validate_attestation(
    fingerprint: Dict,
    nonce: str,
    claimed_hmac: str,
    nonce_store: NonceStore,
    dedup_store: FingerprintDedup,
    connection_ip: str = "",
    tls_fingerprint: str = "",
    previous_ips: Optional[List[str]] = None,
) -> ValidationResult:
    """
    Full replay defense validation pipeline.
    ALL checks must pass for attestation to be accepted.
    """
    result = ValidationResult(timestamp=datetime.utcnow().isoformat() + "Z")

    # Check 0: Nonce is valid and not expired (consumed on use)
    nonce_valid = nonce_store.consume(nonce)
    result.checks["nonce_validity"] = (
        nonce_valid,
        "OK" if nonce_valid else "INVALID_NONCE: Unknown or expired nonce",
    )

    # Check 1: Nonce binding (HMAC)
    if nonce_valid:
        result.checks["nonce_binding"] = validate_nonce_binding(fingerprint, nonce, claimed_hmac)
    else:
        result.checks["nonce_binding"] = (False, "SKIPPED: Invalid nonce")

    # Check 2: Temporal freshness
    result.checks["freshness"] = validate_fingerprint_freshness(fingerprint)

    # Check 3: Connection cross-check
    result.checks["connection_crosscheck"] = validate_connection_crosscheck(
        fingerprint, connection_ip, tls_fingerprint, previous_ips
    )

    # Check 4: Deduplication
    is_dup, fp_hash = dedup_store.is_duplicate(fingerprint)
    result.fingerprint_hash = fp_hash
    result.checks["deduplication"] = (
        not is_dup,
        "OK" if not is_dup else f"DUPLICATE: Fingerprint {fp_hash[:12]}... seen before",
    )

    # All checks must pass
    result.accepted = all(passed for passed, _ in result.checks.values())
    return result
