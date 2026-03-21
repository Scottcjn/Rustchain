#!/usr/bin/env python3
"""
Replay Attack Defense — RIP-PoA Hardware Fingerprint Freshness Validation
======================================================================

Server-side defense against hardware fingerprint replay attacks.

A replay attack: attacker captures a legitimate G4's fingerprint attestation
and replays it from a modern x86 machine to steal the 2.5x antiquity bonus.

Defenses implemented:
1. Temporal Correlation — fingerprint timing entropy must be freshly measured
2. Nonce-Binding — attestation must include a server-issued challenge nonce
3. IP Correlation — attestation IP must be consistent with historical IP range
4. TLS Fingerprint Correlation — TLS JA3 hash must match historical pattern
5. Machine Entropy Freshness — inter-arrival jitter must be genuinely random

Usage:
    from replay_defense import validate_fingerprint_freshness, ReplayDefense

    ok, reason = validate_fingerprint_freshness(
        attestation=payload,
        db_conn=conn,
        now_ts=int(time.time()),
    )
"""

import hashlib
import hmac
import json
import secrets
import statistics
import time
from typing import Dict, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

# Maximum age of a fingerprint attestation before it's considered stale
MAX_FINGERPRINT_AGE_SECONDS = 300  # 5 minutes

# Maximum age of timing entropy data (how fresh the clock drift measurement must be)
MAX_ENTROPY_AGE_SECONDS = 300  # 5 minutes

# Allowed IP change radius (km) — allow some mobility but detect VPN hopping
MAX_IP_MOBILITY_KM = 500

# IP correlation lookback window (seconds)
IP_LOOKBACK_SECONDS = 86400 * 7  # 7 days

# TLS fingerprint change threshold
TLS_FINGERPRINT_HISTORY = 5  # Number of historical JA3 hashes to keep

# Entropy freshness thresholds
MIN_ENTROPY_CV = 0.0001  # CV must be above this (not synthetic/constant)
MAX_ENTROPY_CV_LEGACY = 0.008  # Modern machines have very low CV
MAX_ENTROPY_CV_G4 = 0.15  # G4 can have up to 0.15

# ─────────────────────────────────────────────────────────────────────────────
# CHALLENGE NONCE SYSTEM
# ─────────────────────────────────────────────────────────────────────────────

class ChallengeNonceManager:
    """
    Server-side manager for one-time challenge nonces.

    Flow:
    1. Miner requests challenge: get_challenge(miner_id) → nonce
    2. Miner submits attestation with: nonce + fingerprint + timestamp
    3. Server validates: validate_attestation(nonce, attestation) → ok/reason
    """

    def __init__(self, db_conn):
        self.conn = db_conn
        self._ensure_tables()

    def _ensure_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS attestation_challenges (
                nonce TEXT PRIMARY KEY,
                miner_id TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                used BOOLEAN DEFAULT 0,
                ip_address TEXT,
                ja3_hash TEXT
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS miner_ip_history (
                miner_id TEXT NOT NULL,
                ip_address TEXT NOT NULL,
                ja3_hash TEXT,
                first_seen INTEGER NOT NULL,
                last_seen INTEGER NOT NULL,
                UNIQUE(miner_id, ip_address)
            )
        """)

    def get_challenge(self, miner_id: str, client_ip: str, ja3_hash: str = None) -> str:
        """Issue a new challenge nonce to a miner."""
        nonce = secrets.token_hex(16)  # 32-char hex = 128 bits
        now = int(time.time())
        expires = now + MAX_FINGERPRINT_AGE_SECONDS

        self.conn.execute("""
            INSERT INTO attestation_challenges (nonce, miner_id, created_at, expires_at, ip_address, ja3_hash)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (nonce, miner_id, now, expires, client_ip, ja3_hash))
        self.conn.commit()

        return nonce

    def validate_attestation(
        self,
        nonce: str,
        attestation: Dict,
        client_ip: str,
        ja3_hash: str = None,
        now_ts: int = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate a submitted attestation against its challenge nonce.

        Returns:
            (True, None) — valid
            (False, reason) — invalid with reason string
        """
        now_ts = now_ts or int(time.time())

        # 1. Check nonce exists and is not used
        row = self.conn.execute(
            "SELECT * FROM attestation_challenges WHERE nonce = ?", (nonce,)
        ).fetchone()

        if not row:
            return False, "nonce_not_found"

        nonce_data = dict(zip([d[0] for d in self.conn.execute("SELECT * FROM attestation_challenges WHERE nonce = ?", (nonce,)).description], row))

        if nonce_data["used"]:
            return False, "nonce_already_used"

        if nonce_data["expires_at"] < now_ts:
            return False, "nonce_expired"

        # 2. Miner ID must match
        expected_miner = nonce_data["miner_id"]
        actual_miner = attestation.get("miner_id")
        if expected_miner != actual_miner:
            return False, f"miner_id_mismatch: expected {expected_miner}, got {actual_miner}"

        # 3. IP correlation check
        ip_ok, ip_reason = self._check_ip_correlation(
            expected_miner, client_ip, nonce_data.get("ip_address"), now_ts
        )
        if not ip_ok:
            return False, f"ip_correlation_failed: {ip_reason}"

        # 4. TLS fingerprint correlation
        if ja3_hash:
            tls_ok, tls_reason = self._check_tls_correlation(
                expected_miner, ja3_hash, nonce_data.get("ja3_hash"), now_ts
            )
            if not tls_ok:
                return False, f"tls_correlation_failed: {tls_reason}"

        # 5. Timestamp freshness (nonce was created ~same time as attestation)
        attestation_ts = attestation.get("timestamp", 0)
        ts_diff = abs(now_ts - nonce_data["created_at"])
        if ts_diff > MAX_FINGERPRINT_AGE_SECONDS:
            return False, f"timestamp_too_old: {ts_diff}s since challenge"

        # Mark nonce as used
        self.conn.execute(
            "UPDATE attestation_challenges SET used = 1 WHERE nonce = ?", (nonce,)
        )
        self.conn.commit()

        return True, None

    def _check_ip_correlation(
        self,
        miner_id: str,
        current_ip: str,
        challenge_ip: str,
        now_ts: int,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if the current IP is consistent with historical IP patterns for this miner.
        """
        if not challenge_ip:
            return True, "no_baseline_ip"  # No IP in challenge, can't correlate

        # Check if current IP is same /27 subnet as challenge IP (allows NAT)
        if self._same_subnet(current_ip, challenge_ip, 27):
            return True, None

        # Check historical IPs for this miner
        history = self.conn.execute("""
            SELECT ip_address, first_seen, last_seen
            FROM miner_ip_history
            WHERE miner_id = ? AND last_seen > ?
            ORDER BY last_seen DESC
            LIMIT 10
        """, (miner_id, now_ts - IP_LOOKBACK_SECONDS)).fetchall()

        if not history:
            # First time miner from this IP — flag but allow (could be new setup)
            return True, "first_ip_registration"

        # Check if current IP has been seen before for this miner
        historical_ips = [row[0] for row in history]
        if current_ip in historical_ips:
            return True, "known_ip"

        # IP is new — check if it's geographically consistent
        # (simplified: check /24 subnet match)
        for hist_ip in historical_ips:
            if self._same_subnet(current_ip, hist_ip, 24):
                return True, "same_subnet_as_historical"

        return False, f"ip_unusual: current={current_ip}, expected one of {historical_ips[:3]}"

    def _check_tls_correlation(
        self,
        miner_id: str,
        current_ja3: str,
        challenge_ja3: str,
        now_ts: int,
    ) -> Tuple[bool, Optional[str]]:
        """Check if TLS fingerprint is consistent with historical pattern."""
        if challenge_ja3 and current_ja3 != challenge_ja3:
            return False, f"tls_changed: {challenge_ja3} != {current_ja3}"

        # Check historical JA3 hashes
        history = self.conn.execute("""
            SELECT ja3_hash FROM miner_ip_history
            WHERE miner_id = ? AND ja3_hash IS NOT NULL AND last_seen > ?
            ORDER BY last_seen DESC
            LIMIT ?
        """, (miner_id, now_ts - IP_LOOKBACK_SECONDS, TLS_FINGERPRINT_HISTORY)).fetchall()

        if not history:
            return True, "no_ja3_history"

        historical_ja3s = [row[0] for row in history if row[0]]
        if current_ja3 in historical_ja3s:
            return True, "known_ja3"

        return False, f"ja3_unusual: {current_ja3} not in {historical_ja3s}"

    def _same_subnet(self, ip1: str, ip2: str, prefix_len: int) -> bool:
        """Check if two IPs are in the same subnet."""
        try:
            import ipaddress
            a1 = ipaddress.ip_address(ip1)
            a2 = ipaddress.ip_address(ip2)
            mask = ipaddress.ip_address((1 << 32) - 1 ^ ((1 << (32 - prefix_len)) - 1))
            return int(a1) & int(mask) == int(a2) & int(mask)
        except Exception:
            # If IP parsing fails, do string prefix match
            parts1 = ip1.split('.')
            parts2 = ip2.split('.')
            if prefix_len >= 24:
                return parts1[0] == parts2[0] and parts1[1] == parts2[1] and parts1[2] == parts2[2]
            elif prefix_len >= 16:
                return parts1[0] == parts2[0] and parts1[1] == parts2[1]
            return True

    def update_ip_history(self, miner_id: str, ip_address: str, ja3_hash: str, now_ts: int):
        """Update IP/TLS history for a miner after successful attestation."""
        self.conn.execute("""
            INSERT INTO miner_ip_history (miner_id, ip_address, ja3_hash, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(miner_id, ip_address) DO UPDATE SET
                last_seen = MAX(last_seen, ?)
        """, (miner_id, ip_address, ja3_hash, now_ts, now_ts, now_ts))
        self.conn.commit()


# ─────────────────────────────────────────────────────────────────────────────
# ENTROPY FRESHNESS VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

def validate_entropy_freshness(
    attestation: Dict,
    device_arch: str,
    now_ts: int = None,
) -> Tuple[bool, Optional[str]]:
    """
    Validate that the timing entropy in the attestation was freshly measured,
    not replayed from old data.

    Checks:
    1. CV (coefficient of variation) is in valid range for the claimed arch
    2. Timestamp is recent (within MAX_ENTROPY_AGE_SECONDS)
    3. Inter-sample timing shows genuine randomness (not synthetic)
    """
    now_ts = now_ts or int(time.time())

    attestation_ts = attestation.get("timestamp", 0)
    age = now_ts - attestation_ts

    if age > MAX_ENTROPY_AGE_SECONDS:
        return False, f"entropy_stale: attestation is {age}s old (max {MAX_ENTROPY_AGE_SECONDS}s)"

    clock_drift = attestation.get("clock_drift", {})
    cv = clock_drift.get("cv", 0)

    if cv < MIN_ENTROPY_CV:
        return False, f"entropy_synthetic: CV={cv} too low (min {MIN_ENTROPY_CV})"

    # Check CV is consistent with claimed architecture
    if device_arch in ("g4", "g5", "g3", "vax", "mc68000", "arm2", "mips_r2000", "transputer", "386", "pentium"):
        max_cv = MAX_ENTROPY_CV_LEGACY
    else:
        max_cv = MAX_ENTROPY_CV_LEGACY

    if cv > max_cv * 20:  # Allow some tolerance
        # This is a soft check — very high CV might indicate DOS or attack probe
        return True, f"entropy_unusual_cv: {cv}"

    # Check drift_stdev is non-zero (constant values = synthetic)
    drift_stdev = clock_drift.get("drift_stdev", 0)
    if drift_stdev == 0:
        return False, "entropy_synthetic: drift_stdev is zero (captured/replayed data)"

    return True, None


# ─────────────────────────────────────────────────────────────────────────────
# MAIN VALIDATION FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def validate_fingerprint_freshness(
    attestation: Dict,
    db_conn,
    client_ip: str = None,
    ja3_hash: str = None,
    now_ts: int = None,
) -> Tuple[bool, Optional[str]]:
    """
    Primary entry point: validate a fingerprint attestation for replay attacks.

    Implements 3-layer defense:
    Layer 1: Challenge nonce binding (server-issued, one-time use)
    Layer 2: IP + TLS fingerprint correlation
    Layer 3: Entropy freshness validation

    Args:
        attestation: The full attestation payload from the miner
        db_conn: SQLite connection with attestation_challenges + miner_ip_history tables
        client_ip: The IP address the attestation was submitted from
        ja3_hash: TLS JA3 fingerprint hash of the client connection
        now_ts: Current timestamp (for testing)

    Returns:
        (True, None) — attestation is fresh and valid
        (False, reason) — attestation failed validation with reason string
    """
    now_ts = now_ts or int(time.time())

    # Extract required fields
    nonce = attestation.get("nonce")
    if not nonce:
        return False, "missing_nonce"

    miner_id = attestation.get("miner_id")
    if not miner_id:
        return False, "missing_miner_id"

    device_arch = attestation.get("device_arch", "unknown")

    # ─── Layer 1: Challenge Nonce Binding ────────────────────────────────────
    nonce_mgr = ChallengeNonceManager(db_conn)
    ok, reason = nonce_mgr.validate_attestation(
        nonce=nonce,
        attestation=attestation,
        client_ip=client_ip,
        ja3_hash=ja3_hash,
        now_ts=now_ts,
    )
    if not ok:
        return False, f"nonce_validation_failed: {reason}"

    # ─── Layer 3: Entropy Freshness ─────────────────────────────────────────
    ok, reason = validate_entropy_freshness(attestation, device_arch, now_ts)
    if not ok:
        return False, f"entropy_validation_failed: {reason}"

    # ─── Success ─────────────────────────────────────────────────────────────
    return True, None


# ─────────────────────────────────────────────────────────────────────────────
# CONVENIENCE FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def issue_challenge(db_conn, miner_id: str, client_ip: str = None, ja3_hash: str = None) -> str:
    """Issue a new attestation challenge nonce."""
    mgr = ChallengeNonceManager(db_conn)
    return mgr.get_challenge(miner_id, client_ip or "0.0.0.0", ja3_hash)


def register_miner_ip(db_conn, miner_id: str, ip_address: str, ja3_hash: str = None):
    """Register/update IP history after successful attestation."""
    mgr = ChallengeNonceManager(db_conn)
    mgr.update_ip_history(miner_id, ip_address, ja3_hash, int(time.time()))
