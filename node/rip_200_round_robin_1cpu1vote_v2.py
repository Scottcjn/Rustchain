#!/usr/bin/env python3
"""
RIP-200 v2: Round-Robin Consensus (1 CPU = 1 Vote)
==================================================

Updated Antiquity Multiplier System:
- PowerPC: High multipliers (2.0-2.5x) - true vintage
- Intel Mac (2006-2019): Sliding scale based on age (1.0-1.5x)
- Server x86 (5+ years): Medium multiplier (0.5-1.0x)
- Modern x86 (<5 years): Starts at 0.1x, earns 15%/year loyalty bonus
- Apple Silicon: 1.2x (modern but premium hardware)
"""

import sqlite3
import time
from typing import List, Tuple, Dict
from datetime import datetime

# Genesis timestamp
GENESIS_TIMESTAMP = 1728000000  # Oct 4, 2024 00:00:00 UTC
BLOCK_TIME = 600  # 10 minutes
ATTESTATION_TTL = 600  # 10 minutes
CURRENT_YEAR = 2025

# =============================================================================
# ANTIQUITY MULTIPLIER SYSTEM v2
# =============================================================================

# Base multipliers by architecture class
BASE_MULTIPLIERS = {
    # PowerPC - True Vintage (pre-2006)
    "g4": 2.5,           # PowerPC G4 (2001-2005) - Most valuable
    "g5": 2.0,           # PowerPC G5 (2003-2006) - High value

    # Apple Silicon - Modern Premium
    "apple_silicon": 1.2,  # M1/M2/M3 (2020+) - Premium but modern
    "m1": 1.2,
    "m2": 1.2,
    "m3": 1.2,

    # Placeholders - calculated dynamically
    "intel_mac": None,     # Calculated based on model year
    "server_x86": None,    # Calculated based on age
    "modern_x86": 0.1,     # Base rate, can earn loyalty bonus
}

# Intel Mac model years (for sliding scale)
INTEL_MAC_MODELS = {
    "MacPro1,1": 2006,
    "MacPro2,1": 2007,
    "MacPro3,1": 2008,
    "MacPro4,1": 2009,
    "MacPro5,1": 2010,
    "MacPro6,1": 2013,    # Trash can Mac Pro
    "MacPro7,1": 2019,    # Cheese grater Mac Pro
    "iMacPro1,1": 2017,
    "Macmini6,1": 2012,
    "Macmini6,2": 2012,
    "Macmini7,1": 2014,
    "MacBookPro11,1": 2013,
    "MacBookPro11,2": 2013,
    "MacBookPro11,3": 2013,
    "MacBookPro12,1": 2015,
    "MacBookPro13,1": 2016,
    "MacBookPro14,1": 2017,
    "MacBookPro15,1": 2018,
    "MacBookPro16,1": 2019,
}

# Time decay parameters
DECAY_RATE_PER_YEAR = 0.15  # 15% decay per year for vintage bonus
LOYALTY_RATE_PER_YEAR = 0.15  # 15% bonus per year for modern x86 uptime


def get_intel_mac_multiplier(model_identifier: str, manufacture_year: int = None) -> float:
    """
    Calculate multiplier for Intel Macs based on age

    Sliding scale:
    - 15+ years old: 1.5x (2006-2010 Mac Pros)
    - 12-14 years old: 1.3x (2011-2013 Mac Pros)
    - 8-11 years old: 1.1x (2014-2017)
    - 5-7 years old: 1.0x (2018-2020)
    - <5 years old: 0.8x (2021+, unlikely for Intel)
    """
    # Try to get year from model identifier
    if manufacture_year is None:
        manufacture_year = INTEL_MAC_MODELS.get(model_identifier, CURRENT_YEAR - 5)

    age = CURRENT_YEAR - manufacture_year

    if age >= 15:
        return 1.5  # True vintage Intel (2006-2010)
    elif age >= 12:
        return 1.3  # Classic Intel (2011-2013)
    elif age >= 8:
        return 1.1  # Aging Intel (2014-2017)
    elif age >= 5:
        return 1.0  # Recent Intel (2018-2020)
    else:
        return 0.8  # Very recent Intel


def get_server_x86_multiplier(manufacture_year: int) -> float:
    """
    Calculate multiplier for server/workstation x86 based on age

    Sliding scale:
    - 10+ years old: 1.0x (pre-2015)
    - 8-9 years old: 0.7x (2016-2017)
    - 6-7 years old: 0.5x (2018-2019)
    - 5 years old: 0.3x (2020)
    - <5 years old: 0.1x (2021+) - modern baseline
    """
    age = CURRENT_YEAR - manufacture_year

    if age >= 10:
        return 1.0  # Vintage server
    elif age >= 8:
        return 0.7  # Aging server (like 2017 PowerEdge)
    elif age >= 6:
        return 0.5  # Middle-aged server
    elif age >= 5:
        return 0.3  # Recent server
    else:
        return 0.1  # Modern server


def get_loyalty_bonus(miner_id: str, db_path: str, base_multiplier: float) -> float:
    """
    Calculate loyalty bonus for modern x86 miners

    Modern x86 (<5 years) starts at 0.1x but earns 15% per year
    for consistent uptime (measured by attestation history)

    Max bonus caps at 1.0x total (10 years of perfect uptime)
    """
    if base_multiplier > 0.1:
        return 0.0  # Only modern x86 gets loyalty bonus

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Get first attestation timestamp for this miner
            cursor.execute("""
                SELECT MIN(ts_ok) FROM miner_attest_history
                WHERE miner = ?
            """, (miner_id,))

            result = cursor.fetchone()
            if not result or not result[0]:
                return 0.0

            first_attest = result[0]

            # Calculate years of uptime
            now = int(time.time())
            years_online = (now - first_attest) / (365.25 * 24 * 3600)

            # 15% bonus per year, capped at 0.9 additional (total max 1.0)
            loyalty_bonus = min(years_online * LOYALTY_RATE_PER_YEAR, 0.9)

            return loyalty_bonus

    except Exception:
        return 0.0


def get_device_multiplier(device_info: Dict, db_path: str = None, miner_id: str = None) -> float:
    """
    Master function to calculate multiplier for any device

    device_info should contain:
    - arch: Architecture key (g4, g5, apple_silicon, intel_mac, server_x86, modern_x86)
    - model: Model identifier (optional, for Intel Macs)
    - year: Manufacture year (optional)
    - family: Family name (optional, for display)
    """
    arch = device_info.get("arch", "modern_x86").lower()
    model = device_info.get("model", "")
    year = device_info.get("year", CURRENT_YEAR)

    # PowerPC - Fixed high multipliers
    if arch in ["g4", "ppc_g4", "powerpc_g4"]:
        return 2.5
    elif arch in ["g5", "ppc_g5", "powerpc_g5"]:
        return 2.0

    # Apple Silicon - Fixed premium multiplier
    elif arch in ["apple_silicon", "m1", "m2", "m3", "arm64_apple"]:
        return 1.2

    # Intel Mac - Sliding scale based on age
    elif arch in ["intel_mac", "x86_64_mac", "mac_intel"]:
        return get_intel_mac_multiplier(model, year)

    # Server/Workstation x86 - Sliding scale based on age
    elif arch in ["server_x86", "workstation_x86", "xeon", "epyc"]:
        return get_server_x86_multiplier(year)

    # Modern x86 - Base 0.1x + loyalty bonus
    else:
        base = 0.1
        loyalty = 0.0
        if db_path and miner_id:
            loyalty = get_loyalty_bonus(miner_id, db_path, base)
        return base + loyalty


def get_time_aged_multiplier(device_arch: str, chain_age_years: float, device_info: Dict = None) -> float:
    """
    Calculate time-aged antiquity multiplier with decay

    Vintage hardware bonus decays linearly over blockchain lifetime:
    - Year 0: Full multiplier
    - Year 10: Significantly reduced
    - Year 16.67: Vintage bonus fully decayed to modern baseline

    Modern x86 with loyalty bonus does NOT decay (reward for commitment)
    """
    if device_info:
        base_multiplier = get_device_multiplier(device_info)
    else:
        # Fallback to simple lookup
        base_multiplier = BASE_MULTIPLIERS.get(device_arch.lower(), 0.1)

    # Modern x86 doesn't decay (loyalty bonus is earned, not given)
    if base_multiplier <= 0.1:
        return base_multiplier

    # Apple Silicon gets slight decay (it's modern hardware)
    if device_arch.lower() in ["apple_silicon", "m1", "m2", "m3", "arm64_apple"]:
        decay_rate = 0.05  # 5% per year (slower decay for premium)
    else:
        decay_rate = DECAY_RATE_PER_YEAR

    # Calculate decayed bonus
    if base_multiplier <= 1.0:
        return base_multiplier  # No bonus to decay

    vintage_bonus = base_multiplier - 1.0
    aged_bonus = max(0, vintage_bonus * (1 - decay_rate * chain_age_years))

    return 1.0 + aged_bonus


# =============================================================================
# ROUND-ROBIN CONSENSUS FUNCTIONS
# =============================================================================

def get_chain_age_years(current_slot: int) -> float:
    """Calculate blockchain age in years from slot number"""
    chain_age_seconds = current_slot * BLOCK_TIME
    return chain_age_seconds / (365.25 * 24 * 3600)


def get_attested_miners(db_path: str, current_ts: int) -> List[Tuple[str, str, Dict]]:
    """
    Get all currently attested miners (within TTL window)

    Returns: List of (miner_id, device_arch, device_info) tuples, sorted alphabetically
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT miner, device_arch, device_family, device_model, device_year
            FROM miner_attest_recent
            WHERE ts_ok >= ?
            ORDER BY miner ASC
        """, (current_ts - ATTESTATION_TTL,))

        results = []
        for row in cursor.fetchall():
            miner_id, arch, family, model, year = row
            device_info = {
                "arch": arch or "modern_x86",
                "family": family or "",
                "model": model or "",
                "year": year or CURRENT_YEAR
            }
            results.append((miner_id, arch, device_info))

        return results


def get_round_robin_producer(slot: int, attested_miners: List) -> str:
    """Deterministic round-robin block producer selection"""
    if not attested_miners:
        return None
    producer_index = slot % len(attested_miners)
    return attested_miners[producer_index][0]


def calculate_epoch_rewards_v2(
    db_path: str,
    epoch: int,
    total_reward_urtc: int,
    current_slot: int
) -> Dict[str, int]:
    """
    Calculate reward distribution with v2 multiplier system
    """
    chain_age_years = get_chain_age_years(current_slot)

    epoch_start_slot = epoch * 144
    epoch_end_slot = epoch_start_slot + 143
    epoch_start_ts = GENESIS_TIMESTAMP + (epoch_start_slot * BLOCK_TIME)
    epoch_end_ts = GENESIS_TIMESTAMP + (epoch_end_slot * BLOCK_TIME)

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DISTINCT miner, device_arch, device_family, device_model, device_year
            FROM miner_attest_recent
            WHERE ts_ok >= ? AND ts_ok <= ?
        """, (epoch_start_ts - ATTESTATION_TTL, epoch_end_ts))

        epoch_miners = cursor.fetchall()

    if not epoch_miners:
        return {}

    # Calculate weights with v2 system
    weighted_miners = []
    total_weight = 0.0

    for row in epoch_miners:
        miner_id, arch, family, model, year = row
        device_info = {
            "arch": arch or "modern_x86",
            "family": family or "",
            "model": model or "",
            "year": year or CURRENT_YEAR
        }

        base_mult = get_device_multiplier(device_info, db_path, miner_id)
        weight = get_time_aged_multiplier(arch, chain_age_years, device_info)

        weighted_miners.append((miner_id, weight, device_info))
        total_weight += weight

    # Distribute rewards
    rewards = {}
    remaining = total_reward_urtc

    for i, (miner_id, weight, device_info) in enumerate(weighted_miners):
        if i == len(weighted_miners) - 1:
            share = remaining
        else:
            share = int((weight / total_weight) * total_reward_urtc)
            remaining -= share

        rewards[miner_id] = share

    return rewards


# =============================================================================
# EXAMPLE / TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("RustChain Antiquity Multiplier System v2")
    print("=" * 70)

    # Test devices
    test_devices = [
        {"arch": "g4", "family": "PowerPC G4", "year": 2003},
        {"arch": "g5", "family": "PowerPC G5", "year": 2005},
        {"arch": "intel_mac", "model": "MacPro6,1", "year": 2013},  # 12 years old
        {"arch": "server_x86", "family": "Dell PowerEdge", "year": 2017},  # 8 years old
        {"arch": "apple_silicon", "family": "Apple M2", "year": 2022},
        {"arch": "modern_x86", "family": "Modern Desktop", "year": 2023},
    ]

    print("\n=== Base Multipliers (Year 0) ===")
    print(f"{'Device':<30} {'Age':>8} {'Multiplier':>12}")
    print("-" * 52)

    for device in test_devices:
        mult = get_device_multiplier(device)
        age = CURRENT_YEAR - device.get("year", CURRENT_YEAR)
        name = device.get("family", device.get("arch"))
        print(f"{name:<30} {age:>5} yr {mult:>10.2f}x")

    print("\n=== Multiplier Decay Over Blockchain Lifetime ===")
    for years in [0, 2, 5, 10, 15]:
        print(f"\n--- Chain Age: {years} years ---")
        for device in test_devices:
            arch = device.get("arch")
            mult = get_time_aged_multiplier(arch, years, device)
            name = device.get("family", device.get("arch"))[:25]
            print(f"  {name:<25}: {mult:.3f}x")

    print("\n=== Reward Distribution Example (1.5 RTC) ===")
    total_reward = 150_000_000  # 1.5 RTC in uRTC

    weights = []
    for device in test_devices:
        mult = get_device_multiplier(device)
        weights.append((device.get("family", device.get("arch")), mult))

    total_weight = sum(w[1] for w in weights)

    print(f"{'Device':<30} {'Multiplier':>10} {'Share (RTC)':>12} {'Percent':>8}")
    print("-" * 62)

    for name, mult in weights:
        share_urtc = int((mult / total_weight) * total_reward)
        share_rtc = share_urtc / 100_000_000
        pct = (mult / total_weight) * 100
        print(f"{name:<30} {mult:>8.2f}x {share_rtc:>10.6f} {pct:>7.1f}%")

    print("\n" + "=" * 70)
    print("Key Points:")
    print("- PowerPC G4/G5: Highest multipliers (true vintage)")
    print("- Intel Mac: Sliding scale 0.8-1.5x based on age")
    print("- Server x86: Sliding scale 0.1-1.0x based on age")
    print("- Modern x86: 0.1x base + 15%/year loyalty bonus")
    print("- Vintage bonuses decay 15%/year over chain lifetime")
    print("- Loyalty bonuses do NOT decay (reward for commitment)")
    print("=" * 70)
