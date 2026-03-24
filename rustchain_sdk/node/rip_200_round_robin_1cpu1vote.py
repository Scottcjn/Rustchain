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
    # ===========================================
    # ULTRA-VINTAGE (1979-1995) - 3.0x to 2.5x
    # ===========================================
    
    # Intel 386 (1985) - First 32-bit x86
    "386": 3.0,
    "i386": 3.0,
    "386dx": 3.0,
    "386sx": 3.0,
    
    # Intel 486 (1989)
    "486": 2.9,
    "i486": 2.9,
    "486dx": 2.9,
    "486dx2": 2.9,
    "486dx4": 2.8,
    
    # Motorola 68000 (1979) - Original Mac/Amiga
    "68000": 3.0,
    "mc68000": 3.0,
    "68010": 2.9,
    "68020": 2.7,
    "68030": 2.5,
    "68040": 2.4,
    "68060": 2.2,
    
    # MIPS (1985) - First commercial RISC
    "mips_r2000": 3.0,
    "mips_r3000": 2.9,
    "mips_r4000": 2.7,
    "mips_r4400": 2.6,
    "mips_r5000": 2.5,
    "mips_r10000": 2.4,
    "mips_r12000": 2.3,
    
    # ===========================================
    # RETRO GAME CONSOLES (1983-2001) - 2.3x to 2.8x
    # RIP-304: Pico serial-to-controller bridge
    # ===========================================

    # Nintendo
    "nes_6502": 2.8,          # NES/Famicom - Ricoh 2A03 (6502 derivative, 1983)
    "snes_65c816": 2.7,       # SNES/Super Famicom - Ricoh 5A22 (65C816, 1990)
    "n64_mips": 2.5,          # Nintendo 64 - NEC VR4300 (MIPS R4300i, 1996)
    "gba_arm7": 2.3,          # Game Boy Advance - ARM7TDMI (2001)

    # Sega
    "genesis_68000": 2.5,     # Sega Genesis/Mega Drive - Motorola 68000 (1988)
    "sms_z80": 2.6,           # Sega Master System - Zilog Z80 (1986)
    "saturn_sh2": 2.6,        # Sega Saturn - Hitachi SH-2 dual (1994)

    # Nintendo Handheld
    "gameboy_z80": 2.6,       # Game Boy - Sharp LR35902 (Z80 derivative, 1989)
    "gameboy_color_z80": 2.5, # Game Boy Color - Sharp LR35902 @ 8MHz (1998)

    # Sony
    "ps1_mips": 2.8,          # PlayStation 1 - MIPS R3000A (1994)

    # Generic CPU families used across consoles and computers
    "6502": 2.8,              # MOS 6502 (Apple II, Commodore 64, NES, Atari)
    "65c02": 2.7,             # WDC 65C02 (Apple IIe enhanced, BBC Master)
    "65c816": 2.7,            # WDC 65C816 (SNES, Apple IIGS)
    "z80": 2.6,               # Zilog Z80 (Game Boy, SMS, MSX, Spectrum)
    "sh1": 2.7,               # Hitachi SH-1 (1992) - early embedded
    "sh2": 2.6,               # Hitachi SH-2 (Sega Saturn, 32X)
    "sh4": 2.3,               # Hitachi SH-4 (Dreamcast, 1998) - 200MHz superscalar
    "sh4a": 2.2,              # Renesas SH-4A (2003)

    # ===========================================
    # GAME CONSOLE CPUs — specific silicon (2000-2006)
    # ===========================================

    "dreamcast_sh4": 2.3,     # Sega Dreamcast - Hitachi SH-4 @ 200MHz (1998)
    "ps2_ee": 2.2,            # PS2 Emotion Engine - Custom MIPS R5900 + VU0/VU1 (2000)
    "emotion_engine": 2.2,    # PS2 alias
    "gamecube_gekko": 2.1,    # GameCube - IBM Gekko (PowerPC 750CXe, 2001)
    "xbox_celeron": 1.8,      # Xbox OG - Custom Pentium III / Celeron (2001)
    "psp_allegrex": 2.0,      # PSP - Allegrex (MIPS R4000, 2004)
    "xbox360_xenon": 2.0,     # Xbox 360 - Xenon tri-core PowerPC (2005)
    "xenon": 2.0,             # Xbox 360 alias
    "ps3_cell": 2.2,          # PS3 - Cell Broadband Engine (PPE + 7 SPE, 2006)
    "cell_be": 2.2,           # Cell BE alias — legendary parallel arch
    "wii_broadway": 2.0,      # Wii - IBM Broadway (PowerPC 750CL, 2006)
    "nds_arm7_arm9": 2.3,     # Nintendo DS - ARM7TDMI + ARM946E dual (2004)

    # ===========================================
    # EXOTIC/DEAD ARCHITECTURES — unicorn tier
    # ===========================================

    "itanium": 2.5,           # Intel IA-64 Itanium (2001) — dead arch, extremely rare
    "itanium2": 2.3,          # Itanium 2 / Montecito / Poulson
    "ia64": 2.5,              # IA-64 alias
    "vax": 3.5,               # DEC VAX (1977) — minicomputer legend, if you have one...
    "vax_780": 3.5,           # VAX-11/780 — the original MIPS benchmark machine
    "transputer": 3.5,        # Inmos Transputer (1984) — parallel computing pioneer
    "t800": 3.5,              # Transputer T800 (with FPU)
    "t414": 3.5,              # Transputer T414
    "i860": 3.0,              # Intel i860 (1989) — failed "Cray on a chip"
    "i960": 3.0,              # Intel i960 (1988) — embedded RISC, military/aerospace
    "clipper": 3.5,           # Fairchild Clipper (1986) — workstation RISC, ultra-rare
    "ns32k": 3.5,             # National Semiconductor NS32032 (1984) — failed x86 killer
    "88k": 3.0,               # Motorola 88000 (1988) — killed by PowerPC alliance
    "mc88100": 3.0,           # 88100 alias
    "am29k": 3.0,             # AMD 29000 (1987) — AMD's RISC attempt, laser printers
    "romp": 3.5,              # IBM ROMP (1986) — first commercial RISC, RT PC
    "s390": 2.5,              # IBM System/390 mainframe
    "s390x": 2.3,             # 64-bit z/Architecture

    # Sun SPARC (1987)
    "sparc_v7": 2.9,
    "sparc_v8": 2.7,
    "sparc_v9": 2.5,
    "ultrasparc": 2.3,
    "ultrasparc_t1": 1.9,
    "ultrasparc_t2": 1.8,
    
    # RISC-V (2010+) — open ISA, exotic but modern
    "riscv": 1.4,             # Generic RISC-V boards (SiFive, StarFive, etc.)
    "riscv64": 1.4,
    "riscv32": 1.5,           # 32-bit even rarer

    # DEC Alpha (1992) - Fastest 1990s CPU
    "alpha_21064": 2.7,
    "alpha_21164": 2.5,
    "alpha_21264": 2.3,
    
    # HP PA-RISC (1986)
    "pa_risc_1_0": 2.9,
    "pa_risc_1_1": 2.7,
    "pa_risc_2_0": 2.3,
    
    # IBM POWER (1990)
    "power1": 2.8,
    "power2": 2.6,
    "power3": 2.4,
    "power4": 2.2,
    "power5": 2.0,
    "power6": 1.9,
    "power7": 1.8,
    "power8": 1.5,
    "power9": 1.8,
    
    # ===========================================
    # VINTAGE x86 (1993-2003) - 2.5x to 2.0x
    # ===========================================
    
    # Intel Pentium (1993)
    "pentium": 2.5,
    "pentium_mmx": 2.4,
    "pentium_pro": 2.3,
    "pentium_ii": 2.2,
    "pentium_iii": 2.0,
    
    # Intel Pentium 4 (2000-2006)
    "pentium4": 1.5,
    "pentium_d": 1.5,
    
    # AMD K5/K6 (1996-2000)
    "k5": 2.4,
    "k6": 2.3,
    "k6_2": 2.2,
    "k6_3": 2.1,
    
    # ===========================================
    # ODDBALL x86 (1995-2010) - 2.5x to 1.7x
    # ===========================================
    
    # Cyrix (1995-1999)
    "cyrix_6x86": 2.5,
    "cyrix_mii": 2.3,
    "cyrix_mediagx": 2.2,
    
    # VIA (2001-2010)
    "via_c3": 2.0,
    "via_c7": 1.8,
    "via_nano": 1.7,
    
    # Transmeta (2000-2005)
    "transmeta_crusoe": 2.1,
    "transmeta_efficeon": 1.9,
    
    # IDT WinChip (1997-1999)
    "winchip": 2.3,
    "winchip_c6": 2.3,
    
    # ===========================================
    # POWERPC AMIGA (1999-2012) - 2.4x to 1.9x
    # ===========================================
    
    "amigaone_g3": 2.2,
    "amigaone_g4": 2.1,
    "pegasos_g3": 2.2,
    "pegasos_g4": 2.1,
    "sam440": 2.0,
    "sam460": 1.9,
    
    # ===========================================
    # POWERPC MAC (1994-2006) - 2.5x to 1.8x
    # ===========================================
    
    "g3": 1.8,
    "powerpc g3": 1.8,
    "powerpc g3 (750)": 1.8,
    "g4": 2.5,
    "powerpc g4": 2.5,
    "powerpc g4 (74xx)": 2.5,
    "power macintosh": 2.5,
    "powerpc": 2.5,
    "g5": 2.0,
    "powerpc g5": 2.0,
    "powerpc g5 (970)": 2.0,
    
    # ===========================================
    # MODERN INTEL (2006-2025) - 1.3x to 1.0x
    # ===========================================
    
    "core2": 1.3,
    "core2duo": 1.3,
    "nehalem": 1.2,
    "westmere": 1.2,
    "sandy_bridge": 1.1,
    "sandybridge": 1.1,
    "ivy_bridge": 1.1,
    "ivybridge": 1.15,
    "haswell": 1.1,
    "broadwell": 1.05,
    "skylake": 1.05,
    "kaby_lake": 1.0,
    "coffee_lake": 1.0,
    "cascade_lake": 1.0,
    "comet_lake": 1.0,
    "rocket_lake": 1.0,
    "alder_lake": 1.0,
    "raptor_lake": 1.0,
    "arrow_lake": 1.0,
    "modern_intel": 0.8,
    
    # ===========================================
    # MODERN AMD (2007-2025) - 1.4x to 1.0x
    # ===========================================
    
    "k7_athlon": 1.5,
    "k8_athlon64": 1.5,
    "k10_phenom": 1.4,
    "bulldozer": 1.3,
    "piledriver": 1.3,
    "steamroller": 1.2,
    "excavator": 1.2,
    "zen": 1.1,
    "zen_plus": 1.1,
    "zen2": 1.05,
    "zen3": 1.0,
    "zen4": 1.0,
    "zen5": 1.0,
    "modern_amd": 0.8,
    
    # ===========================================
    # APPLE SILICON (2020-2025) - 1.2x to 1.0x
    # ===========================================
    
    "apple_silicon": 0.8,
    "m1": 1.2,
    "m2": 1.15,
    "m3": 1.1,
    "m4": 1.05,
    
    # ===========================================
    # VINTAGE ARM (1987-2005) — LEGENDARY/ANCIENT
    # These are museum pieces, not NAS boxes
    # ===========================================

    "arm2": 4.0,              # Acorn Archimedes (1987) - MYTHIC
    "arm3": 3.8,              # ARM3 with cache (1989)
    "arm6": 3.5,              # ARM610, first for RiscPC (1992)
    "arm7": 3.0,              # ARM7 (1994)
    "arm7tdmi": 3.0,          # ARM7TDMI - GBA, tons of embedded (1995)
    "strongarm": 2.8,         # DEC/Intel StrongARM SA-110 (1996)
    "sa1100": 2.7,            # StrongARM SA-1100 - iPAQ era (1998)
    "sa1110": 2.7,            # StrongARM SA-1110 (1999)
    "xscale": 2.5,            # Intel XScale - PDAs, Zaurus (2000)
    "arm9": 2.5,              # ARM9 (1998)
    "arm926ej": 2.3,          # ARM926EJ-S (2001)
    "arm11": 2.0,             # ARM11 - original iPhone, RPi 1 (2003)
    "arm1176": 2.0,           # ARM1176JZF-S - Raspberry Pi 1 (2003)
    "cortex_a8": 1.8,         # Cortex-A8 - BeagleBoard, iPhone 3GS (2005)
    "cortex_a9": 1.5,         # Cortex-A9 - Tegra 2, OMAP4 (2007)

    # ===========================================
    # DEFAULTS
    # ===========================================

    "retro": 1.4,
    "modern": 0.8,
    "x86_64": 0.8,
    "aarch64": 0.0005,        # Modern ARM — NAS/SBC spam penalty
    "arm": 0.0005,            # Generic modern ARM
    "armv7": 0.0005,          # Modern ARMv7
    "armv7l": 0.0005,
    "default": 0.8,
    "unknown": 0.8
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
            SELECT DISTINCT miner, device_arch, COALESCE(fingerprint_passed, 1) as fp
            FROM miner_attest_recent
            WHERE ts_ok >= ? AND ts_ok <= ?
        """, (epoch_start_ts - ATTESTATION_TTL, epoch_end_ts))

        epoch_miners = cursor.fetchall()

    if not epoch_miners:
        return {}

    # Calculate time-aged weights
    weighted_miners = []
    total_weight = 0.0

    for row in epoch_miners:
        miner_id, device_arch = row[0], row[1]
        fingerprint_ok = row[2] if len(row) > 2 else 1
        
        # STRICT: VMs/emulators with failed fingerprint get ZERO weight
        if fingerprint_ok == 0:
            weight = 0.0  # No rewards for failed fingerprint
            print(f"[REWARD] {miner_id[:20]}... fingerprint=FAIL -> weight=0")
        else:
            weight = get_time_aged_multiplier(device_arch, chain_age_years)

        # Apply Warthog dual-mining bonus (1.0x/1.1x/1.15x)
        # Double-gated: fingerprint must pass (weight>0) AND fingerprint_ok==1
        if weight > 0 and fingerprint_ok == 1:
            try:
                wart_row = cursor.execute(
                    "SELECT warthog_bonus FROM miner_attest_recent WHERE miner=?",
                    (miner_id,)
                ).fetchone()
                if wart_row and wart_row[0] and wart_row[0] > 1.0:
                    weight *= wart_row[0]
            except Exception:
                pass  # Column may not exist on older schemas

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
