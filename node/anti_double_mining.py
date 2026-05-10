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
    
    for row in rows:
        miner_id, device_arch, fingerprint_passed, entropy_score, profile_json = row
        
        # Parse fingerprint profile
        fingerprint_profile = {}
        if profile_json:
            try:
                fingerprint_profile = json.loads(profile_json)
            except (json.JSONDecodeError, TypeError):
                pass
        
        # Compute machine identity
        identity_hash = compute_machine_identity_hash(device_arch or "unknown", fingerprint_profile)
        
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
    miner_ids: List[str]
) -> str:
    """
    Select one representative miner ID from a group of miner IDs belonging to the same machine.
    
    Selection criteria (in order of priority):
    1. Highest entropy score (most authentic attestation)
    2. Most recent attestation timestamp
    3. First miner ID alphabetically (deterministic tie-breaker)
    
    This ensures consistent selection across re-runs.
    """
    if len(miner_ids) == 1:
        return miner_ids[0]
    
    cursor = conn.cursor()
    
    # Get attestation details for all miner IDs
    placeholders = ",".join("?" * len(miner_ids))
    cursor.execute(f"""
        SELECT miner, entropy_score, ts_ok
        FROM miner_attest_recent
        WHERE miner IN ({placeholders})
        ORDER BY entropy_score DESC, ts_ok DESC, miner ASC
    """, miner_ids)
    
    rows = cursor.fetchall()
    
    if not rows:
        # Fallback: return first miner ID
        return sorted(miner_ids)[0]
    
    # Return miner with highest entropy score (first row after ORDER BY)
    return rows[0][0]


def get_epoch_miner_groups(
    conn: sqlite3.Connection,
    epoch: int
) -> Dict[str, List[str]]:
    """
    Get all miners attested in an epoch, grouped by machine identity.
    
    Returns:
        Dict mapping machine_identity_hash -> list of miner_ids
    """
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
    
    # Group by machine identity
    groups: Dict[str, List[str]] = {}
    
    for miner_id, device_arch, profile_json in rows:
        fingerprint_profile = {}
        if profile_json:
            try:
                fingerprint_profile = json.loads(profile_json)
            except (json.JSONDecodeError, TypeError):
                pass
        
        identity_hash = compute_machine_identity_hash(device_arch, fingerprint_profile)
        
        if identity_hash not in groups:
            groups[identity_hash] = []
        
        if miner_id not in groups[identity_hash]:
            groups[identity_hash].append(miner_id)
    
    return groups


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
    from rip_200_round_robin_1cpu1vote import get_time_aged_multiplier, get_chain_age_years
    
    chain_age_years = get_chain_age_years(current_slot)
    
    epoch_start_slot = epoch * 144
    epoch_end_slot = epoch_start_slot + 143
    epoch_start_ts = GENESIS_TIMESTAMP + (epoch_start_slot * BLOCK_TIME)
    epoch_end_ts = GENESIS_TIMESTAMP + (epoch_end_slot * BLOCK_TIME)

    with sqlite3.connect(db_path) as conn:
        conn.execute("BEGIN")
        
        # Detect duplicate identities
        duplicates = detect_duplicate_identities(conn, epoch, epoch_start_ts, epoch_end_ts)
        
        # Log telemetry
        log_duplicate_detection(duplicates, epoch)
        
        # Get all miner groups by machine identity
        miner_groups = get_epoch_miner_groups(conn, epoch)
        
        # Select representative miner for each machine
        representative_map: Dict[str, str] = {}  # machine_identity -> representative_miner_id
        skipped_miners: Dict[str, str] = {}  # skipped_miner_id -> representative_miner_id
        
        for identity_hash, miner_ids in miner_groups.items():
            if len(miner_ids) > 1:
                # Multiple miners for same machine - select one
                rep = select_representative_miner(conn, miner_ids)
                representative_map[identity_hash] = rep
                
                # Track skipped miners for telemetry
                for mid in miner_ids:
                    if mid != rep:
                        skipped_miners[mid] = rep
                
                logger.info(
                    f"Epoch {epoch}: Machine {identity_hash[:8]}... has {len(miner_ids)} miners, "
                    f"selected {rep} as representative"
                )
            else:
                # Single miner - use directly
                representative_map[identity_hash] = miner_ids[0]
        
        # Get device arch for each representative miner
        cursor = conn.cursor()
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
            # STRICT: VMs/emulators with failed fingerprint get ZERO weight
            if fingerprint_ok == 0:
                weight = 0.0
                logger.info(f"[REWARD] {miner_id[:20]}... fingerprint=FAIL -> weight=0")
            else:
                weight = get_time_aged_multiplier(device_arch, chain_age_years)
            
            # Apply Warthog dual-mining bonus
            if weight > 0 and fingerprint_ok == 1:
                try:
                    wart_row = cursor.execute(
                        "SELECT warthog_bonus FROM miner_attest_recent WHERE miner=?",
                        (miner_id,)
                    ).fetchone()
                    if wart_row and wart_row[0] and wart_row[0] > 1.0:
                        weight *= wart_row[0]
                except Exception:
                    pass
            
            weighted_machines.append((miner_id, weight))
            total_weight += weight

        # Distribute rewards (one per machine, not per miner_id)
        # Only miners with positive weight receive rewards
        rewards = {}
        remaining = total_reward_urtc
        
        # Filter to only positive-weight miners for distribution
        positive_weight_miners = [(mid, w) for mid, w in weighted_machines if w > 0]
        
        if not positive_weight_miners:
            # No eligible miners (all failed fingerprint)
            conn.commit()
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
                # Last miner gets remainder (prevents rounding issues)
                share = remaining
            else:
                share = 0 if total_weight == 0 else int((weight / total_weight) * total_reward_urtc)
                remaining -= share

            rewards[miner_id] = share
        
        conn.commit()
        
        # Build telemetry report
        telemetry = {
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
        
        return rewards, telemetry


# =============================================================================
# INTEGRATION WITH EXISTING REWARDS SYSTEM
# =============================================================================

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
        # Check if already settled
        st = db.execute("SELECT settled FROM epoch_state WHERE epoch=?", (epoch,)).fetchone()
        if st and int(st[0]) == 1:
            if own_conn:
                db.rollback()
            return {"ok": True, "epoch": epoch, "already_settled": True}

        # Calculate rewards with anti-double-mining.
        # When we share the caller's connection we must NOT open a separate one.
        if existing_conn is not None:
            rewards, telemetry = _calculate_anti_double_mining_rewards_conn(
                db, epoch, per_epoch_urtc, current_slot
            )
        else:
            rewards, telemetry = calculate_anti_double_mining_rewards(
                db_path, epoch, per_epoch_urtc, current_slot
            )

        if not rewards:
            if own_conn:
                db.rollback()
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

        # Mark epoch as settled
        db.execute(
            "INSERT OR REPLACE INTO epoch_state (epoch, settled, settled_ts) VALUES (?, 1, ?)",
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
    current_slot: int
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
    miner_groups = get_epoch_miner_groups(conn, epoch)

    # Select representative miner for each machine
    representative_map: Dict[str, str] = {}  # machine_identity -> representative_miner_id
    skipped_miners: Dict[str, str] = {}  # skipped_miner_id -> representative_miner_id

    for identity_hash, miner_ids in miner_groups.items():
        if len(miner_ids) > 1:
            rep = select_representative_miner(conn, miner_ids)
            representative_map[identity_hash] = rep
            for mid in miner_ids:
                if mid != rep:
                    skipped_miners[mid] = rep
        else:
            representative_map[identity_hash] = miner_ids[0]

    cursor = conn.cursor()
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
        if fingerprint_ok == 0:
            weight = 0.0
        else:
            weight = get_time_aged_multiplier(device_arch, chain_age_years)

        if weight > 0 and fingerprint_ok == 1:
            try:
                wart_row = cursor.execute(
                    "SELECT warthog_bonus FROM miner_attest_recent WHERE miner=?",
                    (miner_id,)
                ).fetchone()
                if wart_row and wart_row[0] and wart_row[0] > 1.0:
                    weight *= wart_row[0]
            except Exception:
                pass

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
    import os
    
    # Remove existing test DB
    if os.path.exists(db_path):
        os.remove(db_path)
    
    with sqlite3.connect(db_path) as conn:
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
        
        conn.commit()
    
    print(f"Test database created at {db_path}")
    return db_path


if __name__ == "__main__":
    import sys
    
    # Run tests
    test_db = "/tmp/test_anti_double_mining.db"
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
