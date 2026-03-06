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
"""

import sqlite3
import time
from typing import List, Tuple, Dict

# Genesis timestamp (adjust to actual genesis block timestamp)
GENESIS_TIMESTAMP = 1764706927  # First actual block (Dec 2, 2025)
BLOCK_TIME = 600  # 10 minutes
ATTESTATION_TTL = 86400  # 24 hours - ancient hardware needs longer TTL  # 10 minutes

# Antiquity base multipliers
ANTIQUITY_MULTIPLIERS = {
    # PowerPC G4 variants
    "g4": 2.5,
    "powerpc g4": 2.5,
    "powerpc g4 (74xx)": 2.5,
    "power macintosh": 2.5,  # Assume G4 for Power Mac
    "powerpc": 2.5,          # Generic PowerPC -> G4
    
    # PowerPC G5 variants
    "g5": 2.0,
    "powerpc g5": 2.0,
    "powerpc g5 (970)": 2.0,
    
    # PowerPC G3
    "g3": 1.8,
    "powerpc g3": 1.8,
    "powerpc g3 (750)": 1.8,
    
    # Vintage x86
    "pentium4": 1.5,
    "pentium": 1.5,
    "retro": 1.4,            # Generic retro x86
    "core2duo": 1.3,
    "core2": 1.3,
    "nehalem": 1.2,
    "sandybridge": 1.1,
    
    # Apple Silicon
    "apple_silicon": 0.8,
    "m1": 1.2,
    "m2": 1.15,
    "m3": 1.1,
    
    # Modern (no bonus)
    "modern": 1.0,
    "x86_64": 1.0,
    "aarch64": 0.0005,
    "arm": 0.0005,
    "armv7": 0.0005,
    "armv7l": 0.0005,
    "default": 1.0,
    "unknown": 1.0
}

# Time decay parameters
DECAY_RATE_PER_YEAR = 0.15  # 15% decay per year (vintage bonus → 0 after ~16.67 years)


def get_chain_age_years(current_slot: int) -> float:
    """Calculate blockchain age in years from slot number"""
    chain_age_seconds = current_slot * BLOCK_TIME
    return chain_age_seconds / (365.25 * 24 * 3600)


def get_time_aged_multiplier(device_arch: str, chain_age_years: float) -> float:
    """
    Calculate time-aged antiquity multiplier

    Vintage hardware bonus decays linearly over time:
    - Year 0: Full multiplier (e.g., G4 = 2.5x)
    - Year 10: Equal to modern (1.0x)
    - Year 16.67: Vintage bonus fully decayed (0 additional reward)

    Modern hardware always stays at 1.0x (becomes optimal over time)
    """
    base_multiplier = ANTIQUITY_MULTIPLIERS.get(device_arch.lower(), 1.0)

    # Modern hardware doesn't decay (stays 1.0)
    if base_multiplier <= 1.0:
        return 1.0

    # Calculate decayed bonus
    vintage_bonus = base_multiplier - 1.0  # e.g., G4: 2.5 - 1.0 = 1.5
    aged_bonus = max(0, vintage_bonus * (1 - DECAY_RATE_PER_YEAR * chain_age_years))

    return 1.0 + aged_bonus


def get_attested_miners(db_path: str, current_ts: int) -> List[Tuple[str, str]]:
    """
    Get all currently attested miners (within TTL window)

    Returns: List of (miner_id, device_arch) tuples, sorted alphabetically
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Get miners with valid attestation (within TTL)
        cursor.execute("""
            SELECT miner, device_arch
            FROM miner_attest_recent
            WHERE ts_ok >= ?
            ORDER BY miner ASC
        """, (current_ts - ATTESTATION_TTL,))

        return cursor.fetchall()


def get_round_robin_producer(slot: int, attested_miners: List[Tuple[str, str]]) -> str:
    """
    Deterministic round-robin block producer selection

    Each attested CPU gets exactly 1 turn per rotation cycle.
    No lottery, no probabilistic selection - pure 1 CPU = 1 vote.

    Args:
        slot: Current blockchain slot number
        attested_miners: List of (miner_id, device_arch) tuples

    Returns:
        miner_id of the designated block producer for this slot
    """
    if not attested_miners:
        return None  # No attested miners

    # Deterministic rotation: slot modulo number of miners
    producer_index = slot % len(attested_miners)
    return attested_miners[producer_index][0]


def check_eligibility_round_robin(
    db_path: str,
    miner_id: str,
    slot: int,
    current_ts: int
) -> Dict:
    """
    Check if a specific miner is the designated block producer for this slot

    Returns:
        {
            "eligible": True/False,
            "reason": "your_turn" | "not_your_turn" | "not_attested",
            "slot_producer": miner_id of designated producer,
            "your_turn_at_slot": next slot when this miner can produce,
            "rotation_size": total number of attested miners
        }
    """
    attested_miners = get_attested_miners(db_path, current_ts)

    # Check if miner is attested
    miner_ids = [m[0] for m in attested_miners]
    if miner_id not in miner_ids:
        return {
            "eligible": False,
            "reason": "not_attested",
            "slot_producer": None,
            "rotation_size": len(attested_miners)
        }

    # Get designated producer for this slot
    designated_producer = get_round_robin_producer(slot, attested_miners)

    if miner_id == designated_producer:
        return {
            "eligible": True,
            "reason": "your_turn",
            "slot_producer": miner_id,
            "rotation_size": len(attested_miners)
        }

    # Calculate when this miner's next turn is
    miner_index = miner_ids.index(miner_id)
    current_index = slot % len(attested_miners)

    if miner_index >= current_index:
        slots_until_turn = miner_index - current_index
    else:
        slots_until_turn = len(attested_miners) - current_index + miner_index

    next_turn_slot = slot + slots_until_turn

    return {
        "eligible": False,
        "reason": "not_your_turn",
        "slot_producer": designated_producer,
        "your_turn_at_slot": next_turn_slot,
        "rotation_size": len(attested_miners)
    }


def calculate_epoch_rewards_time_aged(
    db_path: str,
    epoch: int,
    total_reward_urtc: int,
    current_slot: int
) -> Dict[str, int]:
    """
    Calculate reward distribution for an epoch with time-aged multipliers

    Each attested CPU gets rewards weighted by their time-aged antiquity multiplier.
    More miners = smaller individual rewards (anti-pool design).

    Args:
        db_path: Database path
        epoch: Epoch number to calculate rewards for
        total_reward_urtc: Total uRTC to distribute
        current_slot: Current blockchain slot (for age calculation)

    Returns:
        Dict of {miner_id: reward_urtc}
    """
    chain_age_years = get_chain_age_years(current_slot)

    # Get all miners who were attested during this epoch
    epoch_start_slot = epoch * 144
    epoch_end_slot = epoch_start_slot + 143
    epoch_start_ts = GENESIS_TIMESTAMP + (epoch_start_slot * BLOCK_TIME)
    epoch_end_ts = GENESIS_TIMESTAMP + (epoch_end_slot * BLOCK_TIME)

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Get unique attested miners during epoch (any attestation in epoch window)
        cursor.execute("""
            SELECT DISTINCT miner, device_arch
            FROM miner_attest_recent
            WHERE ts_ok >= ? AND ts_ok <= ?
        """, (epoch_start_ts - ATTESTATION_TTL, epoch_end_ts))

        epoch_miners = cursor.fetchall()

    if not epoch_miners:
        return {}

    # Calculate time-aged weights
    weighted_miners = []
    total_weight = 0.0

    for miner_id, device_arch in epoch_miners:
        weight = get_time_aged_multiplier(device_arch, chain_age_years)
        weighted_miners.append((miner_id, weight))
        total_weight += weight

    # Distribute rewards proportionally by weight
    rewards = {}
    remaining = total_reward_urtc

    for i, (miner_id, weight) in enumerate(weighted_miners):
        if i == len(weighted_miners) - 1:
            # Last miner gets remainder (prevents rounding issues)
            share = remaining
        else:
            share = int((weight / total_weight) * total_reward_urtc)
            remaining -= share

        rewards[miner_id] = share

    return rewards


# Example usage and testing
if __name__ == "__main__":
    # Simulate chain aging
    for years in [0, 2, 5, 10, 15, 17]:
        print(f"\n=== Chain Age: {years} years ===")
        g4_mult = get_time_aged_multiplier("g4", years)
        g5_mult = get_time_aged_multiplier("g5", years)
        modern_mult = get_time_aged_multiplier("modern", years)

        print(f"G4 multiplier: {g4_mult:.3f}x")
        print(f"G5 multiplier: {g5_mult:.3f}x")
        print(f"Modern multiplier: {modern_mult:.3f}x")

        # Example reward distribution
        total_reward = 150_000_000  # 1.5 RTC in uRTC
        total_weight = g4_mult + g5_mult + modern_mult

        g4_share = (g4_mult / total_weight) * total_reward
        g5_share = (g5_mult / total_weight) * total_reward
        modern_share = (modern_mult / total_weight) * total_reward

        print(f"\nReward distribution (1.5 RTC total):")
        print(f"  G4: {g4_share / 100_000_000:.6f} RTC ({g4_share/total_reward*100:.1f}%)")
        print(f"  G5: {g5_share / 100_000_000:.6f} RTC ({g5_share/total_reward*100:.1f}%)")
        print(f"  Modern: {modern_share / 100_000_000:.6f} RTC ({modern_share/total_reward*100:.1f}%)")
