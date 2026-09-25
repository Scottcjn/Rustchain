#!/usr/bin/env python3
"""
RustChain Issue #1449: Anti-Double-Mining Enforcement
======================================================

Enforces the rule that one physical machine earns at most one reward per epoch,
regardless of how many miner IDs are run on that machine.

Key Components:
1. Machine Identity Keying: Uses hardware fingerprint + device_arch as unique machine identity
2. Ledger-Side Guardrails: Reward assignment groups by machine identity, not miner_id
3. Telemetry/Alerts: Logs and metrics when duplicate-identity miners are detected
4. False Positive Prevention: Legitimate distinct machines are unaffected

Implementation Strategy:
- At epoch settlement time, group miners by machine_identity (device_arch + fingerprint_hash)
- Select one representative miner_id per machine identity (highest attestation score)
- Distribute one reward per machine identity, not per miner_id
- Log all duplicate detections for monitoring
"""

import sqlite3
import time
import hashlib
import json
import logging
import math
import os
import tempfile
from contextlib import closing
# SYBIL-GUARD: the preferred settlement path (settle_epoch_rip200 -> ADM) must
# apply the review hold. Hard import: never silently settle held miners.
try:
    import sybil_guard
except ImportError:
    from node import sybil_guard
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

# Canonical genesis timestamp — must match rip_200_round_robin_1cpu1vote.py
GENESIS_TIMESTAMP = 1764706927  # Production chain launch (Dec 2, 2025)
BLOCK_TIME = 600

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [ANTI-DOUBLE-MINING] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# MACHINE IDENTITY
# =============================================================================

def compute_machine_identity_hash(device_arch: str, fingerprint_profile: Dict[str, Any]) -> str:
    """
    Compute a unique hash for a machine's identity.
    
    This combines:
    - device_arch: CPU architecture family (e.g., "g4", "g5", "modern")
    - fingerprint_profile: Hardware fingerprint data from attestation
    
    The hash ensures that:
    - Same physical machine = same identity (even with different miner_ids)
    - Different physical machines = different identities
    """
    # Create canonical representation of fingerprint
    # Sort keys for deterministic serialization
    canonical_profile = {
        "arch": device_arch,
        "fingerprint": normalize_fingerprint(fingerprint_profile)
    }
    
    # Hash the canonical representation
    profile_json = json.dumps(canonical_profile, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(profile_json.encode()).hexdigest()[:16]


def normalize_fingerprint(fingerprint_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Normalize fingerprint data for consistent hashing.
    
    Extracts stable hardware characteristics that identify a physical machine:
    - CPU serial (if available)
    - Hardware signatures from fingerprint checks
    - Stable device characteristics
    
    Returns a normalized dict suitable for JSON serialization.
    """
    if not fingerprint_data:
        return {}
    
    normalized = {}
    checks = fingerprint_data.get("checks", {})
    
    # Extract stable identifiers from various fingerprint checks
    if isinstance(checks, dict):
        # Clock drift characteristics (hardware-specific)
        if "clock_drift" in checks:
            data = checks["clock_drift"].get("data", {})
            normalized["clock_cv"] = round(data.get("cv", 0), 6)
            normalized["clock_mean"] = round(data.get("mean_ns", 0), 2)
        
        # Thermal characteristics (hardware-specific)
        if "thermal_entropy" in checks or "thermal_drift" in checks:
            data = checks.get("thermal_entropy", checks.get("thermal_drift", {})).get("data", {})
            normalized["thermal_var"] = round(data.get("variance", 0), 4)
        
        # Cache timing (hardware-specific)
        if "cache_timing" in checks:
            data = checks["cache_timing"].get("data", {})
            normalized["cache_ratio"] = round(data.get("hierarchy_ratio", 0), 4)
        
        # CPU serial (most reliable if available)
        if "cpu_serial" in checks:
            data = checks["cpu_serial"].get("data", {})
            serial = data.get("serial", "")
            if serial:
                normalized["cpu_serial"] = serial
    
    return normalized


# =============================================================================
# ADM IDENTITY FIX (2026-09-25, round 2 after review)
# =============================================================================
# compute_machine_identity_hash(arch, profile) reads profile["checks"], but the
# rows it was fed come from miner_fingerprint_history.profile_json, which holds
# the flat 4-metric temporal profile ({clock_drift_cv, thermal_variance, ...}).
# normalize_fingerprint therefore returned {} for EVERY miner and the identity
# collapsed to hash(device_arch): ADM paid one miner per architecture (prod
# epochs 250-295). Even if it parsed, a 4-float profile is not a machine
# identity: honest legacy clients (the lab's G4s) all send the same constant.
#
# Identity is resolved from persisted MACHINE evidence only. Two enrolled
# miners are DIRECTLY linked iff they
#   * report a common miner_macs.mac_hash whose observation interval
#     [first_ts, last_ts] overlaps [epoch_start - ADM_MAC_RECENCY_S, next_epoch_start)
#     (first_ts is immutable, so a MAC first reported after the epoch ended can
#     never regroup it; see NOTES "ADM IDENTITY FIX" for the last_ts caveat),
#   * AND have the same node-recorded miner_attest_recent.source_ip (the only
#     IP the node persists: latest attestation, no per-epoch history),
#   * AND have the same device_arch.
# Groups are formed ONLY from miners that are all pairwise directly linked
# (no union-find chaining). A miner that links two miners which are not
# directly linked to each other is a BRIDGE CONFLICT: it is returned in
# `conflicts`, becomes its own identity, and the settlement holds it at 0 for
# this epoch; the miners it bridged are not merged.
# A miner with no such evidence is its OWN identity -- never its arch.
ADM_MAC_RECENCY_S = 7 * 86400
_ADM_IN_CHUNK = 500


def _table_columns(conn: sqlite3.Connection, table: str) -> set:
    """Columns of `table`; empty set when the table does not exist.

    Not wrapped in try/except on purpose: PRAGMA on an absent table returns no
    rows, so an exception here is a genuine database fault and must propagate
    (settlement rolls back and the epoch stays unsettled for retry)."""
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}  # fetchall-ok: pragma-result


def _chunks(items: List[str]):
    for i in range(0, len(items), _ADM_IN_CHUNK):
        yield items[i:i + _ADM_IN_CHUNK]


def _as_ip(value) -> str:
    """Normalise a stored source_ip of any SQLite type; '' when unusable."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8", "strict")
        except UnicodeDecodeError:
            return ""
    if not isinstance(value, str):
        # INTEGER/REAL in a TEXT-affinity column is not an address we recorded.
        logger.warning("ADM identity: non-text source_ip %r ignored", value)
        return ""
    return value.strip()


def _load_source_ips(conn: sqlite3.Connection, miners: List[str]) -> Dict[str, str]:
    cols = _table_columns(conn, "miner_attest_recent")
    if not {"miner", "source_ip"} <= cols:
        return {}
    order = "miner, ts_ok DESC, rowid DESC" if "ts_ok" in cols else "miner, rowid DESC"
    ips: Dict[str, str] = {}
    for chunk in _chunks(miners):
        rows = conn.execute(
            f"SELECT miner, source_ip FROM miner_attest_recent "
            f"WHERE miner IN ({','.join('?' * len(chunk))}) ORDER BY {order}",
            chunk,
        ).fetchall()  # fetchall-ok: already-paginated (IN-chunk of <=500 miners, miner is PK)
        for miner, raw in rows:
            if miner in ips:
                continue  # first row per miner wins (miner is PK in prod)
            ip = _as_ip(raw)
            if ip:
                ips[miner] = ip
    return ips


def _epoch_next_start_ts(epoch: int) -> int:
    """Start of epoch+1: the EXCLUSIVE upper bound of `epoch`'s evidence window.

    Round-2 review: the old bound was the start of the epoch's LAST slot, so a
    MAC first reported during that final 600 s slot was wrongly excluded."""
    return GENESIS_TIMESTAMP + (int(epoch) + 1) * 144 * BLOCK_TIME


def _load_epoch_macs(conn: sqlite3.Connection, miners: List[str],
                     epoch_start_ts: int, epoch_until_ts: int) -> Dict[str, set]:
    """MAC hashes observed in [epoch_start - ADM_MAC_RECENCY_S, epoch_until_ts).

    `epoch_until_ts` is EXCLUSIVE (the next epoch's start)."""
    cols = _table_columns(conn, "miner_macs")
    if not {"miner", "mac_hash", "last_ts"} <= cols:
        return {}
    since = int(epoch_start_ts) - ADM_MAC_RECENCY_S
    until = int(epoch_until_ts)
    if "first_ts" in cols:
        window = "last_ts >= ? AND first_ts < ?"
    else:  # legacy schema: only last_ts, bound it on both sides
        window = "last_ts >= ? AND last_ts < ?"
    macs: Dict[str, set] = {}
    for chunk in _chunks(miners):
        rows = conn.execute(
            f"SELECT miner, mac_hash FROM miner_macs "
            f"WHERE miner IN ({','.join('?' * len(chunk))}) AND {window}",
            list(chunk) + [since, until],
        ).fetchall()  # fetchall-ok: already-paginated (IN-chunk of <=500 miners, window-bounded)
        for miner, mac_hash in rows:
            if mac_hash is None or str(mac_hash) == "":
                continue
            macs.setdefault(miner, set()).add(str(mac_hash))
    return macs


def resolve_machine_identities_ex(
    conn: sqlite3.Connection,
    miner_archs: Dict[str, str],
    epoch_start_ts: int,
    epoch_end_ts: Optional[int] = None,
) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    """(miner_id -> identity hash, {conflict_miner: [miners it bridged]}).

    `epoch_end_ts` is the EXCLUSIVE upper bound of the evidence window (the
    next epoch's start); default = epoch_start_ts + one epoch.

    Never raises for a missing table/column (every miner is its own identity);
    a sqlite error on a PRESENT table propagates (fail loud, settlement rolls
    back)."""
    if epoch_end_ts is None:
        epoch_end_ts = int(epoch_start_ts) + 144 * BLOCK_TIME
    miners = list(dict.fromkeys(miner_archs))
    ips = _load_source_ips(conn, miners)
    macs = _load_epoch_macs(conn, [m for m in miners if m in ips],
                            epoch_start_ts, epoch_end_ts)

    # Direct links: same (arch, ip) bucket and >= 1 common MAC.
    buckets: Dict[Tuple[str, str], List[str]] = {}
    for m in miners:
        if m in ips and macs.get(m):
            arch = str(miner_archs.get(m) or "unknown").lower()
            buckets.setdefault((arch, ips[m]), []).append(m)
    adj: Dict[str, set] = {m: set() for m in miners}
    for members in buckets.values():
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                if macs[a] & macs[b]:
                    adj[a].add(b)
                    adj[b].add(a)

    # Bridge conflicts: a miner with two neighbours that are not linked to
    # each other would chain separate machines together.
    conflicts: Dict[str, List[str]] = {}
    for m in miners:
        nbrs = sorted(adj[m])
        bridged = set()
        for i, a in enumerate(nbrs):
            for b in nbrs[i + 1:]:
                if b not in adj[a]:
                    bridged.update((a, b))
        if bridged:
            conflicts[m] = sorted(bridged)

    # Components of the graph without conflict miners. Every remaining
    # component is a clique (a non-clique path u-v-w makes v a conflict).
    seen: set = set()
    identities: Dict[str, str] = {}
    for m in sorted(miners):
        if m in seen:
            continue
        if m in conflicts:
            seen.add(m)
            identities[m] = hashlib.sha256(("conflict|" + m).encode()).hexdigest()[:16]
            continue
        comp, stack = [], [m]
        seen.add(m)
        while stack:
            x = stack.pop()
            comp.append(x)
            for y in adj[x]:
                if y not in seen and y not in conflicts:
                    seen.add(y)
                    stack.append(y)
        comp.sort()
        if len(comp) > 1:
            common = set.intersection(*(macs[x] for x in comp))
            logger.info("ADM identity: %d miner ids share machine evidence "
                        "(arch=%s ip=%s common_macs=%d): %s",
                        len(comp), str(miner_archs.get(comp[0])).lower(), ips[comp[0]],
                        len(common), comp)
            basis = "machine|" + "|".join(comp)
        else:
            basis = "miner|" + comp[0]
        ident = hashlib.sha256(basis.encode()).hexdigest()[:16]
        for x in comp:
            identities[x] = ident
    for m, bridged in conflicts.items():
        logger.critical("ADM identity: BRIDGE CONFLICT %s reports MACs linking miners that "
                        "share no MAC with each other %s (same ip/arch); held at 0 for this "
                        "epoch, bridged miners NOT merged", m, bridged)
    return identities, conflicts


def resolve_machine_identities(
    conn: sqlite3.Connection,
    miner_archs: Dict[str, str],
    epoch_start_ts: int,
    epoch_end_ts: Optional[int] = None,
) -> Dict[str, str]:
    """Map miner_id -> machine identity hash (see ADM IDENTITY FIX above)."""
    return resolve_machine_identities_ex(conn, miner_archs, epoch_start_ts, epoch_end_ts)[0]


def _safe_weight(value, miner_id: str = "?", what: str = "weight") -> float:
    """Finite, non-negative float; anything else -> 0.0 with a log line. Never raises."""
    try:
        w = float(value if value is not None else 0.0)
    except (TypeError, ValueError, OverflowError):
        logger.error("ADM: non-numeric %s %r for %s treated as 0", what, value, miner_id)
        return 0.0
    if not math.isfinite(w) or w < 0:
        logger.error("ADM: invalid %s %r for %s treated as 0", what, value, miner_id)
        return 0.0
    return w


def _first_seen_map(conn: sqlite3.Connection, miners: List[str]) -> Dict[str, int]:
    """Earliest node-recorded evidence of each miner (attestation history or
    hardware binding). Missing tables contribute nothing."""
    first: Dict[str, int] = {}
    bad_logged = [False]

    def _take(rows):
        for m, ts in rows:
            if ts is None:
                continue
            # Round-2 review: int(inf) raises OverflowError, which escaped and
            # aborted settlement. Non-finite / negative / unparsable values are
            # treated as missing evidence (logged once), never raised.
            try:
                f = float(ts)
                ok = math.isfinite(f) and f >= 0
                t = int(f) if ok else None
            except (TypeError, ValueError, OverflowError):
                t = None
            if t is None:
                if not bad_logged[0]:
                    logger.error("ADM: invalid first-seen timestamp %r for %s treated as "
                                 "missing (further invalid values not logged)", ts, m)
                    bad_logged[0] = True
                continue
            if m not in first or t < first[m]:
                first[m] = t

    if {"miner", "ts_ok"} <= _table_columns(conn, "miner_attest_history"):
        for chunk in _chunks(miners):
            _take(conn.execute(
                f"SELECT miner, MIN(ts_ok) FROM miner_attest_history "
                f"WHERE miner IN ({','.join('?' * len(chunk))}) GROUP BY miner",
                chunk).fetchall())  # fetchall-ok: already-paginated (IN-chunk of <=500, GROUP BY miner)
    if {"bound_miner", "bound_at"} <= _table_columns(conn, "hardware_bindings"):
        for chunk in _chunks(miners):
            _take(conn.execute(
                f"SELECT bound_miner, MIN(bound_at) FROM hardware_bindings "
                f"WHERE bound_miner IN ({','.join('?' * len(chunk))}) GROUP BY bound_miner",
                chunk).fetchall())  # fetchall-ok: already-paginated (IN-chunk of <=500, GROUP BY)
    return first


@dataclass
class MachineIdentity:
    """Represents a unique physical machine identity."""
    identity_hash: str
    device_arch: str
    fingerprint_profile: Dict[str, Any]
    associated_miner_ids: List[str]
    
    def to_dict(self) -> Dict:
        return {
            "identity_hash": self.identity_hash,
            "device_arch": self.device_arch,
            "associated_miner_count": len(self.associated_miner_ids),
            "associated_miner_ids": self.associated_miner_ids
        }


# =============================================================================
# DUPLICATE DETECTION
# =============================================================================

def detect_duplicate_identities(
    conn: sqlite3.Connection,
    epoch: int,
    epoch_start_ts: int,
    epoch_end_ts: int
) -> List[MachineIdentity]:
    """
    Detect machines with multiple miner IDs in the same epoch.

    Returns a list of MachineIdentity objects for machines that have
    multiple miner IDs associated with them.

    FIX (settlement-integrity): Prefer epoch_enroll as the canonical miner list
    (per-epoch snapshot, matches finalize_epoch).  Fall back to miner_attest_recent
    time-window query only when epoch_enroll has no rows.
    """
    cursor = conn.cursor()

    # Primary source: epoch_enroll (per-epoch snapshot).
    cursor.execute(
        "SELECT miner_pk FROM epoch_enroll WHERE epoch = ?",
        (epoch,)
    )
    enrolled = cursor.fetchall()

    if enrolled:
        rows = []
        for (miner_pk,) in enrolled:
            profile_row = cursor.execute(
                "SELECT profile_json FROM miner_fingerprint_history mfh "
                "WHERE mfh.miner = ? ORDER BY mfh.ts DESC LIMIT 1",
                (miner_pk,)
            ).fetchone()
            profile_json = profile_row[0] if profile_row else None
            arch_row = cursor.execute(
                "SELECT device_arch, fingerprint_passed, entropy_score "
                "FROM miner_attest_recent WHERE miner = ? LIMIT 1",
                (miner_pk,)
            ).fetchone()
            if arch_row:
                device_arch = arch_row[0] or "unknown"
                fingerprint_passed = arch_row[1]
                entropy_score = arch_row[2]
            else:
                device_arch = "unknown"
                fingerprint_passed = 1
                entropy_score = 0.0
            rows.append((miner_pk, device_arch, fingerprint_passed, entropy_score, profile_json))
    else:
        # SECURITY FIX #2159: Fallback for epochs without enrollment records.
        # Vulnerable to stale-attestation drop when settlement is delayed.
        logger.warning(
            "detect_duplicate_identities: epoch %d has no epoch_enroll rows, "
            "falling back to miner_attest_recent (may drop miners if delayed)",
            epoch
        )
        cursor.execute("""
            SELECT
                miner,
                device_arch,
                fingerprint_passed,
                entropy_score,
                (
                    SELECT profile_json
                    FROM miner_fingerprint_history mfh
                    WHERE mfh.miner = miner_attest_recent.miner
                    ORDER BY mfh.ts DESC
                    LIMIT 1
                ) as latest_profile
            FROM miner_attest_recent
            WHERE ts_ok >= ? AND ts_ok <= ?
            ORDER BY device_arch, entropy_score DESC
        """, (epoch_start_ts, epoch_end_ts))
        rows = cursor.fetchall()

    # Group miners by machine identity
    identity_map: Dict[str, List[Tuple[str, Dict]]] = {}  # identity_hash -> [(miner_id, attestation_data)]
    # ADM IDENTITY FIX: machine evidence, not hash(arch + unparsed profile).
    _identities = resolve_machine_identities(
        conn, {r[0]: (r[1] or "unknown") for r in rows}, epoch_start_ts,
        _epoch_next_start_ts(epoch),   # exclusive evidence bound (round-2 review)
    )

    for row in rows:
        miner_id, device_arch, fingerprint_passed, entropy_score, profile_json = row
        
        # Parse fingerprint profile
        fingerprint_profile = {}
        if profile_json:
            try:
                fingerprint_profile = json.loads(profile_json)
            except (json.JSONDecodeError, TypeError):
                pass
        
        # Compute machine identity (ADM IDENTITY FIX)
        identity_hash = _identities[miner_id]
        
        if identity_hash not in identity_map:
            identity_map[identity_hash] = []
        
        identity_map[identity_hash].append((
            miner_id,
            {
                "device_arch": device_arch,
                "fingerprint_passed": fingerprint_passed,
                "entropy_score": entropy_score,
                "fingerprint_profile": fingerprint_profile
            }
        ))
    
    # Identify duplicates (machines with multiple miner IDs)
    duplicates = []
    for identity_hash, miners in identity_map.items():
        if len(miners) > 1:
            # This machine has multiple miner IDs
            device_arch = miners[0][1]["device_arch"]
            fingerprint_profile = miners[0][1]["fingerprint_profile"]
            miner_ids = [m[0] for m in miners]
            
            duplicates.append(MachineIdentity(
                identity_hash=identity_hash,
                device_arch=device_arch or "unknown",
                fingerprint_profile=fingerprint_profile,
                associated_miner_ids=miner_ids
            ))
    
    return duplicates


def log_duplicate_detection(duplicates: List[MachineIdentity], epoch: int):
    """
    Log telemetry for duplicate identity detection.
    
    This provides visibility into potential double-mining attempts.
    """
    if not duplicates:
        logger.info(f"Epoch {epoch}: No duplicate machine identities detected")
        return
    
    logger.warning(f"Epoch {epoch}: Detected {len(duplicates)} machines with multiple miner IDs")
    
    for machine in duplicates:
        logger.warning(
            f"  Machine {machine.identity_hash[:8]}... ({machine.device_arch}): "
            f"{len(machine.associated_miner_ids)} miner IDs detected"
        )
        for i, miner_id in enumerate(machine.associated_miner_ids):
            logger.warning(f"    [{i+1}] {miner_id}")
    
    # Emit metrics-style log for monitoring systems
    logger.info(f"METRIC: duplicate_machines_count={len(duplicates)} epoch={epoch}")


# =============================================================================
# REWARD SELECTION
# =============================================================================

def select_representative_miner(
    conn: sqlite3.Connection,
    miner_ids: List[str],
    epoch: Optional[int] = None,
    held: Optional[set] = None,
) -> str:
    """
    Select one representative miner ID from a group of miner IDs belonging to the same machine.

    Selection criteria (in order of priority):
    0. Unheld miners before held ones (a held alias cannot take the slot)
    1. ESTABLISHED FIRST (ADM round 2, NAT copycat): the earliest node-recorded
       first-seen (miner_attest_history / hardware_bindings). A newer identity
       that copied an established miner's MAC behind the same egress cannot
       displace it by enrolling heavier. Miners with no first-seen evidence
       rank after those with evidence.
    2. Highest enrolled epoch weight (when epoch is provided)
    3. Highest entropy score, then most recent attestation
    4. First miner ID alphabetically (deterministic tie-breaker)
    """
    if len(miner_ids) == 1:
        return miner_ids[0]

    held = held or set()
    candidates = [m for m in miner_ids if m not in held] or list(miner_ids)

    first_seen = _first_seen_map(conn, candidates)
    if first_seen:
        earliest = min(first_seen.get(m, float("inf")) for m in candidates)
        established = [m for m in candidates if first_seen.get(m, float("inf")) == earliest]
    else:
        established = list(candidates)

    epoch_weights: Dict[str, float] = {}
    if epoch is not None:
        epoch_weights = {m: (0.0 if m in held else w)
                         for m, w in _get_epoch_enrolled_weights(conn, epoch).items()}

    def _by_weight(ids: List[str]) -> List[str]:
        if not epoch_weights:
            return ids
        best = max(epoch_weights.get(m, 0.0) for m in ids)
        return [m for m in ids if epoch_weights.get(m, 0.0) == best]

    pool = _by_weight(established)
    if len(pool) > 1:
        placeholders = ",".join("?" * len(pool))
        rows = conn.execute(f"""
            SELECT miner, entropy_score, ts_ok
            FROM miner_attest_recent
            WHERE miner IN ({placeholders})
            ORDER BY entropy_score DESC, ts_ok DESC, miner ASC
        """, pool).fetchall()  # fetchall-ok: bounded-by-schema (one machine group, miner is PK)
        choice = rows[0][0] if rows else sorted(pool)[0]
    else:
        choice = pool[0]

    weight_only = sorted(_by_weight(candidates))[0] if epoch_weights else None
    if weight_only is not None and weight_only != choice and first_seen:
        logger.warning(
            "ADM representative: kept established %s (first_seen=%s) over heavier/newer %s "
            "(first_seen=%s) in group %s",
            choice, first_seen.get(choice), weight_only, first_seen.get(weight_only),
            sorted(miner_ids))
    return choice


def get_epoch_miner_groups(
    conn: sqlite3.Connection,
    epoch: int
) -> Dict[str, List[str]]:
    """
    Get all miners attested in an epoch, grouped by machine identity.
    
    Returns:
        Dict mapping machine_identity_hash -> list of miner_ids
    """
    return get_epoch_miner_groups_ex(conn, epoch)[0]


def get_epoch_miner_groups_ex(
    conn: sqlite3.Connection,
    epoch: int
) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    """(groups, bridge conflicts) -- see resolve_machine_identities_ex."""
    epoch_start_slot = epoch * 144
    epoch_end_slot = epoch_start_slot + 143
    epoch_start_ts = GENESIS_TIMESTAMP + (epoch_start_slot * BLOCK_TIME)
    epoch_end_ts = GENESIS_TIMESTAMP + (epoch_end_slot * BLOCK_TIME)

    cursor = conn.cursor()

    # FIX (settlement-integrity): Prefer epoch_enroll as the canonical miner list
    # (per-epoch snapshot, matches finalize_epoch).  Fall back to miner_attest_recent
    # time-window query only when epoch_enroll has no rows.
    cursor.execute(
        "SELECT miner_pk FROM epoch_enroll WHERE epoch = ?",
        (epoch,)
    )
    enrolled = cursor.fetchall()

    if enrolled:
        # Build miner list from epoch_enroll; look up arch + fingerprint history.
        rows = []
        for (miner_pk,) in enrolled:
            profile_row = cursor.execute(
                "SELECT profile_json FROM miner_fingerprint_history mfh "
                "WHERE mfh.miner = ? ORDER BY mfh.ts DESC LIMIT 1",
                (miner_pk,)
            ).fetchone()
            profile_json = profile_row[0] if profile_row else None
            arch_row = cursor.execute(
                "SELECT device_arch FROM miner_attest_recent WHERE miner = ? LIMIT 1",
                (miner_pk,)
            ).fetchone()
            device_arch = (arch_row[0] or "unknown") if arch_row else "unknown"
            rows.append((miner_pk, device_arch, profile_json))
    else:
        # SECURITY FIX #2159: Fallback for epochs without enrollment records.
        # Vulnerable to stale-attestation drop when settlement is delayed.
        logger.warning(
            "get_epoch_miner_groups: epoch %d has no epoch_enroll rows, "
            "falling back to miner_attest_recent (may drop miners if delayed)",
            epoch
        )
        cursor.execute("""
            SELECT
                miner,
                COALESCE(device_arch, 'unknown') as device_arch,
                (
                    SELECT profile_json
                    FROM miner_fingerprint_history mfh
                    WHERE mfh.miner = miner_attest_recent.miner
                    ORDER BY mfh.ts DESC
                    LIMIT 1
                ) as latest_profile
            FROM miner_attest_recent
            WHERE ts_ok >= ? AND ts_ok <= ?
        """, (epoch_start_ts, epoch_end_ts))
        rows = cursor.fetchall()
    
    # Group by machine identity (ADM IDENTITY FIX: machine evidence only;
    # a miner without evidence is its own identity, never its arch).
    groups: Dict[str, List[str]] = {}
    _identities, _conflicts = resolve_machine_identities_ex(
        conn, {r[0]: (r[1] or "unknown") for r in rows}, epoch_start_ts,
        _epoch_next_start_ts(epoch),   # exclusive evidence bound (round-2 review)
    )

    for miner_id, device_arch, profile_json in rows:
        identity_hash = _identities[miner_id]
        
        if identity_hash not in groups:
            groups[identity_hash] = []
        
        if miner_id not in groups[identity_hash]:
            groups[identity_hash].append(miner_id)
    
    return groups, _conflicts


def _get_epoch_enrolled_weights(conn: sqlite3.Connection, epoch: int) -> Dict[str, float]:
    """Return canonical per-epoch weights from epoch_enroll when available.

    Older test/legacy schemas only have (epoch, miner_pk).  In that case this
    returns an empty map and callers fall back to the historical arch-derived
    multiplier path.
    """
    # SYBIL-GUARD (round 2): these used to swallow every sqlite3.Error and
    # return {}, which made the caller fall back to ARCH multipliers for every
    # miner -- a held (weight 0) G4 would then be paid 2.5x. Only a genuinely
    # absent table/column is "no weights"; any other error propagates so the
    # settlement rolls back and the epoch stays unsettled for retry.
    cols = conn.execute("PRAGMA table_info(epoch_enroll)").fetchall()

    if not any(col[1] == "weight" for col in cols):
        return {}

    rows = conn.execute(
        "SELECT miner_pk, weight FROM epoch_enroll WHERE epoch = ?",
        (epoch,),
    ).fetchall()

    weights: Dict[str, float] = {}
    for miner_pk, weight in rows:
        # NaN / inf / negative / non-numeric -> 0 with a log line, never raise
        # (SQLite's dynamic typing admits all of them in an INTEGER column).
        weights[miner_pk] = _safe_weight(weight, miner_pk, "enrolled weight")
    return weights


# =============================================================================
# ANTI-DOUBLE-MINING REWARD CALCULATION
# =============================================================================

def calculate_anti_double_mining_rewards(
    db_path: str,
    epoch: int,
    total_reward_urtc: int,
    current_slot: int
) -> Tuple[Dict[str, int], Dict[str, Any]]:
    """
    Calculate epoch rewards with anti-double-mining enforcement.
    
    This function:
    1. Groups miners by machine identity (not miner_id)
    2. Selects one representative miner per machine
    3. Distributes rewards per machine, not per miner_id
    4. Returns telemetry data about duplicate detections
    
    Args:
        db_path: Database path
        epoch: Epoch number
        total_reward_urtc: Total uRTC to distribute
        current_slot: Current blockchain slot
    
    Returns:
        Tuple of (rewards_dict, telemetry_dict)
        - rewards_dict: {miner_id: reward_urtc} for representative miners only
        - telemetry_dict: Detection statistics for monitoring
    """
    # SYBIL-GUARD (round 2): delegate to the connection variant so the review
    # hold lives in one place. Read-only: record_escrow=False, never committed.
    with closing(sqlite3.connect(db_path)) as conn:
        return _calculate_anti_double_mining_rewards_conn(
            conn, epoch, total_reward_urtc, current_slot, record_escrow=False
        )


def settle_epoch_with_anti_double_mining(
    db_path: str,
    epoch: int,
    per_epoch_urtc: int,
    current_slot: int,
    existing_conn=None
) -> Dict[str, Any]:
    """
    Settle epoch rewards with anti-double-mining enforcement.

    When *existing_conn* is provided (a live sqlite3.Connection already holding
    ``BEGIN IMMEDIATE``), it is used for all reads/writes and the caller owns
    the transaction lifecycle.  When omitted, a fresh connection is opened
    (legacy / standalone-call compatibility).

    Returns:
        Settlement result with telemetry data
    """
    UNIT = 1_000_000

    if existing_conn is not None:
        db = existing_conn
        own_conn = False
    else:
        db = sqlite3.connect(db_path, timeout=10)
        own_conn = True
        db.execute("BEGIN IMMEDIATE")

    try:
        # Atomic check-and-set for settlement
        # We use an UPDATE that only succeeds if settled is currently 0.
        # This prevents the race condition.
        res = db.execute("UPDATE epoch_state SET settled = 1, settled_ts = ? WHERE epoch = ? AND settled = 0", (int(time.time()), epoch))
        claimed = res.rowcount > 0
        if res.rowcount == 0:
            # If no row was updated, it was either already settled or doesn't exist
            st = db.execute("SELECT settled FROM epoch_state WHERE epoch=?", (epoch,)).fetchone()
            if st and int(st[0]) == 1:
                if own_conn:
                    db.rollback()
                return {"ok": True, "epoch": epoch, "already_settled": True}
            # If it doesn't exist, we can proceed to create it (handled by the later INSERT)


        # Calculate rewards with anti-double-mining.
        # When we share the caller's connection we must NOT open a separate one.
        # SYBIL-GUARD: always compute on `db` (the settlement transaction), so
        # the hold read and the escrow write are atomic with the credits.
        rewards, telemetry = _calculate_anti_double_mining_rewards_conn(
            db, epoch, per_epoch_urtc, current_slot
        )

        if not rewards:
            if own_conn:
                db.rollback()
            elif claimed:
                # Shared connection: the caller owns the transaction and commits
                # on return (see settle_epoch_rip200), so `own_conn`-gated rollback
                # never runs and the claim above would be committed despite paying
                # nothing — burning the epoch's emission and making every retry
                # answer already_settled. Rolling back is not ours to do here, so
                # undo only our own claim and leave the epoch retryable. This
                # matches the standard path, which rolls back before returning the
                # same error.
                db.execute(
                    "UPDATE epoch_state SET settled = 0, settled_ts = NULL WHERE epoch = ?",
                    (epoch,)
                )
            return {"ok": False, "error": "no_eligible_miners", "epoch": epoch}

        # Credit rewards to miners
        ts_now = int(time.time())
        miners_data = []

        for miner_id, share_urtc in rewards.items():
            # Insert or update balance
            db.execute(
                "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?) "
                "ON CONFLICT(miner_id) DO UPDATE SET amount_i64 = amount_i64 + ?",
                (miner_id, share_urtc, share_urtc)
            )

            # Record in ledger
            db.execute(
                "INSERT INTO ledger (ts, epoch, miner_id, delta_i64, reason) VALUES (?, ?, ?, ?, ?)",
                (ts_now, epoch, miner_id, share_urtc, f"epoch_{epoch}_reward")
            )

            # Record in epoch_rewards
            db.execute(
                "INSERT INTO epoch_rewards (epoch, miner_id, share_i64) VALUES (?, ?, ?)",
                (epoch, miner_id, share_urtc)
            )

            # Get metadata for reporting
            arch_row = db.execute(
                "SELECT device_arch FROM miner_attest_recent WHERE miner = ? LIMIT 1",
                (miner_id,)
            ).fetchone()
            device_arch = arch_row[0] if arch_row else "unknown"

            from rip_200_round_robin_1cpu1vote import get_time_aged_multiplier, get_chain_age_years
            chain_age = get_chain_age_years(current_slot)
            multiplier = get_time_aged_multiplier(device_arch, chain_age)

            miners_data.append({
                "miner_id": miner_id,
                "share_urtc": share_urtc,
                "share_rtc": share_urtc / UNIT,
                "multiplier": round(multiplier, 3),
                "device_arch": device_arch
            })

        # Mark epoch as settled without replacing the whole row.
        # INSERT OR REPLACE deletes any existing epoch_state metadata columns
        # (for example finalized/accepted_blocks/pot) before inserting the
        # narrow settlement row. Preserve unrelated epoch state fields.
        updated = db.execute(
            "UPDATE epoch_state SET settled = 1, settled_ts = ? WHERE epoch = ?",
            (ts_now, epoch)
        ).rowcount
        if updated == 0:
            db.execute(
                "INSERT INTO epoch_state (epoch, settled, settled_ts) VALUES (?, 1, ?)",
                (epoch, ts_now)
            )

        if own_conn:
            db.commit()

        return {
            "ok": True,
            "epoch": epoch,
            "distributed_rtc": per_epoch_urtc / UNIT,
            "distributed_urtc": per_epoch_urtc,
            "miners": miners_data,
            "chain_age_years": round(get_chain_age_years(current_slot), 2),
            "anti_double_mining_telemetry": telemetry
        }

    except Exception as e:
        if own_conn:
            try:
                db.rollback()
            except Exception:
                pass
        raise
    finally:
        if own_conn:
            db.close()


def _calculate_anti_double_mining_rewards_conn(
    conn,
    epoch: int,
    total_reward_urtc: int,
    current_slot: int,
    record_escrow: bool = True,
) -> Tuple[Dict[str, int], Dict[str, Any]]:
    """Same as calculate_anti_double_mining_rewards but uses an existing connection.

    The caller owns the transaction lifecycle — this function does NOT commit
    or rollback.
    """
    from rip_200_round_robin_1cpu1vote import get_time_aged_multiplier, get_chain_age_years

    chain_age_years = get_chain_age_years(current_slot)

    epoch_start_slot = epoch * 144
    epoch_end_slot = epoch_start_slot + 143
    epoch_start_ts = GENESIS_TIMESTAMP + (epoch_start_slot * BLOCK_TIME)
    epoch_end_ts = GENESIS_TIMESTAMP + (epoch_end_slot * BLOCK_TIME)

    # Detect duplicate identities
    duplicates = detect_duplicate_identities(conn, epoch, epoch_start_ts, epoch_end_ts)

    # Log telemetry
    log_duplicate_detection(duplicates, epoch)

    # Get all miner groups by machine identity
    miner_groups, identity_conflicts = get_epoch_miner_groups_ex(conn, epoch)

    # SYBIL-GUARD: needs_review / incident-cohort miners settle at 0, read on
    # the settlement connection. When record_escrow, each held miner's
    # positive enrolled weight is escrowed in the same transaction as the
    # credits. hold_for_settlement never raises.
    _all_ids = [m for ids in miner_groups.values() for m in ids]
    # weights is passed as a callable so a transient read error here only
    # skips the escrow record (hold still applied) instead of aborting the
    # settlement. The payout weights below are read again and stay fail-loud.
    _held = sybil_guard.hold_for_settlement(
        conn, epoch, _all_ids,
        weights=lambda: _get_epoch_enrolled_weights(conn, epoch),
        record=record_escrow,
    )
    # ADM round 2: bridge-conflict miners (MACs linking miners that share no
    # MAC with each other) settle at 0 for this epoch, escrowed like a review
    # hold. The miners they bridged stay separate and are paid normally.
    if identity_conflicts:
        _held = set(_held) | set(identity_conflicts)
        if record_escrow:
            _cw = _get_epoch_enrolled_weights(conn, epoch)
            for _m in sorted(identity_conflicts):
                _units = int(_cw.get(_m, 0.0))
                if _units > 0:
                    sybil_guard.record_review_escrow_safe(
                        conn, epoch, _m, _units, "adm_identity_bridge_conflict")

    # Select representative miner for each machine
    representative_map: Dict[str, str] = {}  # machine_identity -> representative_miner_id
    skipped_miners: Dict[str, str] = {}  # skipped_miner_id -> representative_miner_id

    for identity_hash, miner_ids in miner_groups.items():
        if len(miner_ids) > 1:
            rep = select_representative_miner(conn, miner_ids, epoch=epoch, held=_held)
            representative_map[identity_hash] = rep
            for mid in miner_ids:
                if mid != rep:
                    skipped_miners[mid] = rep
        else:
            representative_map[identity_hash] = miner_ids[0]

    cursor = conn.cursor()
    enrolled_weights = _get_epoch_enrolled_weights(conn, epoch)
    machine_data = []

    for identity_hash, miner_id in representative_map.items():
        row = cursor.execute(
            "SELECT device_arch, COALESCE(fingerprint_passed, 1) FROM miner_attest_recent WHERE miner=?",
            (miner_id,)
        ).fetchone()

        if row:
            device_arch = row[0] or "unknown"
            fingerprint_ok = row[1]
            machine_data.append((miner_id, device_arch, fingerprint_ok, identity_hash))

    # Calculate time-aged weights for each machine
    weighted_machines = []
    total_weight = 0.0

    for miner_id, device_arch, fingerprint_ok, identity_hash in machine_data:
        if miner_id in _held:
            weight = 0.0  # SYBIL-GUARD review hold (escrowed above)
        elif fingerprint_ok == 0:
            weight = 0.0
        elif miner_id in enrolled_weights:
            # Preserve the canonical per-epoch weight snapshot used by the
            # normal settlement path.  Recomputing from device_arch here can
            # change the payout split for delayed settlements or RIP-309
            # filtered weights.
            weight = enrolled_weights[miner_id]
        else:
            weight = _safe_weight(get_time_aged_multiplier(device_arch, chain_age_years),
                                  miner_id, "arch multiplier")

        if weight > 0 and fingerprint_ok == 1:
            try:
                wart_row = cursor.execute(
                    "SELECT warthog_bonus FROM miner_attest_recent WHERE miner=?",
                    (miner_id,)
                ).fetchone()
                # Apply capped warthog bonus (MAX = 2.0) to prevent reward inflation.
                # Non-finite / malformed values are treated as 0 (no bonus).
                bonus = _safe_weight(wart_row[0], miner_id, "warthog_bonus") if wart_row else 0.0
                if 1.0 < bonus <= 2.0:
                    weight *= bonus
                elif bonus > 2.0:
                    weight *= 2.0
            except Exception:
                pass
        weight = _safe_weight(weight, miner_id, "settlement weight")

        weighted_machines.append((miner_id, weight))
        total_weight += weight

    # Distribute rewards
    rewards = {}
    remaining = total_reward_urtc
    positive_weight_miners = [(mid, w) for mid, w in weighted_machines if w > 0]

    if not positive_weight_miners:
        return {}, {
            "epoch": epoch,
            "total_machines": len(representative_map),
            "total_miner_ids_processed": sum(len(ids) for ids in miner_groups.values()),
            "duplicate_machines_detected": len(duplicates),
            "duplicate_miner_ids_skipped": len(skipped_miners),
            "skipped_details": [
                {"skipped": skipped, "rewarded_representative": rep}
                for skipped, rep in skipped_miners.items()
            ],
            "duplicate_machine_details": [d.to_dict() for d in duplicates],
            "note": "No eligible miners (all failed fingerprint validation)"
        }

    for i, (miner_id, weight) in enumerate(positive_weight_miners):
        if i == len(positive_weight_miners) - 1:
            share = remaining
        else:
            share = 0 if total_weight == 0 else int((weight / total_weight) * total_reward_urtc)
            remaining -= share
        rewards[miner_id] = share

    return rewards, {
        "epoch": epoch,
        "total_machines": len(representative_map),
        "total_miner_ids_processed": sum(len(ids) for ids in miner_groups.values()),
        "duplicate_machines_detected": len(duplicates),
        "duplicate_miner_ids_skipped": len(skipped_miners),
        "skipped_details": [
            {"skipped": skipped, "rewarded_representative": rep}
            for skipped, rep in skipped_miners.items()
        ],
        "duplicate_machine_details": [d.to_dict() for d in duplicates]
    }


# =============================================================================
# TESTING UTILITIES
# =============================================================================

def setup_test_scenario(db_path: str):
    """
    Setup test database with duplicate miner scenarios.
    
    Creates:
    - Machine A: 3 miner IDs (should only reward 1)
    - Machine B: 1 miner ID (should reward normally)
    - Machine C: 2 miner IDs (should only reward 1)
    """
    # Remove existing test DB
    if os.path.exists(db_path):
        os.remove(db_path)
    
    with closing(sqlite3.connect(db_path)) as conn:
        # Create tables
        conn.execute("""
            CREATE TABLE miner_attest_recent (
                miner TEXT PRIMARY KEY,
                device_arch TEXT,
                ts_ok INTEGER,
                fingerprint_passed INTEGER DEFAULT 1,
                entropy_score REAL,
                warthog_bonus REAL DEFAULT 1.0
            )
        """)
        
        conn.execute("""
            CREATE TABLE miner_fingerprint_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                miner TEXT NOT NULL,
                ts INTEGER NOT NULL,
                profile_json TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE epoch_enroll (
                epoch INTEGER NOT NULL,
                miner_pk TEXT NOT NULL
            )
        """)
        
        conn.execute("""
            CREATE TABLE epoch_state (
                epoch INTEGER PRIMARY KEY,
                settled INTEGER DEFAULT 0,
                settled_ts INTEGER
            )
        """)
        
        conn.execute("""
            CREATE TABLE balances (
                miner_id TEXT PRIMARY KEY,
                amount_i64 INTEGER DEFAULT 0
            )
        """)
        
        conn.execute("""
            CREATE TABLE ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER,
                epoch INTEGER,
                miner_id TEXT,
                delta_i64 INTEGER,
                reason TEXT
            )
        """)
        
        conn.execute("""
            CREATE TABLE epoch_rewards (
                epoch INTEGER,
                miner_id TEXT,
                share_i64 INTEGER,
                PRIMARY KEY (epoch, miner_id)
            )
        """)
        
        # Insert test data
        current_ts = int(time.time())
        epoch = 0
        epoch_start_ts = GENESIS_TIMESTAMP + (epoch * 144 * BLOCK_TIME)
        
        # Machine A: Same fingerprint, 3 different miner IDs
        fingerprint_a = json.dumps({
            "checks": {
                "clock_drift": {"data": {"cv": 0.001, "mean_ns": 100.0}},
                "cpu_serial": {"data": {"serial": "SERIAL-A-12345"}}
            }
        })
        
        conn.execute("""
            INSERT INTO miner_attest_recent (miner, device_arch, ts_ok, fingerprint_passed, entropy_score)
            VALUES (?, ?, ?, ?, ?)
        """, ("miner-a1", "g4", epoch_start_ts + 100, 1, 0.05))
        
        conn.execute("""
            INSERT INTO miner_attest_recent (miner, device_arch, ts_ok, fingerprint_passed, entropy_score)
            VALUES (?, ?, ?, ?, ?)
        """, ("miner-a2", "g4", epoch_start_ts + 200, 1, 0.06))
        
        conn.execute("""
            INSERT INTO miner_attest_recent (miner, device_arch, ts_ok, fingerprint_passed, entropy_score)
            VALUES (?, ?, ?, ?, ?)
        """, ("miner-a3", "g4", epoch_start_ts + 300, 1, 0.07))
        
        # Fingerprint history for Machine A miners (same profile = same machine)
        for miner in ["miner-a1", "miner-a2", "miner-a3"]:
            conn.execute("""
                INSERT INTO miner_fingerprint_history (miner, ts, profile_json)
                VALUES (?, ?, ?)
            """, (miner, current_ts, fingerprint_a))
        
        # Machine B: Unique fingerprint, 1 miner ID
        fingerprint_b = json.dumps({
            "checks": {
                "clock_drift": {"data": {"cv": 0.002, "mean_ns": 200.0}},
                "cpu_serial": {"data": {"serial": "SERIAL-B-67890"}}
            }
        })
        
        conn.execute("""
            INSERT INTO miner_attest_recent (miner, device_arch, ts_ok, fingerprint_passed, entropy_score)
            VALUES (?, ?, ?, ?, ?)
        """, ("miner-b1", "g5", epoch_start_ts + 150, 1, 0.08))
        
        conn.execute("""
            INSERT INTO miner_fingerprint_history (miner, ts, profile_json)
            VALUES (?, ?, ?)
        """, ("miner-b1", current_ts, fingerprint_b))
        
        # Machine C: Same fingerprint, 2 different miner IDs
        fingerprint_c = json.dumps({
            "checks": {
                "clock_drift": {"data": {"cv": 0.003, "mean_ns": 300.0}},
                "cpu_serial": {"data": {"serial": "SERIAL-C-11111"}}
            }
        })
        
        conn.execute("""
            INSERT INTO miner_attest_recent (miner, device_arch, ts_ok, fingerprint_passed, entropy_score)
            VALUES (?, ?, ?, ?, ?)
        """, ("miner-c1", "modern", epoch_start_ts + 250, 1, 0.09))
        
        conn.execute("""
            INSERT INTO miner_attest_recent (miner, device_arch, ts_ok, fingerprint_passed, entropy_score)
            VALUES (?, ?, ?, ?, ?)
        """, ("miner-c2", "modern", epoch_start_ts + 350, 1, 0.10))
        
        for miner in ["miner-c1", "miner-c2"]:
            conn.execute("""
                INSERT INTO miner_fingerprint_history (miner, ts, profile_json)
                VALUES (?, ?, ?)
            """, (miner, current_ts, fingerprint_c))

        # Machine identity evidence. ADM groups miners as one machine only when
        # they share a MAC hash seen in the epoch window AND the same
        # node-observed source_ip AND the same arch; the fingerprint profiles
        # above are not an identity signal.
        conn.execute("ALTER TABLE miner_attest_recent ADD COLUMN source_ip TEXT")
        conn.execute("""
            CREATE TABLE miner_macs (
                miner TEXT NOT NULL,
                mac_hash TEXT NOT NULL,
                first_ts INTEGER NOT NULL,
                last_ts INTEGER NOT NULL,
                count INTEGER DEFAULT 1,
                PRIMARY KEY (miner, mac_hash)
            )
        """)
        evidence = {
            "miner-a1": ("192.0.2.10", "mac-machine-a"),
            "miner-a2": ("192.0.2.10", "mac-machine-a"),
            "miner-a3": ("192.0.2.10", "mac-machine-a"),
            "miner-b1": ("192.0.2.20", "mac-machine-b"),
            "miner-c1": ("192.0.2.30", "mac-machine-c"),
            "miner-c2": ("192.0.2.30", "mac-machine-c"),
        }
        for miner, (ip, mac) in evidence.items():
            conn.execute("UPDATE miner_attest_recent SET source_ip = ? WHERE miner = ?", (ip, miner))
            conn.execute(
                "INSERT INTO miner_macs VALUES (?, ?, ?, ?, 1)",
                (miner, mac, epoch_start_ts + 60, epoch_start_ts + 60),
            )

        conn.commit()
    
    print(f"Test database created at {db_path}")
    return db_path


if __name__ == "__main__":
    import sys
    
    # Run tests
    test_db = os.path.join(tempfile.gettempdir(), "test_anti_double_mining.db")
    setup_test_scenario(test_db)
    
    print("\n=== Testing Anti-Double-Mining Detection ===\n")

    current_slot = (int(time.time()) - GENESIS_TIMESTAMP) // BLOCK_TIME
    rewards, telemetry = calculate_anti_double_mining_rewards(
        test_db, epoch=0, total_reward_urtc=150_000_000, current_slot=current_slot
    )
    
    print(f"\nRewards distributed:")
    for miner_id, reward in sorted(rewards.items()):
        print(f"  {miner_id}: {reward / 1_000_000:.6f} RTC")
    
    print(f"\nTelemetry:")
    print(f"  Total machines: {telemetry['total_machines']}")
    print(f"  Total miner IDs: {telemetry['total_miner_ids_processed']}")
    print(f"  Duplicates detected: {telemetry['duplicate_machines_detected']}")
    print(f"  Skipped miner IDs: {telemetry['duplicate_miner_ids_skipped']}")
    
    if telemetry['skipped_details']:
        print(f"\nSkipped miners (should not be rewarded):")
        for detail in telemetry['skipped_details']:
            print(f"  {detail['skipped']} -> rewarded rep: {detail['rewarded_representative']}")
    
    # Verify: Should have 3 machines, 6 miner IDs, 2 duplicates, 3 skipped
    assert telemetry['total_machines'] == 3, f"Expected 3 machines, got {telemetry['total_machines']}"
    assert telemetry['total_miner_ids_processed'] == 6, f"Expected 6 miner IDs, got {telemetry['total_miner_ids_processed']}"
    assert telemetry['duplicate_machines_detected'] == 2, f"Expected 2 duplicates, got {telemetry['duplicate_machines_detected']}"
    assert telemetry['duplicate_miner_ids_skipped'] == 3, f"Expected 3 skipped, got {telemetry['duplicate_miner_ids_skipped']}"
    assert len(rewards) == 3, f"Expected 3 rewards, got {len(rewards)}"
    
    print("\n✓ All tests passed!")
    
    # Cleanup
    import os
    os.remove(test_db)
