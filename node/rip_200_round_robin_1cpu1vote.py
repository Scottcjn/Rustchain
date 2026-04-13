#!/usr/bin/env python3
"""
RIP-200: Round-Robin Consensus (1 CPU = 1 Vote)
================================================

Replaces VRF lottery with deterministic round-robin block producer selection.
Implements time-aging antiquity multipliers for rewards.

Key Changes:
1. Block production: Deterministic rotation (no lottery)
2. Rewards: Weighted by time-decaying antiquity multiplier
3. Anti-pool: Each CPU gets equal block production turns
4. Time-aging: Vintage hardware advantage decays over blockchain lifetime
5. RIP-309: Rotating 4-of-6 hardware fingerprint checks per epoch
"""

import hashlib
import logging
import random
import sqlite3
import time
from typing import List, Tuple, Dict, Optional

logger = logging.getLogger(__name__)

# Genesis timestamp (adjust to actual genesis block timestamp)
GENESIS_TIMESTAMP = 1764706927  # First actual block (Dec 2, 2025)
BLOCK_TIME = 600  # 10 minutes
ATTESTATION_TTL = 86400  # 24 hours - ancient hardware needs longer TTL

# The 6 hardware fingerprint checks used in attestation (RIP-309)
FP_CHECKS = [
    'clock_drift',
    'cache_timing',
    'simd_bias',
    'thermal_drift',
    'instruction_jitter',
    'anti_emulation',
]

# Number of checks that are ACTIVE per epoch (RIP-309 Phase 1)
FP_ACTIVE_COUNT = 4

# Antiquity base multipliers
ANTIQUITY_MULTIPLIERS = {
    "386": 3.0, "i386": 3.0, "386dx": 3.0, "386sx": 3.0,
    "486": 2.9, "i486": 2.9, "486dx": 2.9, "486dx2": 2.9, "486dx4": 2.8,
    "68000": 3.0, "mc68000": 3.0, "68010": 2.9, "68020": 2.7, "68030": 2.5,
    "68040": 2.4, "68060": 2.2,
    "mips_r2000": 3.0, "mips_r3000": 2.9, "mips_r4000": 2.7,
    "mips_r4400": 2.6, "mips_r5000": 2.5, "mips_r10000": 2.4, "mips_r12000": 2.3,
    "nes_6502": 2.8, "snes_65c816": 2.7, "n64_mips": 2.5, "gba_arm7": 2.3,
    "genesis_68000": 2.5, "sms_z80": 2.6, "saturn_sh2": 2.6,
    "gameboy_z80": 2.6, "gameboy_color_z80": 2.5, "ps1_mips": 2.8,
    "6502": 2.8, "65c02": 2.7, "65c816": 2.7, "z80": 2.6,
    "sh1": 2.7, "sh2": 2.6, "sh4": 2.3, "sh4a": 2.2,
    "dreamcast_sh4": 2.3, "ps2_ee": 2.2, "emotion_engine": 2.2,
    "gamecube_gekko": 2.1, "xbox_celeron": 1.8, "psp_allegrex": 2.0,
    "xbox360_xenon": 2.0, "xenon": 2.0, "ps3_cell": 2.2, "cell_be": 2.2,
    "wii_broadway": 2.0, "nds_arm7_arm9": 2.3,
    "itanium": 2.5, "itanium2": 2.3, "ia64": 2.5,
    "vax": 3.5, "vax_780": 3.5, "transputer": 3.5, "t800": 3.5, "t414": 3.5,
    "i860": 3.0, "i960": 3.0, "clipper": 3.5, "ns32k": 3.5,
    "88k": 3.0, "mc88100": 3.0, "am29k": 3.0, "romp": 3.5,
    "s390": 2.5, "s390x": 2.3,
    "sparc_v7": 2.9, "sparc_v8": 2.7, "sparc_v9": 2.5,
    "ultrasparc": 2.3, "ultrasparc_t1": 1.9, "ultrasparc_t2": 1.8,
    "riscv": 1.4, "riscv64": 1.4, "riscv32": 1.5,
    "alpha_21064": 2.7, "alpha_21164": 2.5, "alpha_21264": 2.3,
    "pa_risc_1_0": 2.9, "pa_risc_1_1": 2.7, "pa_risc_2_0": 2.3,
    "power1": 2.8, "power2": 2.6, "power3": 2.4, "power4": 2.2,
    "power5": 2.0, "power6": 1.9, "power7": 1.8, "power8": 1.5, "power9": 1.8,
    "pentium": 2.5, "pentium_mmx": 2.4, "pentium_pro": 2.3,
    "pentium_ii": 2.2, "pentium_iii": 2.0,
    "pentium4": 1.5, "pentium_d": 1.5,
    "k5": 2.4, "k6": 2.3, "k6_2": 2.2, "k6_3": 2.1,
    "cyrix_6x86": 2.5, "cyrix_mii": 2.3, "cyrix_mediagx": 2.2,
    "via_c3": 2.0, "via_c7": 1.8, "via_nano": 1.7,
    "transmeta_crusoe": 2.1, "transmeta_efficeon": 1.9,
    "winchip": 2.3, "winchip_c6": 2.3,
    "amigaone_g3": 2.2, "amigaone_g4": 2.1,
    "pegasos_g3": 2.2, "pegasos_g4": 2.1, "sam440": 2.0, "sam460": 1.9,
    "g3": 1.8, "powerpc g3": 1.8, "powerpc g3 (750)": 1.8,
    "g4": 2.5, "powerpc g4": 2.5, "powerpc g4 (74xx)": 2.5,
    "power macintosh": 2.5, "powerpc": 2.5,
    "g5": 2.0, "powerpc g5": 2.0, "powerpc g5 (970)": 2.0,
    "core2": 1.3, "core2duo": 1.3, "nehalem": 1.2, "westmere": 1.2,
    "sandy_bridge": 1.1, "sandybridge": 1.1,
    "ivy_bridge": 1.1, "ivybridge": 1.15,
    "haswell": 1.1, "broadwell": 1.05, "skylake": 1.05,
    "kaby_lake": 1.0, "coffee_lake": 1.0, "cascade_lake": 1.0,
    "comet_lake": 1.0, "rocket_lake": 1.0,
    "alder_lake": 1.0, "raptor_lake": 1.0, "arrow_lake": 1.0,
    "modern_intel": 0.8,
    "k7_athlon": 1.5, "k8_athlon64": 1.5, "k10_phenom": 1.4,
    "bulldozer": 1.3, "piledriver": 1.3, "steamroller": 1.2, "excavator": 1.2,
    "zen": 1.1, "zen_plus": 1.1, "zen2": 1.05, "zen3": 1.0,
    "zen4": 1.0, "zen5": 1.0, "modern_amd": 0.8,
    "apple_silicon": 0.8, "m1": 1.2, "m2": 1.15, "m3": 1.1, "m4": 1.05,
    "arm2": 4.0, "arm3": 3.8, "arm6": 3.5, "arm7": 3.0, "arm7tdmi": 3.0,
    "strongarm": 2.8, "sa1100": 2.7, "sa1110": 2.7, "xscale": 2.5,
    "arm9": 2.5, "arm926ej": 2.3, "arm11": 2.0, "arm1176": 2.0,
    "cortex_a8": 1.8, "cortex_a9": 1.5,
    "retro": 1.4, "modern": 0.8, "x86_64": 0.8,
    "aarch64": 0.0005, "arm": 0.0005, "armv7": 0.0005, "armv7l": 0.0005,
    "default": 0.8, "unknown": 0.8
}

DECAY_RATE_PER_YEAR = 0.15


# ---------------------------------------------------------------------------
# RIP-309: Rotating Fingerprint Checks
# ---------------------------------------------------------------------------

def get_prev_block_hash_for_epoch(db_path: str, epoch: int) -> Optional[str]:
    """Retrieve the block hash of the last block in the given epoch."""
    epoch_end_slot = epoch * 144 + 143
    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT block_hash FROM blocks WHERE slot = ?", (epoch_end_slot,)
            ).fetchone()
            if row:
                return row[0]
    except Exception as e:
        logger.warning(
            "Could not retrieve block hash for epoch %d (slot %d): %s",
            epoch, epoch_end_slot, e
        )
    return None


def derive_measurement_nonce(prev_block_hash: Optional[str], epoch: int) -> bytes:
    """
    RIP-309: Derive the measurement nonce for an epoch.

    nonce = SHA256(prev_block_hash || "measurement_nonce")

    If prev_block_hash is unavailable (e.g., genesis), falls back to
    epoch-number-only derivation (still deterministic but less unpredictable).
    """
    if prev_block_hash:
        data = prev_block_hash.encode() + b"measurement_nonce"
    else:
        data = f"epoch_{epoch}_fallback_nonce".encode()
    return hashlib.sha256(data).digest()


def get_active_fp_checks_for_epoch(
    prev_block_hash: Optional[str],
    epoch: int,
) -> Tuple[List[str], int]:
    """
    RIP-309 Phase 1: Select which 4 of 6 fingerprint checks are ACTIVE for
    the given epoch.

    Selection is deterministic (same block hash → same checks, auditable)
    and unpredictable (cannot determine without knowing block hash).
    All 6 checks still run and log; only the active 4 affect rewards.

    Returns: (active_check_names, seed)
    """
    nonce = derive_measurement_nonce(prev_block_hash, epoch)
    seed = int.from_bytes(nonce[:4], 'big')
    rng = random.Random(seed)
    active = rng.sample(FP_CHECKS, FP_ACTIVE_COUNT)

    inactive = [c for c in FP_CHECKS if c not in active]
    logger.info(
        "[RIP-309] Epoch %d | active=%s | inactive=%s | seed=%d",
        epoch, sorted(active), sorted(inactive), seed
    )
    return active, seed


def fp_passed_active_checks(
    fingerprint_data,
    active_checks: List[str],
) -> bool:
    """
    RIP-309: Evaluate whether a miner PASSED the active fingerprint checks.

    fingerprint_data may be:
    - A JSON string: {"checks": {"check_name": bool, ...}}
    - An integer 0/1 (legacy fingerprint_passed)
    - None

    A miner passes if ALL active checks returned true.
    Inactive checks are ignored (still run and log, but don't affect rewards).

    Falls back to legacy 0/1 field for backwards compatibility.
    """
    import json as _json

    if fingerprint_data is None:
        return True

    fp = None
    if isinstance(fingerprint_data, str):
        try:
            fp = _json.loads(fingerprint_data)
        except Exception:
            pass
    else:
        fp = fingerprint_data

    if isinstance(fp, dict) and "checks" in fp:
        checks = fp.get("checks", {})
        if isinstance(checks, dict):
            for check_name in active_checks:
                if check_name in checks and not checks[check_name]:
                    return False
            return True

    if isinstance(fp, dict):
        return bool(fp.get("fingerprint_passed", True))

    if isinstance(fingerprint_data, (int, float)):
        return bool(fingerprint_data)

    return True


# ---------------------------------------------------------------------------
# Time-Aged Multipliers
# ---------------------------------------------------------------------------

def get_chain_age_years(current_slot: int) -> float:
    chain_age_seconds = current_slot * BLOCK_TIME
    return chain_age_seconds / (365.25 * 24 * 3600)


def get_time_aged_multiplier(device_arch: str, chain_age_years: float) -> float:
    base = ANTIQUITY_MULTIPLIERS.get(device_arch.lower(), 1.0)
    if base <= 1.0:
        return 1.0
    vintage_bonus = base - 1.0
    aged_bonus = max(0, vintage_bonus * (1 - DECAY_RATE_PER_YEAR * chain_age_years))
    return 1.0 + aged_bonus


def get_attested_miners(db_path: str, current_ts: int) -> List[Tuple[str, str]]:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT miner, device_arch
            FROM miner_attest_recent
            WHERE ts_ok >= ?
            ORDER BY miner ASC
        """, (current_ts - ATTESTATION_TTL,))
        return cursor.fetchall()


def get_round_robin_producer(slot: int, attested_miners: List[Tuple[str, str]]) -> str:
    if not attested_miners:
        return None
    return attested_miners[slot % len(attested_miners)][0]


def check_eligibility_round_robin(
    db_path: str, miner_id: str, slot: int, current_ts: int
) -> Dict:
    attested_miners = get_attested_miners(db_path, current_ts)
    miner_ids = [m[0] for m in attested_miners]

    if miner_id not in miner_ids:
        return {"eligible": False, "reason": "not_attested",
                "slot_producer": None, "rotation_size": len(attested_miners)}

    designated = get_round_robin_producer(slot, attested_miners)

    if miner_id == designated:
        return {"eligible": True, "reason": "your_turn",
                "slot_producer": miner_id, "rotation_size": len(attested_miners)}

    idx = miner_ids.index(miner_id)
    cur_idx = slot % len(attested_miners)
    if idx >= cur_idx:
        wait = idx - cur_idx
    else:
        wait = len(attested_miners) - cur_idx + idx

    return {"eligible": False, "reason": "not_your_turn",
            "slot_producer": designated, "your_turn_at_slot": slot + wait,
            "rotation_size": len(attested_miners)}


def calculate_epoch_rewards_time_aged(
    db_path: str,
    epoch: int,
    total_reward_urtc: int,
    current_slot: int,
    prev_block_hash: Optional[str] = None,
) -> Dict[str, int]:
    """
    Calculate reward distribution for an epoch with time-aged multipliers
    and RIP-309 rotating fingerprint checks.

    RIP-309 Phase 1: Only 4 of 6 fingerprint checks count toward rewards
    each epoch. The active set is determined by a nonce derived from the
    previous epoch's last block hash (SHA256(block_hash || "measurement_nonce")).

    Args:
        db_path: Database path
        epoch: Epoch number to calculate rewards for
        total_reward_urtc: Total uRTC to distribute
        current_slot: Current blockchain slot (for age calculation)
        prev_block_hash: Hash of the last block in the previous epoch.
                        If None, looks up from blocks table or falls back
                        to epoch-number derivation (RIP-309 nonce computation).

    Returns:
        Dict of {miner_id: reward_urtc}
    """
    chain_age_years = get_chain_age_years(current_slot)

    epoch_start_slot = epoch * 144
    epoch_end_slot = epoch_start_slot + 143
    epoch_start_ts = GENESIS_TIMESTAMP + (epoch_start_slot * BLOCK_TIME)
    epoch_end_ts = GENESIS_TIMESTAMP + (epoch_end_slot * BLOCK_TIME)

    # RIP-309: Resolve block hash and determine active fingerprint checks
    if prev_block_hash is None:
        prev_block_hash = get_prev_block_hash_for_epoch(db_path, epoch - 1)

    active_fp_checks, fp_seed = get_active_fp_checks_for_epoch(prev_block_hash, epoch)

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT miner_pk FROM epoch_enroll WHERE epoch = ?", (epoch,)
        )
        enrolled = cursor.fetchall()

        if enrolled:
            epoch_miners = []
            for (miner_pk,) in enrolled:
                row = cursor.execute(
                    "SELECT device_arch, fingerprint "
                    "FROM miner_attest_recent WHERE miner = ? LIMIT 1",
                    (miner_pk,)
                ).fetchone()
                if row:
                    epoch_miners.append((miner_pk, row[0] or "unknown", row[1]))
                else:
                    epoch_miners.append((miner_pk, "unknown", None))
        else:
            logger.warning(
                "Epoch %d: no epoch_enroll rows, falling back to "
                "miner_attest_recent time-window query", epoch
            )
            cursor.execute("""
                SELECT DISTINCT miner, device_arch, fingerprint
                FROM miner_attest_recent
                WHERE ts_ok >= ? AND ts_ok <= ?
            """, (epoch_start_ts - ATTESTATION_TTL, epoch_end_ts))
            epoch_miners = cursor.fetchall()

    if not epoch_miners:
        return {}

    logger.info(
        "[RIP-309] Epoch %d reward calc | active_fp=%s | seed=%d | miners=%d",
        epoch, sorted(active_fp_checks), fp_seed, len(epoch_miners)
    )

    weighted_miners = []
    total_weight = 0.0

    for row in epoch_miners:
        miner_id, device_arch = row[0], row[1]
        fingerprint_data = row[2] if len(row) > 2 else None

        # RIP-309: Evaluate only the active fingerprint checks
        fingerprint_ok = fp_passed_active_checks(fingerprint_data, active_fp_checks)

        if not fingerprint_ok:
            weight = 0.0
            print(
                f"[REWARD] {miner_id[:20]}... RIP-309 fp=FAIL "
                f"(active={active_fp_checks}) -> weight=0"
            )
        else:
            weight = get_time_aged_multiplier(device_arch, chain_age_years)

        # Warthog dual-mining bonus
        if weight > 0 and fingerprint_ok:
            try:
                wart_row = cursor.execute(
                    "SELECT warthog_bonus FROM miner_attest_recent WHERE miner=?",
                    (miner_id,)
                ).fetchone()
                if wart_row and wart_row[0] and wart_row[0] > 1.0:
                    weight *= wart_row[0]
            except Exception:
                pass

        weighted_miners.append((miner_id, weight))
        total_weight += weight

    if total_weight <= 0:
        logger.warning(
            "Epoch %d: total_weight=0, no rewards distributed", epoch
        )
        return {}

    eligible = [(m, w) for m, w in weighted_miners if w > 0]
    rewards = {}
    remaining = total_reward_urtc

    for i, (miner_id, weight) in enumerate(eligible):
        if i == len(eligible) - 1:
            share = remaining
        else:
            share = int((weight / total_weight) * total_reward_urtc)
            remaining -= share
        rewards[miner_id] = share

    return rewards


if __name__ == "__main__":
    import json

    print("=== RIP-309 Fingerprint Check Rotation ===\n")
    for i, bh in enumerate(["abc123", "def456", "789abc"]):
        active, seed = get_active_fp_checks_for_epoch(bh, epoch=i + 1)
        print(f"Epoch {i+1} | bh={bh} | seed={seed} | active={sorted(active)}")

    print("\n=== Time-Aged Multiplier Demo ===\n")
    for years in [0, 2, 5, 10, 15, 17]:
        g4 = get_time_aged_multiplier("g4", years)
        g5 = get_time_aged_multiplier("g5", years)
        modern = get_time_aged_multiplier("modern", years)
        print(f"Age {years}y | G4={g4:.3f}x | G5={g5:.3f}x | Modern={modern:.3f}x")

    print("\n=== RIP-309 Per-Check Fingerprint Test ===\n")
    fp_all_pass = {"checks": {c: True for c in FP_CHECKS}}
    fp_one_fail = {"checks": {c: True for c in FP_CHECKS}}
    fp_one_fail["checks"]["cache_timing"] = False
    fp_inactive_fail = {"checks": {c: True for c in FP_CHECKS}}
    fp_inactive_fail["checks"]["anti_emulation"] = False  # inactive if selected

    active, _ = get_active_fp_checks_for_epoch("test_hash", epoch=1)
    print(f"Active checks: {sorted(active)}")
    for label, fp in [
        ("all pass", fp_all_pass),
        ("one fail (inactive check)", fp_one_fail),
        ("inactive check fail", fp_inactive_fail),
        ("legacy pass", True),
        ("legacy fail", False),
    ]:
        result = fp_passed_active_checks(fp, active)
        print(f"  {label}: {'PASS' if result else 'FAIL'}")
