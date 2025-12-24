#!/usr/bin/env python3
"""
RustChain Proof of Antiquity - Hardware Database
================================================
Comprehensive database of vintage and rare hardware for PoA multiplier calculation.
Includes CPUID values, PVR codes, chipset IDs, and rarity bonuses.

Reference databases used:
- Intel/AMD CPUID documentation
- IBM PowerPC Processor Version Register (PVR) values
- Amiga Hardware Reference Manual
- PCI ID Repository (pci-ids.ucw.cz)
- USB ID Repository
"""

from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple
import re

@dataclass
class HardwareEntry:
    """Single hardware entry in the database"""
    id: str                    # Unique identifier (CPUID, PVR, chipset ID)
    name: str                  # Human-readable name
    family: str                # Hardware family (x86, powerpc, m68k, etc.)
    year: int                  # Release year (approximate)
    base_multiplier: float     # Base PoA multiplier
    rarity_bonus: float        # Additional bonus for rare hardware (0.0 - 1.0)
    tier: str                  # MYTHIC, LEGENDARY, ANCIENT, VINTAGE, STANDARD, PENALTY
    notes: str = ""            # Additional notes

# =============================================================================
# x86 PROCESSOR DATABASE (by CPUID Family/Model/Stepping)
# Format: "family_model" or "family_model_stepping"
# =============================================================================

X86_CPUID_DATABASE: Dict[str, HardwareEntry] = {
    # ============ MYTHIC TIER (4.0x) - Pre-486 ============
    # Intel 8086/8088 (1978-1979)
    "8086": HardwareEntry("8086", "Intel 8086", "x86", 1978, 4.0, 0.5, "MYTHIC", "Original x86"),
    "8088": HardwareEntry("8088", "Intel 8088", "x86", 1979, 4.0, 0.5, "MYTHIC", "IBM PC original"),

    # Intel 80186/80188 (1982)
    "80186": HardwareEntry("80186", "Intel 80186", "x86", 1982, 4.0, 0.6, "MYTHIC", "Embedded variant"),
    "80188": HardwareEntry("80188", "Intel 80188", "x86", 1982, 4.0, 0.6, "MYTHIC", "Embedded 8-bit bus"),

    # Intel 80286 (1982)
    "2_0": HardwareEntry("2_0", "Intel 80286", "x86", 1982, 4.0, 0.4, "MYTHIC", "Protected mode"),
    "286": HardwareEntry("286", "Intel 80286", "x86", 1982, 4.0, 0.4, "MYTHIC"),

    # Intel 80386 (1985)
    "3_0": HardwareEntry("3_0", "Intel 80386DX", "x86", 1985, 4.0, 0.3, "MYTHIC", "32-bit x86"),
    "3_2": HardwareEntry("3_2", "Intel 80386SX", "x86", 1988, 4.0, 0.25, "MYTHIC", "16-bit bus"),
    "3_4": HardwareEntry("3_4", "Intel 80386SL", "x86", 1990, 4.0, 0.35, "MYTHIC", "Low power"),
    "386": HardwareEntry("386", "Intel 80386", "x86", 1985, 4.0, 0.3, "MYTHIC"),

    # AMD Am386 variants
    "amd_386": HardwareEntry("amd_386", "AMD Am386", "x86", 1991, 4.0, 0.35, "MYTHIC", "AMD clone"),

    # Cyrix 386 variants
    "cyrix_386": HardwareEntry("cyrix_386", "Cyrix Cx486SLC", "x86", 1992, 4.0, 0.4, "MYTHIC", "386 pin-compatible"),

    # ============ LEGENDARY-HIGH TIER (3.8x) - 486 ============
    # Intel 486 (1989)
    "4_0": HardwareEntry("4_0", "Intel 486DX", "x86", 1989, 3.8, 0.2, "LEGENDARY", "Integrated FPU"),
    "4_1": HardwareEntry("4_1", "Intel 486DX-50", "x86", 1990, 3.8, 0.25, "LEGENDARY", "50MHz variant"),
    "4_2": HardwareEntry("4_2", "Intel 486SX", "x86", 1991, 3.8, 0.15, "LEGENDARY", "No FPU"),
    "4_3": HardwareEntry("4_3", "Intel 486DX2", "x86", 1992, 3.8, 0.2, "LEGENDARY", "Clock doubled"),
    "4_4": HardwareEntry("4_4", "Intel 486SL", "x86", 1992, 3.8, 0.3, "LEGENDARY", "Mobile/low power"),
    "4_5": HardwareEntry("4_5", "Intel 486SX2", "x86", 1994, 3.8, 0.2, "LEGENDARY"),
    "4_7": HardwareEntry("4_7", "Intel 486DX2-WB", "x86", 1994, 3.8, 0.2, "LEGENDARY", "Write-back cache"),
    "4_8": HardwareEntry("4_8", "Intel 486DX4", "x86", 1994, 3.8, 0.2, "LEGENDARY", "Clock tripled"),
    "4_9": HardwareEntry("4_9", "Intel 486DX4-WB", "x86", 1994, 3.8, 0.2, "LEGENDARY"),
    "486": HardwareEntry("486", "Intel 486", "x86", 1989, 3.8, 0.2, "LEGENDARY"),

    # AMD 486 variants (often higher clocks)
    "amd_4_3": HardwareEntry("amd_4_3", "AMD Am486DX2", "x86", 1993, 3.8, 0.25, "LEGENDARY"),
    "amd_4_7": HardwareEntry("amd_4_7", "AMD Am486DX4", "x86", 1994, 3.8, 0.25, "LEGENDARY"),
    "amd_4_8": HardwareEntry("amd_4_8", "AMD Am5x86", "x86", 1995, 3.8, 0.3, "LEGENDARY", "486 socket, P75 perf"),
    "am5x86": HardwareEntry("am5x86", "AMD Am5x86", "x86", 1995, 3.8, 0.3, "LEGENDARY"),

    # Cyrix 486 variants
    "cyrix_4_4": HardwareEntry("cyrix_4_4", "Cyrix Cx486DX2", "x86", 1993, 3.8, 0.35, "LEGENDARY", "Rare"),
    "cyrix_4_9": HardwareEntry("cyrix_4_9", "Cyrix Cx5x86", "x86", 1995, 3.8, 0.4, "LEGENDARY", "Rare Cyrix"),

    # ============ LEGENDARY TIER (3.5x) - Pentium 1 ============
    # Intel Pentium (P5) (1993)
    "5_1": HardwareEntry("5_1", "Intel Pentium 60/66", "x86", 1993, 3.5, 0.2, "LEGENDARY", "First Pentium"),
    "5_2": HardwareEntry("5_2", "Intel Pentium 75-200", "x86", 1994, 3.5, 0.15, "LEGENDARY", "P54C"),
    "5_3": HardwareEntry("5_3", "Intel Pentium OverDrive", "x86", 1995, 3.5, 0.3, "LEGENDARY", "Upgrade chip"),
    "5_4": HardwareEntry("5_4", "Intel Pentium MMX", "x86", 1997, 3.5, 0.1, "LEGENDARY", "P55C with MMX"),
    "5_7": HardwareEntry("5_7", "Intel Pentium MMX Mobile", "x86", 1997, 3.5, 0.2, "LEGENDARY"),
    "5_8": HardwareEntry("5_8", "Intel Pentium MMX Mobile", "x86", 1998, 3.5, 0.2, "LEGENDARY"),
    "pentium": HardwareEntry("pentium", "Intel Pentium", "x86", 1993, 3.5, 0.15, "LEGENDARY"),
    "p5": HardwareEntry("p5", "Intel Pentium P5", "x86", 1993, 3.5, 0.15, "LEGENDARY"),
    "p54c": HardwareEntry("p54c", "Intel Pentium P54C", "x86", 1994, 3.5, 0.15, "LEGENDARY"),
    "p55c": HardwareEntry("p55c", "Intel Pentium MMX P55C", "x86", 1997, 3.5, 0.1, "LEGENDARY"),

    # AMD K5 (1996) - Pentium competitor
    "amd_5_0": HardwareEntry("amd_5_0", "AMD K5 PR75-PR100", "x86", 1996, 3.5, 0.3, "LEGENDARY", "AMD's first x86"),
    "amd_5_1": HardwareEntry("amd_5_1", "AMD K5 PR120-PR133", "x86", 1996, 3.5, 0.3, "LEGENDARY"),
    "amd_5_2": HardwareEntry("amd_5_2", "AMD K5 PR150-PR200", "x86", 1996, 3.5, 0.3, "LEGENDARY"),
    "k5": HardwareEntry("k5", "AMD K5", "x86", 1996, 3.5, 0.3, "LEGENDARY"),

    # Cyrix 6x86 (1996) - Pentium competitor (actually family 5 compatible)
    "cyrix_5_2": HardwareEntry("cyrix_5_2", "Cyrix 6x86", "x86", 1996, 3.5, 0.4, "LEGENDARY", "Rare Cyrix"),
    "cyrix_5_4": HardwareEntry("cyrix_5_4", "Cyrix 6x86MX", "x86", 1997, 3.5, 0.4, "LEGENDARY", "Rare"),
    "6x86": HardwareEntry("6x86", "Cyrix 6x86", "x86", 1996, 3.5, 0.4, "LEGENDARY"),

    # IDT/Centaur WinChip (1997)
    "idt_5_4": HardwareEntry("idt_5_4", "IDT WinChip C6", "x86", 1997, 3.5, 0.5, "LEGENDARY", "Very rare"),
    "idt_5_8": HardwareEntry("idt_5_8", "IDT WinChip 2", "x86", 1998, 3.5, 0.5, "LEGENDARY", "Very rare"),
    "winchip": HardwareEntry("winchip", "IDT WinChip", "x86", 1997, 3.5, 0.5, "LEGENDARY"),

    # NexGen Nx586 (1994) - Very rare
    "nexgen_5": HardwareEntry("nexgen_5", "NexGen Nx586", "x86", 1994, 3.5, 0.7, "LEGENDARY", "Extremely rare"),
    "nx586": HardwareEntry("nx586", "NexGen Nx586", "x86", 1994, 3.5, 0.7, "LEGENDARY"),

    # ============ LEGENDARY-LOW TIER (3.2x) - Pentium II / Celeron ============
    # Intel Pentium Pro (1995) - Actually family 6
    "6_1": HardwareEntry("6_1", "Intel Pentium Pro", "x86", 1995, 3.2, 0.2, "LEGENDARY", "P6 architecture"),
    "ppro": HardwareEntry("ppro", "Intel Pentium Pro", "x86", 1995, 3.2, 0.2, "LEGENDARY"),

    # Intel Pentium II (1997)
    "6_3": HardwareEntry("6_3", "Intel Pentium II Klamath", "x86", 1997, 3.2, 0.15, "LEGENDARY", "Slot 1"),
    "6_5": HardwareEntry("6_5", "Intel Pentium II Deschutes", "x86", 1998, 3.2, 0.1, "LEGENDARY"),
    "pii": HardwareEntry("pii", "Intel Pentium II", "x86", 1997, 3.2, 0.15, "LEGENDARY"),
    "p2": HardwareEntry("p2", "Intel Pentium II", "x86", 1997, 3.2, 0.15, "LEGENDARY"),
    "klamath": HardwareEntry("klamath", "Intel Pentium II Klamath", "x86", 1997, 3.2, 0.15, "LEGENDARY"),

    # Intel Celeron (1998)
    "6_6": HardwareEntry("6_6", "Intel Celeron Mendocino", "x86", 1998, 3.2, 0.1, "LEGENDARY"),
    "celeron_slot1": HardwareEntry("celeron_slot1", "Intel Celeron (Slot 1)", "x86", 1998, 3.2, 0.15, "LEGENDARY"),
    "mendocino": HardwareEntry("mendocino", "Intel Celeron Mendocino", "x86", 1998, 3.2, 0.1, "LEGENDARY"),

    # AMD K6 (1997)
    "amd_6_6": HardwareEntry("amd_6_6", "AMD K6", "x86", 1997, 3.2, 0.2, "LEGENDARY"),
    "amd_6_8": HardwareEntry("amd_6_8", "AMD K6-2", "x86", 1998, 3.2, 0.15, "LEGENDARY", "3DNow!"),
    "amd_6_9": HardwareEntry("amd_6_9", "AMD K6-III", "x86", 1999, 3.2, 0.2, "LEGENDARY", "Triple cache"),
    "k6": HardwareEntry("k6", "AMD K6", "x86", 1997, 3.2, 0.2, "LEGENDARY"),
    "k6-2": HardwareEntry("k6-2", "AMD K6-2", "x86", 1998, 3.2, 0.15, "LEGENDARY"),
    "k6-3": HardwareEntry("k6-3", "AMD K6-III", "x86", 1999, 3.2, 0.2, "LEGENDARY"),

    # ============ LEGENDARY-LOW TIER (3.0x) - Pentium III / Athlon ============
    # Intel Pentium III (1999)
    "6_7": HardwareEntry("6_7", "Intel Pentium III Katmai", "x86", 1999, 3.0, 0.1, "LEGENDARY", "SSE"),
    "6_8": HardwareEntry("6_8", "Intel Pentium III Coppermine", "x86", 1999, 3.0, 0.05, "LEGENDARY"),
    "6_10": HardwareEntry("6_10", "Intel Pentium III Coppermine-T", "x86", 2000, 3.0, 0.05, "LEGENDARY"),
    "6_11": HardwareEntry("6_11", "Intel Pentium III Tualatin", "x86", 2001, 3.0, 0.1, "LEGENDARY"),
    "piii": HardwareEntry("piii", "Intel Pentium III", "x86", 1999, 3.0, 0.1, "LEGENDARY"),
    "p3": HardwareEntry("p3", "Intel Pentium III", "x86", 1999, 3.0, 0.1, "LEGENDARY"),
    "katmai": HardwareEntry("katmai", "Intel Pentium III Katmai", "x86", 1999, 3.0, 0.1, "LEGENDARY"),
    "coppermine": HardwareEntry("coppermine", "Intel Pentium III Coppermine", "x86", 1999, 3.0, 0.05, "LEGENDARY"),
    "tualatin": HardwareEntry("tualatin", "Intel Pentium III Tualatin", "x86", 2001, 3.0, 0.1, "LEGENDARY"),

    # AMD Athlon (1999)
    "amd_6_1": HardwareEntry("amd_6_1", "AMD Athlon (K7)", "x86", 1999, 3.0, 0.1, "LEGENDARY", "Slot A"),
    "amd_6_2": HardwareEntry("amd_6_2", "AMD Athlon (K75)", "x86", 1999, 3.0, 0.1, "LEGENDARY"),
    "amd_6_4": HardwareEntry("amd_6_4", "AMD Athlon Thunderbird", "x86", 2000, 3.0, 0.05, "LEGENDARY"),
    "amd_6_6_xp": HardwareEntry("amd_6_6_xp", "AMD Athlon XP Palomino", "x86", 2001, 3.0, 0.05, "LEGENDARY"),
    "amd_6_8_xp": HardwareEntry("amd_6_8_xp", "AMD Athlon XP Thoroughbred", "x86", 2002, 3.0, 0.05, "LEGENDARY"),
    "amd_6_10_xp": HardwareEntry("amd_6_10_xp", "AMD Athlon XP Barton", "x86", 2003, 3.0, 0.1, "LEGENDARY", "512K L2"),
    "athlon": HardwareEntry("athlon", "AMD Athlon", "x86", 1999, 3.0, 0.1, "LEGENDARY"),
    "athlon_xp": HardwareEntry("athlon_xp", "AMD Athlon XP", "x86", 2001, 3.0, 0.05, "LEGENDARY"),
    "thunderbird": HardwareEntry("thunderbird", "AMD Athlon Thunderbird", "x86", 2000, 3.0, 0.05, "LEGENDARY"),
    "barton": HardwareEntry("barton", "AMD Athlon XP Barton", "x86", 2003, 3.0, 0.1, "LEGENDARY"),

    # VIA C3 (2001) - Rare
    "via_6_7": HardwareEntry("via_6_7", "VIA C3 Samuel", "x86", 2001, 3.0, 0.4, "LEGENDARY", "Rare VIA"),
    "via_6_8": HardwareEntry("via_6_8", "VIA C3 Ezra", "x86", 2001, 3.0, 0.4, "LEGENDARY", "Rare"),
    "via_6_9": HardwareEntry("via_6_9", "VIA C3 Nehemiah", "x86", 2003, 3.0, 0.4, "LEGENDARY", "Rare"),
    "c3": HardwareEntry("c3", "VIA C3", "x86", 2001, 3.0, 0.4, "LEGENDARY"),

    # Transmeta Crusoe (2000) - Very rare
    "transmeta_5_4": HardwareEntry("transmeta_5_4", "Transmeta Crusoe TM5400", "x86", 2000, 3.0, 0.6, "LEGENDARY", "Code morphing"),
    "transmeta_5_5": HardwareEntry("transmeta_5_5", "Transmeta Crusoe TM5600", "x86", 2000, 3.0, 0.6, "LEGENDARY"),
    "transmeta_15": HardwareEntry("transmeta_15", "Transmeta Efficeon", "x86", 2003, 3.0, 0.6, "LEGENDARY"),
    "crusoe": HardwareEntry("crusoe", "Transmeta Crusoe", "x86", 2000, 3.0, 0.6, "LEGENDARY"),
    "efficeon": HardwareEntry("efficeon", "Transmeta Efficeon", "x86", 2003, 3.0, 0.6, "LEGENDARY"),

    # ============ ANCIENT TIER (2.5x) - Pentium 4 / Athlon 64 ============
    # Intel Pentium 4 (2000)
    "15_0": HardwareEntry("15_0", "Intel Pentium 4 Willamette", "x86", 2000, 2.5, 0.1, "ANCIENT", "NetBurst"),
    "15_1": HardwareEntry("15_1", "Intel Pentium 4 Willamette-2", "x86", 2001, 2.5, 0.1, "ANCIENT"),
    "15_2": HardwareEntry("15_2", "Intel Pentium 4 Northwood", "x86", 2002, 2.5, 0.05, "ANCIENT", "130nm"),
    "15_3": HardwareEntry("15_3", "Intel Pentium 4 Prescott", "x86", 2004, 2.5, 0.05, "ANCIENT", "90nm"),
    "15_4": HardwareEntry("15_4", "Intel Pentium 4 Prescott-2M", "x86", 2005, 2.5, 0.05, "ANCIENT"),
    "15_6": HardwareEntry("15_6", "Intel Pentium D", "x86", 2005, 2.5, 0.1, "ANCIENT", "Dual Prescott"),
    "p4": HardwareEntry("p4", "Intel Pentium 4", "x86", 2000, 2.5, 0.05, "ANCIENT"),
    "pentium4": HardwareEntry("pentium4", "Intel Pentium 4", "x86", 2000, 2.5, 0.05, "ANCIENT"),
    "willamette": HardwareEntry("willamette", "Intel Pentium 4 Willamette", "x86", 2000, 2.5, 0.1, "ANCIENT"),
    "northwood": HardwareEntry("northwood", "Intel Pentium 4 Northwood", "x86", 2002, 2.5, 0.05, "ANCIENT"),
    "prescott": HardwareEntry("prescott", "Intel Pentium 4 Prescott", "x86", 2004, 2.5, 0.05, "ANCIENT"),

    # Intel Pentium M (2003)
    "6_9": HardwareEntry("6_9", "Intel Pentium M Banias", "x86", 2003, 2.5, 0.15, "ANCIENT", "Mobile P6"),
    "6_13": HardwareEntry("6_13", "Intel Pentium M Dothan", "x86", 2004, 2.5, 0.1, "ANCIENT"),
    "pentium_m": HardwareEntry("pentium_m", "Intel Pentium M", "x86", 2003, 2.5, 0.1, "ANCIENT"),
    "banias": HardwareEntry("banias", "Intel Pentium M Banias", "x86", 2003, 2.5, 0.15, "ANCIENT"),
    "dothan": HardwareEntry("dothan", "Intel Pentium M Dothan", "x86", 2004, 2.5, 0.1, "ANCIENT"),

    # AMD Athlon 64 (2003)
    "amd_15_4": HardwareEntry("amd_15_4", "AMD Athlon 64 Clawhammer", "x86", 2003, 2.5, 0.1, "ANCIENT", "x86-64"),
    "amd_15_5": HardwareEntry("amd_15_5", "AMD Opteron", "x86", 2003, 2.5, 0.15, "ANCIENT", "Server"),
    "amd_15_7": HardwareEntry("amd_15_7", "AMD Athlon 64 San Diego", "x86", 2005, 2.5, 0.1, "ANCIENT"),
    "amd_15_11": HardwareEntry("amd_15_11", "AMD Athlon 64 Orleans", "x86", 2006, 2.5, 0.05, "ANCIENT"),
    "amd_15_35": HardwareEntry("amd_15_35", "AMD Athlon 64 X2", "x86", 2005, 2.5, 0.1, "ANCIENT", "Dual core"),
    "athlon64": HardwareEntry("athlon64", "AMD Athlon 64", "x86", 2003, 2.5, 0.1, "ANCIENT"),
    "athlon64_x2": HardwareEntry("athlon64_x2", "AMD Athlon 64 X2", "x86", 2005, 2.5, 0.1, "ANCIENT"),
    "opteron": HardwareEntry("opteron", "AMD Opteron", "x86", 2003, 2.5, 0.15, "ANCIENT"),

    # ============ ANCIENT TIER (2.0x) - Core Duo / Early Core ============
    # Intel Core (2006)
    "6_14": HardwareEntry("6_14", "Intel Core Yonah", "x86", 2006, 2.0, 0.1, "ANCIENT", "Core Duo/Solo"),
    "core_duo": HardwareEntry("core_duo", "Intel Core Duo", "x86", 2006, 2.0, 0.1, "ANCIENT"),
    "core_solo": HardwareEntry("core_solo", "Intel Core Solo", "x86", 2006, 2.0, 0.1, "ANCIENT"),
    "yonah": HardwareEntry("yonah", "Intel Core Yonah", "x86", 2006, 2.0, 0.1, "ANCIENT"),

    # Intel Pentium D
    "pentium_d": HardwareEntry("pentium_d", "Intel Pentium D", "x86", 2005, 2.0, 0.1, "ANCIENT"),

    # AMD Athlon X2 (socket 939/AM2)
    "amd_15_67": HardwareEntry("amd_15_67", "AMD Athlon X2 Brisbane", "x86", 2007, 2.0, 0.05, "ANCIENT"),

    # ============ VINTAGE TIER (1.5x) - Core 2 ============
    # Intel Core 2 (2006)
    "6_15": HardwareEntry("6_15", "Intel Core 2 Merom/Conroe", "x86", 2006, 1.5, 0.05, "VINTAGE", "Core 2 Duo"),
    "6_22": HardwareEntry("6_22", "Intel Core 2 Merom-L", "x86", 2007, 1.5, 0.05, "VINTAGE"),
    "6_23": HardwareEntry("6_23", "Intel Core 2 Penryn", "x86", 2008, 1.5, 0.05, "VINTAGE", "45nm"),
    "6_29": HardwareEntry("6_29", "Intel Xeon Dunnington", "x86", 2008, 1.5, 0.1, "VINTAGE", "6-core"),
    "core2": HardwareEntry("core2", "Intel Core 2", "x86", 2006, 1.5, 0.05, "VINTAGE"),
    "core2_duo": HardwareEntry("core2_duo", "Intel Core 2 Duo", "x86", 2006, 1.5, 0.05, "VINTAGE"),
    "core2_quad": HardwareEntry("core2_quad", "Intel Core 2 Quad", "x86", 2007, 1.5, 0.05, "VINTAGE"),
    "conroe": HardwareEntry("conroe", "Intel Core 2 Conroe", "x86", 2006, 1.5, 0.05, "VINTAGE"),
    "merom": HardwareEntry("merom", "Intel Core 2 Merom", "x86", 2006, 1.5, 0.05, "VINTAGE"),
    "penryn": HardwareEntry("penryn", "Intel Core 2 Penryn", "x86", 2008, 1.5, 0.05, "VINTAGE"),

    # AMD Phenom (2007)
    "amd_16_2": HardwareEntry("amd_16_2", "AMD Phenom X4 Agena", "x86", 2007, 1.5, 0.1, "VINTAGE"),
    "amd_16_4": HardwareEntry("amd_16_4", "AMD Phenom II X4 Deneb", "x86", 2009, 1.5, 0.05, "VINTAGE"),
    "amd_16_6": HardwareEntry("amd_16_6", "AMD Phenom II X6 Thuban", "x86", 2010, 1.5, 0.1, "VINTAGE", "6-core"),
    "phenom": HardwareEntry("phenom", "AMD Phenom", "x86", 2007, 1.5, 0.1, "VINTAGE"),
    "phenom_ii": HardwareEntry("phenom_ii", "AMD Phenom II", "x86", 2009, 1.5, 0.05, "VINTAGE"),

    # AMD FX (2011)
    "amd_21_1": HardwareEntry("amd_21_1", "AMD FX Bulldozer", "x86", 2011, 1.5, 0.1, "VINTAGE"),
    "amd_21_2": HardwareEntry("amd_21_2", "AMD FX Piledriver", "x86", 2012, 1.5, 0.1, "VINTAGE"),
    "fx": HardwareEntry("fx", "AMD FX", "x86", 2011, 1.5, 0.1, "VINTAGE"),
    "bulldozer": HardwareEntry("bulldozer", "AMD FX Bulldozer", "x86", 2011, 1.5, 0.1, "VINTAGE"),
    "piledriver": HardwareEntry("piledriver", "AMD FX Piledriver", "x86", 2012, 1.5, 0.1, "VINTAGE"),

    # ============ STANDARD TIER (1.0x) - Nehalem through Haswell ============
    "6_26": HardwareEntry("6_26", "Intel Core i7 Nehalem", "x86", 2008, 1.0, 0.0, "STANDARD"),
    "6_30": HardwareEntry("6_30", "Intel Core i7 Lynnfield", "x86", 2009, 1.0, 0.0, "STANDARD"),
    "6_37": HardwareEntry("6_37", "Intel Core Westmere", "x86", 2010, 1.0, 0.0, "STANDARD"),
    "6_42": HardwareEntry("6_42", "Intel Core Sandy Bridge", "x86", 2011, 1.0, 0.0, "STANDARD"),
    "6_58": HardwareEntry("6_58", "Intel Core Ivy Bridge", "x86", 2012, 1.0, 0.0, "STANDARD"),
    "6_60": HardwareEntry("6_60", "Intel Core Haswell", "x86", 2013, 1.0, 0.0, "STANDARD"),
    "nehalem": HardwareEntry("nehalem", "Intel Core Nehalem", "x86", 2008, 1.0, 0.0, "STANDARD"),
    "sandy_bridge": HardwareEntry("sandy_bridge", "Intel Core Sandy Bridge", "x86", 2011, 1.0, 0.0, "STANDARD"),
    "ivy_bridge": HardwareEntry("ivy_bridge", "Intel Core Ivy Bridge", "x86", 2012, 1.0, 0.0, "STANDARD"),
    "haswell": HardwareEntry("haswell", "Intel Core Haswell", "x86", 2013, 1.0, 0.0, "STANDARD"),

    # ============ PENALTY TIER (0.8x) - Modern x86-64 ============
    "6_61": HardwareEntry("6_61", "Intel Core Broadwell", "x86", 2014, 0.8, 0.0, "PENALTY"),
    "6_78": HardwareEntry("6_78", "Intel Core Skylake", "x86", 2015, 0.8, 0.0, "PENALTY"),
    "6_142": HardwareEntry("6_142", "Intel Core Kaby Lake", "x86", 2016, 0.8, 0.0, "PENALTY"),
    "6_158": HardwareEntry("6_158", "Intel Core Coffee Lake", "x86", 2017, 0.8, 0.0, "PENALTY"),
    "skylake": HardwareEntry("skylake", "Intel Core Skylake", "x86", 2015, 0.8, 0.0, "PENALTY"),
    "kaby_lake": HardwareEntry("kaby_lake", "Intel Core Kaby Lake", "x86", 2016, 0.8, 0.0, "PENALTY"),
    "coffee_lake": HardwareEntry("coffee_lake", "Intel Core Coffee Lake", "x86", 2017, 0.8, 0.0, "PENALTY"),
    "alder_lake": HardwareEntry("alder_lake", "Intel Core Alder Lake", "x86", 2021, 0.8, 0.0, "PENALTY"),
    "raptor_lake": HardwareEntry("raptor_lake", "Intel Core Raptor Lake", "x86", 2022, 0.8, 0.0, "PENALTY"),

    # AMD Ryzen (Modern - Penalty)
    "amd_23_1": HardwareEntry("amd_23_1", "AMD Ryzen Zen", "x86", 2017, 0.8, 0.0, "PENALTY"),
    "amd_23_8": HardwareEntry("amd_23_8", "AMD Ryzen Zen+", "x86", 2018, 0.8, 0.0, "PENALTY"),
    "amd_23_49": HardwareEntry("amd_23_49", "AMD Ryzen Zen 2", "x86", 2019, 0.8, 0.0, "PENALTY"),
    "amd_25_33": HardwareEntry("amd_25_33", "AMD Ryzen Zen 3", "x86", 2020, 0.8, 0.0, "PENALTY"),
    "amd_25_97": HardwareEntry("amd_25_97", "AMD Ryzen Zen 4", "x86", 2022, 0.8, 0.0, "PENALTY"),
    "ryzen": HardwareEntry("ryzen", "AMD Ryzen", "x86", 2017, 0.8, 0.0, "PENALTY"),
    "zen": HardwareEntry("zen", "AMD Ryzen Zen", "x86", 2017, 0.8, 0.0, "PENALTY"),
    "zen2": HardwareEntry("zen2", "AMD Ryzen Zen 2", "x86", 2019, 0.8, 0.0, "PENALTY"),
    "zen3": HardwareEntry("zen3", "AMD Ryzen Zen 3", "x86", 2020, 0.8, 0.0, "PENALTY"),
    "zen4": HardwareEntry("zen4", "AMD Ryzen Zen 4", "x86", 2022, 0.8, 0.0, "PENALTY"),
}

# =============================================================================
# POWERPC PROCESSOR DATABASE (by PVR - Processor Version Register)
# =============================================================================

POWERPC_PVR_DATABASE: Dict[str, HardwareEntry] = {
    # ============ MYTHIC TIER (4.0x) - POWER1 / PowerPC 601 ============
    "0x0001": HardwareEntry("0x0001", "PowerPC 601", "powerpc", 1993, 4.0, 0.4, "MYTHIC", "First PowerPC"),
    "0x0003": HardwareEntry("0x0003", "PowerPC 603", "powerpc", 1994, 3.5, 0.2, "LEGENDARY", "Low power"),
    "0x0004": HardwareEntry("0x0004", "PowerPC 604", "powerpc", 1994, 3.5, 0.2, "LEGENDARY", "High performance"),
    "0x0006": HardwareEntry("0x0006", "PowerPC 603e", "powerpc", 1996, 3.5, 0.15, "LEGENDARY"),
    "0x0007": HardwareEntry("0x0007", "PowerPC 603ev", "powerpc", 1997, 3.5, 0.15, "LEGENDARY"),
    "0x0009": HardwareEntry("0x0009", "PowerPC 604e", "powerpc", 1996, 3.5, 0.15, "LEGENDARY"),
    "0x000A": HardwareEntry("0x000A", "PowerPC 604ev", "powerpc", 1997, 3.5, 0.15, "LEGENDARY"),
    "601": HardwareEntry("601", "PowerPC 601", "powerpc", 1993, 4.0, 0.4, "MYTHIC"),
    "603": HardwareEntry("603", "PowerPC 603", "powerpc", 1994, 3.5, 0.2, "LEGENDARY"),
    "603e": HardwareEntry("603e", "PowerPC 603e", "powerpc", 1996, 3.5, 0.15, "LEGENDARY"),
    "604": HardwareEntry("604", "PowerPC 604", "powerpc", 1994, 3.5, 0.2, "LEGENDARY"),
    "604e": HardwareEntry("604e", "PowerPC 604e", "powerpc", 1996, 3.5, 0.15, "LEGENDARY"),

    # ============ LEGENDARY TIER (3.2x) - PowerPC G3 ============
    "0x0008": HardwareEntry("0x0008", "PowerPC 750 (G3)", "powerpc", 1997, 3.2, 0.1, "LEGENDARY", "G3"),
    "0x7000": HardwareEntry("0x7000", "PowerPC 750CX (G3)", "powerpc", 1999, 3.2, 0.1, "LEGENDARY"),
    "0x7002": HardwareEntry("0x7002", "PowerPC 750CXe (G3)", "powerpc", 2000, 3.2, 0.1, "LEGENDARY"),
    "0x7003": HardwareEntry("0x7003", "PowerPC 750FX (G3)", "powerpc", 2002, 3.2, 0.15, "LEGENDARY"),
    "0x7004": HardwareEntry("0x7004", "PowerPC 750GX (G3)", "powerpc", 2004, 3.2, 0.15, "LEGENDARY"),
    "750": HardwareEntry("750", "PowerPC 750 (G3)", "powerpc", 1997, 3.2, 0.1, "LEGENDARY"),
    "g3": HardwareEntry("g3", "PowerPC G3", "powerpc", 1997, 3.2, 0.1, "LEGENDARY"),
    "750cx": HardwareEntry("750cx", "PowerPC 750CX (G3)", "powerpc", 1999, 3.2, 0.1, "LEGENDARY"),
    "750fx": HardwareEntry("750fx", "PowerPC 750FX (G3)", "powerpc", 2002, 3.2, 0.15, "LEGENDARY"),
    "750gx": HardwareEntry("750gx", "PowerPC 750GX (G3)", "powerpc", 2004, 3.2, 0.15, "LEGENDARY"),

    # ============ ANCIENT TIER (2.5x) - PowerPC G4 ============
    "0x000C": HardwareEntry("0x000C", "PowerPC 7400 (G4)", "powerpc", 1999, 2.5, 0.1, "ANCIENT", "AltiVec"),
    "0x800C": HardwareEntry("0x800C", "PowerPC 7410 (G4)", "powerpc", 2000, 2.5, 0.1, "ANCIENT"),
    "0x8000": HardwareEntry("0x8000", "PowerPC 7450 (G4)", "powerpc", 2001, 2.5, 0.1, "ANCIENT", "Improved G4"),
    "0x8001": HardwareEntry("0x8001", "PowerPC 7445 (G4)", "powerpc", 2003, 2.5, 0.1, "ANCIENT"),
    "0x8002": HardwareEntry("0x8002", "PowerPC 7455 (G4)", "powerpc", 2002, 2.5, 0.1, "ANCIENT"),
    "0x8003": HardwareEntry("0x8003", "PowerPC 7447 (G4)", "powerpc", 2003, 2.5, 0.1, "ANCIENT"),
    "0x8004": HardwareEntry("0x8004", "PowerPC 7448 (G4)", "powerpc", 2005, 2.5, 0.15, "ANCIENT", "Last G4"),
    "7400": HardwareEntry("7400", "PowerPC 7400 (G4)", "powerpc", 1999, 2.5, 0.1, "ANCIENT"),
    "7410": HardwareEntry("7410", "PowerPC 7410 (G4)", "powerpc", 2000, 2.5, 0.1, "ANCIENT"),
    "7450": HardwareEntry("7450", "PowerPC 7450 (G4)", "powerpc", 2001, 2.5, 0.1, "ANCIENT"),
    "7455": HardwareEntry("7455", "PowerPC 7455 (G4)", "powerpc", 2002, 2.5, 0.1, "ANCIENT"),
    "7447": HardwareEntry("7447", "PowerPC 7447 (G4)", "powerpc", 2003, 2.5, 0.1, "ANCIENT"),
    "7448": HardwareEntry("7448", "PowerPC 7448 (G4)", "powerpc", 2005, 2.5, 0.15, "ANCIENT"),
    "g4": HardwareEntry("g4", "PowerPC G4", "powerpc", 1999, 2.5, 0.1, "ANCIENT"),

    # ============ ANCIENT TIER (2.0x) - PowerPC G5 ============
    "0x0039": HardwareEntry("0x0039", "PowerPC 970 (G5)", "powerpc", 2003, 2.0, 0.1, "ANCIENT", "First G5"),
    "0x003C": HardwareEntry("0x003C", "PowerPC 970FX (G5)", "powerpc", 2004, 2.0, 0.1, "ANCIENT", "90nm"),
    "0x0044": HardwareEntry("0x0044", "PowerPC 970MP (G5)", "powerpc", 2005, 2.0, 0.15, "ANCIENT", "Dual-core"),
    "970": HardwareEntry("970", "PowerPC 970 (G5)", "powerpc", 2003, 2.0, 0.1, "ANCIENT"),
    "970fx": HardwareEntry("970fx", "PowerPC 970FX (G5)", "powerpc", 2004, 2.0, 0.1, "ANCIENT"),
    "970mp": HardwareEntry("970mp", "PowerPC 970MP (G5)", "powerpc", 2005, 2.0, 0.15, "ANCIENT"),
    "g5": HardwareEntry("g5", "PowerPC G5", "powerpc", 2003, 2.0, 0.1, "ANCIENT"),

    # ============ RARE POWERPC VARIANTS ============
    # IBM POWER series (Servers)
    "power1": HardwareEntry("power1", "IBM POWER1", "powerpc", 1990, 4.0, 0.7, "MYTHIC", "Extremely rare"),
    "power2": HardwareEntry("power2", "IBM POWER2", "powerpc", 1993, 4.0, 0.6, "MYTHIC", "Very rare"),
    "power3": HardwareEntry("power3", "IBM POWER3", "powerpc", 1998, 3.5, 0.5, "LEGENDARY", "Rare server"),
    "power4": HardwareEntry("power4", "IBM POWER4", "powerpc", 2001, 3.0, 0.4, "LEGENDARY", "First GHz"),
    "power5": HardwareEntry("power5", "IBM POWER5", "powerpc", 2004, 2.5, 0.3, "ANCIENT"),

    # Freescale/NXP embedded PowerPC
    "mpc5xx": HardwareEntry("mpc5xx", "Freescale MPC5xx", "powerpc", 1996, 3.5, 0.5, "LEGENDARY", "Automotive"),
    "mpc8xx": HardwareEntry("mpc8xx", "Freescale MPC8xx", "powerpc", 1997, 3.5, 0.4, "LEGENDARY", "Networking"),
    "e300": HardwareEntry("e300", "Freescale e300", "powerpc", 2004, 3.0, 0.3, "LEGENDARY"),
    "e500": HardwareEntry("e500", "Freescale e500", "powerpc", 2003, 2.5, 0.3, "ANCIENT"),
    "e600": HardwareEntry("e600", "Freescale e600", "powerpc", 2005, 2.5, 0.3, "ANCIENT"),

    # AMCC PowerPC
    "ppc405": HardwareEntry("ppc405", "AMCC PPC405", "powerpc", 1999, 3.2, 0.4, "LEGENDARY", "Embedded"),
    "ppc440": HardwareEntry("ppc440", "AMCC PPC440", "powerpc", 2002, 3.0, 0.3, "LEGENDARY"),
    "ppc460": HardwareEntry("ppc460", "AMCC PPC460", "powerpc", 2006, 2.5, 0.3, "ANCIENT"),
}

# =============================================================================
# MOTOROLA 68K PROCESSOR DATABASE
# =============================================================================

M68K_DATABASE: Dict[str, HardwareEntry] = {
    # ============ MYTHIC TIER (4.0x) ============
    "68000": HardwareEntry("68000", "Motorola 68000", "m68k", 1979, 4.0, 0.3, "MYTHIC", "Original Mac/Amiga"),
    "68008": HardwareEntry("68008", "Motorola 68008", "m68k", 1982, 4.0, 0.4, "MYTHIC", "8-bit bus variant"),
    "68010": HardwareEntry("68010", "Motorola 68010", "m68k", 1982, 4.0, 0.35, "MYTHIC", "Virtual memory"),
    "68012": HardwareEntry("68012", "Motorola 68012", "m68k", 1983, 4.0, 0.6, "MYTHIC", "Very rare"),
    "68020": HardwareEntry("68020", "Motorola 68020", "m68k", 1984, 4.0, 0.25, "MYTHIC", "32-bit"),
    "68030": HardwareEntry("68030", "Motorola 68030", "m68k", 1987, 4.0, 0.2, "MYTHIC", "Integrated MMU"),

    # ============ LEGENDARY-HIGH TIER (3.8x) ============
    "68040": HardwareEntry("68040", "Motorola 68040", "m68k", 1990, 3.8, 0.2, "LEGENDARY", "Integrated FPU"),
    "68lc040": HardwareEntry("68lc040", "Motorola 68LC040", "m68k", 1991, 3.8, 0.25, "LEGENDARY", "No FPU"),
    "68060": HardwareEntry("68060", "Motorola 68060", "m68k", 1994, 3.8, 0.3, "LEGENDARY", "Final 68K"),
    "68lc060": HardwareEntry("68lc060", "Motorola 68LC060", "m68k", 1995, 3.8, 0.35, "LEGENDARY"),

    # ============ RARE VARIANTS ============
    "cpu32": HardwareEntry("cpu32", "Motorola CPU32", "m68k", 1990, 3.8, 0.5, "LEGENDARY", "Embedded 68K"),
    "coldfire": HardwareEntry("coldfire", "Freescale ColdFire", "m68k", 1994, 3.5, 0.3, "LEGENDARY", "68K compatible"),
    "dragonball": HardwareEntry("dragonball", "Motorola DragonBall", "m68k", 1995, 3.5, 0.4, "LEGENDARY", "Palm PDAs"),
}

# =============================================================================
# CLASSIC COMPUTER CHIPSET DATABASE (Amiga, Atari, C64, etc.)
# =============================================================================

CLASSIC_CHIPSET_DATABASE: Dict[str, HardwareEntry] = {
    # ============ AMIGA CHIPSETS (MYTHIC) ============
    "ocs": HardwareEntry("ocs", "Amiga OCS (Original Chip Set)", "amiga", 1985, 4.0, 0.3, "MYTHIC", "A1000/A500/A2000"),
    "ecs": HardwareEntry("ecs", "Amiga ECS (Enhanced Chip Set)", "amiga", 1990, 4.0, 0.25, "MYTHIC", "A500+/A600/A3000"),
    "aga": HardwareEntry("aga", "Amiga AGA (Advanced Graphics)", "amiga", 1992, 4.0, 0.2, "MYTHIC", "A1200/A4000"),
    "agnus_8361": HardwareEntry("agnus_8361", "Agnus 8361 (PAL-A)", "amiga", 1985, 4.0, 0.35, "MYTHIC"),
    "agnus_8367": HardwareEntry("agnus_8367", "Agnus 8367 (NTSC-A)", "amiga", 1985, 4.0, 0.35, "MYTHIC"),
    "agnus_8370": HardwareEntry("agnus_8370", "Fat Agnus 8370", "amiga", 1987, 4.0, 0.3, "MYTHIC", "1MB"),
    "agnus_8372": HardwareEntry("agnus_8372", "Fat Agnus 8372", "amiga", 1988, 4.0, 0.3, "MYTHIC", "ECS"),
    "agnus_8375": HardwareEntry("agnus_8375", "Alice 8375", "amiga", 1992, 4.0, 0.25, "MYTHIC", "AGA"),
    "denise_8362": HardwareEntry("denise_8362", "Denise 8362", "amiga", 1985, 4.0, 0.35, "MYTHIC", "OCS"),
    "denise_8373": HardwareEntry("denise_8373", "Super Denise 8373", "amiga", 1990, 4.0, 0.3, "MYTHIC", "ECS"),
    "lisa_8364": HardwareEntry("lisa_8364", "Lisa 8364", "amiga", 1992, 4.0, 0.25, "MYTHIC", "AGA"),
    "paula_8364": HardwareEntry("paula_8364", "Paula 8364", "amiga", 1985, 4.0, 0.35, "MYTHIC", "Sound/IO"),

    # Amiga Accelerator Cards (RARE!)
    "blizzard_1230": HardwareEntry("blizzard_1230", "Blizzard 1230 (68030)", "amiga", 1995, 4.0, 0.5, "MYTHIC", "A1200 accelerator"),
    "blizzard_1260": HardwareEntry("blizzard_1260", "Blizzard 1260 (68060)", "amiga", 1997, 4.0, 0.6, "MYTHIC", "Very rare"),
    "cyberstorm_060": HardwareEntry("cyberstorm_060", "CyberStorm 68060", "amiga", 1996, 4.0, 0.6, "MYTHIC", "A4000 accelerator"),
    "apollo_68080": HardwareEntry("apollo_68080", "Apollo 68080 FPGA", "amiga", 2017, 3.5, 0.7, "LEGENDARY", "Modern retro"),

    # ============ ATARI CHIPSETS (MYTHIC) ============
    "shifter": HardwareEntry("shifter", "Atari ST Shifter", "atari", 1985, 4.0, 0.35, "MYTHIC", "Video"),
    "glue": HardwareEntry("glue", "Atari ST GLUE", "atari", 1985, 4.0, 0.35, "MYTHIC", "Bus controller"),
    "mmu": HardwareEntry("mmu", "Atari ST MMU", "atari", 1985, 4.0, 0.35, "MYTHIC", "Memory management"),
    "blitter": HardwareEntry("blitter", "Atari ST BLiTTER", "atari", 1987, 4.0, 0.4, "MYTHIC", "STE/Mega ST"),
    "videl": HardwareEntry("videl", "Atari Falcon VIDEL", "atari", 1992, 4.0, 0.5, "MYTHIC", "Falcon030 only"),
    "dsp56001": HardwareEntry("dsp56001", "Motorola DSP56001", "atari", 1992, 4.0, 0.5, "MYTHIC", "Falcon030 DSP"),

    # ============ COMMODORE 64/128 (MYTHIC) ============
    "vic_ii": HardwareEntry("vic_ii", "MOS 6569 VIC-II (PAL)", "c64", 1982, 4.0, 0.25, "MYTHIC", "C64 video"),
    "vic_ii_ntsc": HardwareEntry("vic_ii_ntsc", "MOS 6567 VIC-II (NTSC)", "c64", 1982, 4.0, 0.25, "MYTHIC"),
    "sid_6581": HardwareEntry("sid_6581", "MOS 6581 SID", "c64", 1982, 4.0, 0.3, "MYTHIC", "C64 sound"),
    "sid_8580": HardwareEntry("sid_8580", "MOS 8580 SID", "c64", 1986, 4.0, 0.35, "MYTHIC", "C64C sound"),
    "cia_6526": HardwareEntry("cia_6526", "MOS 6526 CIA", "c64", 1982, 4.0, 0.25, "MYTHIC", "I/O"),
    "pla_906114": HardwareEntry("pla_906114", "MOS 906114-01 PLA", "c64", 1982, 4.0, 0.3, "MYTHIC"),
    "vdc_8563": HardwareEntry("vdc_8563", "MOS 8563 VDC", "c64", 1985, 4.0, 0.45, "MYTHIC", "C128 80-col"),
    "mmu_8722": HardwareEntry("mmu_8722", "MOS 8722 MMU", "c64", 1985, 4.0, 0.45, "MYTHIC", "C128 only"),

    # ============ APPLE II (MYTHIC) ============
    "iou": HardwareEntry("iou", "Apple IOU", "apple2", 1977, 4.0, 0.4, "MYTHIC", "I/O controller"),
    "mmu_apple2": HardwareEntry("mmu_apple2", "Apple II MMU", "apple2", 1983, 4.0, 0.4, "MYTHIC", "IIe/IIc"),
    "iigs_mega2": HardwareEntry("iigs_mega2", "Apple IIgs Mega II", "apple2", 1986, 4.0, 0.5, "MYTHIC", "IIgs"),
    "iigs_fpi": HardwareEntry("iigs_fpi", "Apple IIgs FPI", "apple2", 1986, 4.0, 0.5, "MYTHIC"),

    # ============ RARE/OBSCURE SYSTEMS (HIGH BONUS) ============
    # Sinclair ZX Spectrum
    "ula_spectrum": HardwareEntry("ula_spectrum", "Ferranti ULA", "spectrum", 1982, 4.0, 0.35, "MYTHIC", "ZX Spectrum"),

    # BBC Micro
    "bbc_video_ula": HardwareEntry("bbc_video_ula", "BBC Video ULA", "bbc", 1981, 4.0, 0.5, "MYTHIC"),

    # MSX
    "v9938": HardwareEntry("v9938", "Yamaha V9938 VDP", "msx", 1985, 4.0, 0.4, "MYTHIC", "MSX2"),
    "v9958": HardwareEntry("v9958", "Yamaha V9958 VDP", "msx", 1988, 4.0, 0.45, "MYTHIC", "MSX2+"),

    # TI-99/4A
    "tms9900": HardwareEntry("tms9900", "TI TMS9900", "ti99", 1976, 4.0, 0.6, "MYTHIC", "16-bit!"),
    "tms9918a": HardwareEntry("tms9918a", "TI TMS9918A VDP", "ti99", 1979, 4.0, 0.5, "MYTHIC"),

    # Tandy/Radio Shack
    "coco_sam": HardwareEntry("coco_sam", "TRS-80 CoCo SAM", "tandy", 1980, 4.0, 0.5, "MYTHIC"),
    "gime": HardwareEntry("gime", "GIME (CoCo 3)", "tandy", 1986, 4.0, 0.55, "MYTHIC", "Rare"),

    # Acorn Archimedes
    "vidc1": HardwareEntry("vidc1", "ARM VIDC1", "acorn", 1987, 4.0, 0.6, "MYTHIC", "Archimedes"),
    "memc1": HardwareEntry("memc1", "ARM MEMC1", "acorn", 1987, 4.0, 0.6, "MYTHIC"),
    "ioc": HardwareEntry("ioc", "ARM IOC", "acorn", 1987, 4.0, 0.6, "MYTHIC"),
}

# =============================================================================
# WORKSTATION/SERVER PROCESSORS (SPARC, PA-RISC, Alpha, MIPS)
# =============================================================================

WORKSTATION_DATABASE: Dict[str, HardwareEntry] = {
    # ============ DEC ALPHA (LEGENDARY) ============
    "ev4": HardwareEntry("ev4", "DEC Alpha 21064 (EV4)", "alpha", 1992, 3.0, 0.5, "LEGENDARY", "First Alpha"),
    "ev45": HardwareEntry("ev45", "DEC Alpha 21064A (EV45)", "alpha", 1994, 3.0, 0.45, "LEGENDARY"),
    "ev5": HardwareEntry("ev5", "DEC Alpha 21164 (EV5)", "alpha", 1995, 3.0, 0.4, "LEGENDARY"),
    "ev56": HardwareEntry("ev56", "DEC Alpha 21164A (EV56)", "alpha", 1996, 3.0, 0.35, "LEGENDARY"),
    "pca56": HardwareEntry("pca56", "DEC Alpha 21164PC (PCA56)", "alpha", 1997, 3.0, 0.4, "LEGENDARY", "Low cost"),
    "ev6": HardwareEntry("ev6", "DEC Alpha 21264 (EV6)", "alpha", 1998, 3.0, 0.35, "LEGENDARY"),
    "ev67": HardwareEntry("ev67", "DEC Alpha 21264A (EV67)", "alpha", 1999, 3.0, 0.3, "LEGENDARY"),
    "ev68": HardwareEntry("ev68", "DEC Alpha 21264C (EV68)", "alpha", 2001, 3.0, 0.35, "LEGENDARY"),
    "ev7": HardwareEntry("ev7", "DEC Alpha 21364 (EV7)", "alpha", 2003, 3.0, 0.5, "LEGENDARY", "Final Alpha"),
    "alpha": HardwareEntry("alpha", "DEC Alpha", "alpha", 1992, 3.0, 0.4, "LEGENDARY"),

    # ============ SUN SPARC (LEGENDARY) ============
    "sparc_v7": HardwareEntry("sparc_v7", "SPARC V7", "sparc", 1987, 3.0, 0.5, "LEGENDARY", "Sun-4"),
    "sparc_v8": HardwareEntry("sparc_v8", "SPARC V8 (SuperSPARC)", "sparc", 1992, 3.0, 0.4, "LEGENDARY"),
    "ultrasparc_i": HardwareEntry("ultrasparc_i", "UltraSPARC I", "sparc", 1995, 3.0, 0.35, "LEGENDARY"),
    "ultrasparc_ii": HardwareEntry("ultrasparc_ii", "UltraSPARC II", "sparc", 1997, 3.0, 0.3, "LEGENDARY"),
    "ultrasparc_iii": HardwareEntry("ultrasparc_iii", "UltraSPARC III", "sparc", 2001, 2.5, 0.3, "ANCIENT"),
    "ultrasparc_iv": HardwareEntry("ultrasparc_iv", "UltraSPARC IV", "sparc", 2004, 2.5, 0.25, "ANCIENT"),
    "sparc64": HardwareEntry("sparc64", "Fujitsu SPARC64", "sparc", 1995, 3.0, 0.4, "LEGENDARY"),
    "sparc": HardwareEntry("sparc", "SPARC", "sparc", 1987, 3.0, 0.4, "LEGENDARY"),

    # ============ HP PA-RISC (LEGENDARY) ============
    "pa7000": HardwareEntry("pa7000", "HP PA-7000", "parisc", 1991, 3.0, 0.5, "LEGENDARY"),
    "pa7100": HardwareEntry("pa7100", "HP PA-7100", "parisc", 1992, 3.0, 0.45, "LEGENDARY"),
    "pa7200": HardwareEntry("pa7200", "HP PA-7200", "parisc", 1994, 3.0, 0.4, "LEGENDARY"),
    "pa8000": HardwareEntry("pa8000", "HP PA-8000", "parisc", 1996, 3.0, 0.35, "LEGENDARY"),
    "pa8200": HardwareEntry("pa8200", "HP PA-8200", "parisc", 1997, 3.0, 0.35, "LEGENDARY"),
    "pa8500": HardwareEntry("pa8500", "HP PA-8500", "parisc", 1998, 3.0, 0.35, "LEGENDARY"),
    "pa8600": HardwareEntry("pa8600", "HP PA-8600", "parisc", 2000, 2.5, 0.35, "ANCIENT"),
    "pa8700": HardwareEntry("pa8700", "HP PA-8700", "parisc", 2001, 2.5, 0.35, "ANCIENT"),
    "pa8800": HardwareEntry("pa8800", "HP PA-8800", "parisc", 2003, 2.5, 0.4, "ANCIENT", "Final PA-RISC"),
    "parisc": HardwareEntry("parisc", "HP PA-RISC", "parisc", 1986, 3.0, 0.4, "LEGENDARY"),

    # ============ SGI MIPS (LEGENDARY) ============
    "r2000": HardwareEntry("r2000", "MIPS R2000", "mips", 1985, 3.5, 0.5, "LEGENDARY", "First MIPS"),
    "r3000": HardwareEntry("r3000", "MIPS R3000", "mips", 1988, 3.5, 0.45, "LEGENDARY"),
    "r4000": HardwareEntry("r4000", "MIPS R4000", "mips", 1991, 3.0, 0.4, "LEGENDARY", "64-bit"),
    "r4400": HardwareEntry("r4400", "MIPS R4400", "mips", 1992, 3.0, 0.35, "LEGENDARY"),
    "r4600": HardwareEntry("r4600", "MIPS R4600 Orion", "mips", 1994, 3.0, 0.3, "LEGENDARY"),
    "r5000": HardwareEntry("r5000", "MIPS R5000", "mips", 1996, 3.0, 0.3, "LEGENDARY"),
    "r8000": HardwareEntry("r8000", "MIPS R8000", "mips", 1994, 3.0, 0.5, "LEGENDARY", "Superscalar"),
    "r10000": HardwareEntry("r10000", "MIPS R10000", "mips", 1996, 3.0, 0.35, "LEGENDARY"),
    "r12000": HardwareEntry("r12000", "MIPS R12000", "mips", 1998, 3.0, 0.35, "LEGENDARY"),
    "r14000": HardwareEntry("r14000", "MIPS R14000", "mips", 2001, 2.5, 0.35, "ANCIENT"),
    "r16000": HardwareEntry("r16000", "MIPS R16000", "mips", 2002, 2.5, 0.4, "ANCIENT", "Final SGI MIPS"),
    "mips": HardwareEntry("mips", "MIPS", "mips", 1985, 3.0, 0.4, "LEGENDARY"),

    # ============ IBM mainframes (VERY RARE) ============
    "s390": HardwareEntry("s390", "IBM S/390", "ibm", 1990, 3.0, 0.8, "LEGENDARY", "Mainframe"),
    "z900": HardwareEntry("z900", "IBM zSeries z900", "ibm", 2000, 2.5, 0.6, "ANCIENT"),
    "z990": HardwareEntry("z990", "IBM zSeries z990", "ibm", 2003, 2.5, 0.5, "ANCIENT"),
}

# =============================================================================
# ARM PROCESSORS (Vintage through Modern)
# =============================================================================

ARM_DATABASE: Dict[str, HardwareEntry] = {
    # ============ LEGENDARY TIER (3.0x) - Early ARM ============
    "arm2": HardwareEntry("arm2", "ARM2", "arm", 1987, 4.0, 0.6, "MYTHIC", "Acorn Archimedes"),
    "arm3": HardwareEntry("arm3", "ARM3", "arm", 1989, 4.0, 0.5, "MYTHIC"),
    "arm6": HardwareEntry("arm6", "ARM6/ARM610", "arm", 1992, 3.5, 0.4, "LEGENDARY"),
    "arm7": HardwareEntry("arm7", "ARM7", "arm", 1994, 3.5, 0.3, "LEGENDARY"),
    "arm7tdmi": HardwareEntry("arm7tdmi", "ARM7TDMI", "arm", 1995, 3.5, 0.25, "LEGENDARY", "GBA"),
    "strongarm": HardwareEntry("strongarm", "StrongARM SA-110", "arm", 1996, 3.0, 0.3, "LEGENDARY", "DEC/Intel"),
    "sa1100": HardwareEntry("sa1100", "StrongARM SA-1100", "arm", 1998, 3.0, 0.3, "LEGENDARY", "iPAQ"),
    "xscale": HardwareEntry("xscale", "Intel XScale", "arm", 2000, 2.5, 0.25, "ANCIENT", "PDAs"),

    # ============ ANCIENT TIER (2.0-2.5x) - ARM9/ARM11 ============
    "arm9": HardwareEntry("arm9", "ARM9", "arm", 1998, 2.5, 0.2, "ANCIENT"),
    "arm926ej": HardwareEntry("arm926ej", "ARM926EJ-S", "arm", 2001, 2.5, 0.2, "ANCIENT"),
    "arm11": HardwareEntry("arm11", "ARM11", "arm", 2003, 2.0, 0.15, "ANCIENT", "iPhone 1"),
    "arm1176": HardwareEntry("arm1176", "ARM1176JZF-S", "arm", 2003, 2.0, 0.15, "ANCIENT", "RPi 1"),

    # ============ VINTAGE TIER (1.5x) - Cortex-A ============
    "cortex_a8": HardwareEntry("cortex_a8", "ARM Cortex-A8", "arm", 2005, 1.5, 0.1, "VINTAGE", "iPhone 3GS"),
    "cortex_a9": HardwareEntry("cortex_a9", "ARM Cortex-A9", "arm", 2007, 1.5, 0.05, "VINTAGE"),
    "cortex_a15": HardwareEntry("cortex_a15", "ARM Cortex-A15", "arm", 2010, 1.5, 0.05, "VINTAGE"),

    # ============ PENALTY TIER (0.8x) - Modern ARM ============
    "cortex_a53": HardwareEntry("cortex_a53", "ARM Cortex-A53", "arm", 2012, 1.0, 0.0, "STANDARD"),
    "cortex_a72": HardwareEntry("cortex_a72", "ARM Cortex-A72", "arm", 2015, 0.8, 0.0, "PENALTY"),
    "cortex_a76": HardwareEntry("cortex_a76", "ARM Cortex-A76", "arm", 2018, 0.8, 0.0, "PENALTY"),
    "cortex_x1": HardwareEntry("cortex_x1", "ARM Cortex-X1", "arm", 2020, 0.8, 0.0, "PENALTY"),

    # Apple Silicon (PENALTY)
    "m1": HardwareEntry("m1", "Apple M1", "arm", 2020, 0.8, 0.0, "PENALTY", "Modern ARM"),
    "m1_pro": HardwareEntry("m1_pro", "Apple M1 Pro", "arm", 2021, 0.8, 0.0, "PENALTY"),
    "m1_max": HardwareEntry("m1_max", "Apple M1 Max", "arm", 2021, 0.8, 0.0, "PENALTY"),
    "m1_ultra": HardwareEntry("m1_ultra", "Apple M1 Ultra", "arm", 2022, 0.8, 0.0, "PENALTY"),
    "m2": HardwareEntry("m2", "Apple M2", "arm", 2022, 0.8, 0.0, "PENALTY"),
    "m2_pro": HardwareEntry("m2_pro", "Apple M2 Pro", "arm", 2023, 0.8, 0.0, "PENALTY"),
    "m2_max": HardwareEntry("m2_max", "Apple M2 Max", "arm", 2023, 0.8, 0.0, "PENALTY"),
    "m3": HardwareEntry("m3", "Apple M3", "arm", 2023, 0.8, 0.0, "PENALTY"),
    "m3_pro": HardwareEntry("m3_pro", "Apple M3 Pro", "arm", 2023, 0.8, 0.0, "PENALTY"),
    "m3_max": HardwareEntry("m3_max", "Apple M3 Max", "arm", 2023, 0.8, 0.0, "PENALTY"),
    "apple_silicon": HardwareEntry("apple_silicon", "Apple Silicon", "arm", 2020, 0.8, 0.0, "PENALTY"),
}

# =============================================================================
# VINTAGE GRAPHICS CARDS (BONUS MULTIPLIERS!)
# =============================================================================

GRAPHICS_DATABASE: Dict[str, HardwareEntry] = {
    # ============ MYTHIC/LEGENDARY GRAPHICS ============
    # 3dfx Voodoo (MYTHIC!)
    "voodoo1": HardwareEntry("voodoo1", "3dfx Voodoo Graphics", "gpu", 1996, 0.0, 0.5, "MYTHIC", "First 3D accelerator"),
    "voodoo2": HardwareEntry("voodoo2", "3dfx Voodoo2", "gpu", 1998, 0.0, 0.4, "MYTHIC", "SLI!"),
    "voodoo_banshee": HardwareEntry("voodoo_banshee", "3dfx Voodoo Banshee", "gpu", 1998, 0.0, 0.35, "LEGENDARY"),
    "voodoo3": HardwareEntry("voodoo3", "3dfx Voodoo3", "gpu", 1999, 0.0, 0.3, "LEGENDARY"),
    "voodoo4": HardwareEntry("voodoo4", "3dfx Voodoo4", "gpu", 2000, 0.0, 0.4, "LEGENDARY", "Rare"),
    "voodoo5": HardwareEntry("voodoo5", "3dfx Voodoo5", "gpu", 2000, 0.0, 0.5, "LEGENDARY", "Very rare"),
    "voodoo5_6000": HardwareEntry("voodoo5_6000", "3dfx Voodoo5 6000", "gpu", 2000, 0.0, 0.9, "LEGENDARY", "Extremely rare"),

    # S3 (MYTHIC/LEGENDARY)
    "virge": HardwareEntry("virge", "S3 ViRGE", "gpu", 1995, 0.0, 0.35, "MYTHIC", "First consumer 3D"),
    "virge_dx": HardwareEntry("virge_dx", "S3 ViRGE/DX", "gpu", 1996, 0.0, 0.3, "MYTHIC"),
    "savage3d": HardwareEntry("savage3d", "S3 Savage3D", "gpu", 1998, 0.0, 0.3, "LEGENDARY"),
    "savage4": HardwareEntry("savage4", "S3 Savage4", "gpu", 1999, 0.0, 0.25, "LEGENDARY"),
    "savage2000": HardwareEntry("savage2000", "S3 Savage2000", "gpu", 1999, 0.0, 0.35, "LEGENDARY", "Rare"),

    # ATI Rage (LEGENDARY)
    "rage_pro": HardwareEntry("rage_pro", "ATI Rage Pro", "gpu", 1997, 0.0, 0.25, "LEGENDARY"),
    "rage_128": HardwareEntry("rage_128", "ATI Rage 128", "gpu", 1999, 0.0, 0.2, "LEGENDARY"),
    "rage_fury": HardwareEntry("rage_fury", "ATI Rage Fury MAXX", "gpu", 1999, 0.0, 0.4, "LEGENDARY", "Dual GPU"),
    "radeon_ddr": HardwareEntry("radeon_ddr", "ATI Radeon DDR", "gpu", 2000, 0.0, 0.2, "LEGENDARY"),
    "radeon_7200": HardwareEntry("radeon_7200", "ATI Radeon 7200", "gpu", 2001, 0.0, 0.15, "LEGENDARY"),

    # NVIDIA (LEGENDARY/ANCIENT)
    "riva_128": HardwareEntry("riva_128", "NVIDIA RIVA 128", "gpu", 1997, 0.0, 0.35, "LEGENDARY"),
    "riva_tnt": HardwareEntry("riva_tnt", "NVIDIA RIVA TNT", "gpu", 1998, 0.0, 0.3, "LEGENDARY"),
    "tnt2": HardwareEntry("tnt2", "NVIDIA TNT2", "gpu", 1999, 0.0, 0.25, "LEGENDARY"),
    "geforce_256": HardwareEntry("geforce_256", "NVIDIA GeForce 256", "gpu", 1999, 0.0, 0.25, "LEGENDARY", "First GeForce"),
    "geforce2": HardwareEntry("geforce2", "NVIDIA GeForce2", "gpu", 2000, 0.0, 0.2, "LEGENDARY"),
    "geforce3": HardwareEntry("geforce3", "NVIDIA GeForce3", "gpu", 2001, 0.0, 0.15, "ANCIENT"),
    "geforce4": HardwareEntry("geforce4", "NVIDIA GeForce4", "gpu", 2002, 0.0, 0.15, "ANCIENT"),

    # Matrox (RARE!)
    "millennium": HardwareEntry("millennium", "Matrox Millennium", "gpu", 1995, 0.0, 0.5, "LEGENDARY", "Professional"),
    "mystique": HardwareEntry("mystique", "Matrox Mystique", "gpu", 1996, 0.0, 0.4, "LEGENDARY"),
    "g200": HardwareEntry("g200", "Matrox G200", "gpu", 1998, 0.0, 0.35, "LEGENDARY"),
    "g400": HardwareEntry("g400", "Matrox G400", "gpu", 1999, 0.0, 0.35, "LEGENDARY", "Best 2D"),
    "parhelia": HardwareEntry("parhelia", "Matrox Parhelia", "gpu", 2002, 0.0, 0.5, "LEGENDARY", "Triple-head"),

    # Number Nine (VERY RARE!)
    "imagine_128": HardwareEntry("imagine_128", "Number Nine Imagine 128", "gpu", 1995, 0.0, 0.6, "LEGENDARY", "Very rare"),
    "revolution_3d": HardwareEntry("revolution_3d", "Number Nine Revolution 3D", "gpu", 1997, 0.0, 0.7, "LEGENDARY", "Extremely rare"),
    "revolution_iv": HardwareEntry("revolution_iv", "Number Nine Revolution IV", "gpu", 1998, 0.0, 0.7, "LEGENDARY"),

    # Rendition (MYTHIC - VERY RARE!)
    "verite_v1000": HardwareEntry("verite_v1000", "Rendition Verite V1000", "gpu", 1995, 0.0, 0.7, "MYTHIC", "Extremely rare"),
    "verite_v2100": HardwareEntry("verite_v2100", "Rendition Verite V2100", "gpu", 1997, 0.0, 0.6, "MYTHIC", "Very rare"),
    "verite_v2200": HardwareEntry("verite_v2200", "Rendition Verite V2200", "gpu", 1998, 0.0, 0.6, "MYTHIC", "Very rare"),

    # PowerVR (RARE!)
    "pcx1": HardwareEntry("pcx1", "NEC PowerVR PCX1", "gpu", 1996, 0.0, 0.6, "LEGENDARY", "Tile-based"),
    "pcx2": HardwareEntry("pcx2", "NEC PowerVR PCX2", "gpu", 1997, 0.0, 0.5, "LEGENDARY"),
    "kyro": HardwareEntry("kyro", "PowerVR Kyro", "gpu", 2000, 0.0, 0.4, "LEGENDARY"),
    "kyro_ii": HardwareEntry("kyro_ii", "PowerVR Kyro II", "gpu", 2001, 0.0, 0.35, "LEGENDARY"),
}


# =============================================================================
# HARDWARE LOOKUP FUNCTIONS
# =============================================================================

def normalize_id(hw_id: str) -> str:
    """Normalize hardware ID for lookup"""
    return hw_id.lower().strip().replace(" ", "_").replace("-", "_")

def lookup_hardware(hw_id: str, family: Optional[str] = None) -> Optional[HardwareEntry]:
    """
    Look up hardware by ID with optional family hint.
    Returns the HardwareEntry if found, None otherwise.
    """
    norm_id = normalize_id(hw_id)

    # Try specific databases based on family hint
    databases = []
    if family:
        family_lower = family.lower()
        if "x86" in family_lower or "intel" in family_lower or "amd" in family_lower:
            databases.append(X86_CPUID_DATABASE)
        elif "powerpc" in family_lower or "ppc" in family_lower:
            databases.append(POWERPC_PVR_DATABASE)
        elif "m68k" in family_lower or "68" in family_lower or "motorola" in family_lower:
            databases.append(M68K_DATABASE)
        elif "arm" in family_lower or "apple" in family_lower:
            databases.append(ARM_DATABASE)
        elif any(x in family_lower for x in ["sparc", "alpha", "mips", "parisc", "ibm"]):
            databases.append(WORKSTATION_DATABASE)
        elif any(x in family_lower for x in ["amiga", "atari", "c64", "commodore", "apple2", "spectrum", "msx"]):
            databases.append(CLASSIC_CHIPSET_DATABASE)
        elif any(x in family_lower for x in ["gpu", "voodoo", "geforce", "radeon", "matrox"]):
            databases.append(GRAPHICS_DATABASE)

    # Add all databases as fallback
    databases.extend([
        X86_CPUID_DATABASE,
        POWERPC_PVR_DATABASE,
        M68K_DATABASE,
        ARM_DATABASE,
        WORKSTATION_DATABASE,
        CLASSIC_CHIPSET_DATABASE,
        GRAPHICS_DATABASE,
    ])

    # Search through databases
    for db in databases:
        if norm_id in db:
            return db[norm_id]

        # Try partial matching for common variants
        for key, entry in db.items():
            if norm_id in key or key in norm_id:
                return entry

    return None

def calculate_poa_multiplier(
    device_family: str,
    device_arch: str,
    device_model: Optional[str] = None,
    chipset_ids: Optional[List[str]] = None,
    gpu_id: Optional[str] = None,
) -> Tuple[float, str, float, str]:
    """
    Calculate PoA multiplier based on hardware detection.

    Returns:
        Tuple of (base_multiplier, tier_name, rarity_bonus, hardware_name)
    """
    family_lower = device_family.lower() if device_family else ""
    arch_lower = device_arch.lower() if device_arch else ""
    model_lower = device_model.lower() if device_model else ""

    # Default values
    base_mult = 1.0
    tier = "STANDARD"
    rarity = 0.0
    hw_name = "Unknown Hardware"

    # Try to look up the exact hardware
    entry = None

    # Try arch first
    if device_arch:
        entry = lookup_hardware(device_arch, device_family)

    # Try model if no match
    if not entry and device_model:
        entry = lookup_hardware(device_model, device_family)

    # Try chipset IDs
    if not entry and chipset_ids:
        for chip_id in chipset_ids:
            entry = lookup_hardware(chip_id, device_family)
            if entry:
                break

    # If found in database, use those values
    if entry:
        base_mult = entry.base_multiplier
        tier = entry.tier
        rarity = entry.rarity_bonus
        hw_name = entry.name
    else:
        # Fallback to family-based detection
        if "m68k" in family_lower or "68" in arch_lower or "motorola" in family_lower:
            base_mult, tier, rarity, hw_name = 4.0, "MYTHIC", 0.2, "Motorola 68K"
        elif "amiga" in family_lower or "amiga" in arch_lower:
            base_mult, tier, rarity, hw_name = 4.0, "MYTHIC", 0.3, "Amiga"
        elif "atari" in family_lower or "atari" in arch_lower:
            base_mult, tier, rarity, hw_name = 4.0, "MYTHIC", 0.35, "Atari ST"
        elif "c64" in family_lower or "commodore" in family_lower:
            base_mult, tier, rarity, hw_name = 4.0, "MYTHIC", 0.25, "Commodore 64"
        elif "386" in arch_lower or "i386" in arch_lower:
            base_mult, tier, rarity, hw_name = 4.0, "MYTHIC", 0.3, "Intel 386"
        elif "286" in arch_lower:
            base_mult, tier, rarity, hw_name = 4.0, "MYTHIC", 0.4, "Intel 286"
        elif "486" in arch_lower or "i486" in arch_lower:
            base_mult, tier, rarity, hw_name = 3.8, "LEGENDARY", 0.2, "Intel 486"
        elif "pentium" in arch_lower and any(x in arch_lower for x in ["mmx", "p5", "p54", "p55", " 1", "_1"]):
            base_mult, tier, rarity, hw_name = 3.5, "LEGENDARY", 0.15, "Pentium 1"
        elif "pentium" in arch_lower and any(x in arch_lower for x in [" 2", "_2", "ii", "klamath", "deschutes"]):
            base_mult, tier, rarity, hw_name = 3.2, "LEGENDARY", 0.1, "Pentium II"
        elif "pentium" in arch_lower and any(x in arch_lower for x in [" 3", "_3", "iii", "katmai", "coppermine"]):
            base_mult, tier, rarity, hw_name = 3.0, "LEGENDARY", 0.1, "Pentium III"
        elif "pentium" in arch_lower and any(x in arch_lower for x in [" 4", "_4", "iv", "willamette", "northwood"]):
            base_mult, tier, rarity, hw_name = 2.5, "ANCIENT", 0.05, "Pentium 4"
        elif "powerpc" in family_lower or "ppc" in family_lower:
            if "601" in arch_lower:
                base_mult, tier, rarity, hw_name = 4.0, "MYTHIC", 0.4, "PowerPC 601"
            elif "603" in arch_lower or "604" in arch_lower:
                base_mult, tier, rarity, hw_name = 3.5, "LEGENDARY", 0.15, "PowerPC 603/604"
            elif "g3" in arch_lower or "750" in arch_lower:
                base_mult, tier, rarity, hw_name = 3.2, "LEGENDARY", 0.1, "PowerPC G3"
            elif "g4" in arch_lower or "74" in arch_lower:
                base_mult, tier, rarity, hw_name = 2.5, "ANCIENT", 0.1, "PowerPC G4"
            elif "g5" in arch_lower or "970" in arch_lower:
                base_mult, tier, rarity, hw_name = 2.0, "ANCIENT", 0.1, "PowerPC G5"
            else:
                base_mult, tier, rarity, hw_name = 3.0, "LEGENDARY", 0.2, "PowerPC"
        elif "alpha" in family_lower:
            base_mult, tier, rarity, hw_name = 3.0, "LEGENDARY", 0.4, "DEC Alpha"
        elif "sparc" in family_lower:
            base_mult, tier, rarity, hw_name = 3.0, "LEGENDARY", 0.4, "SPARC"
        elif "mips" in family_lower:
            base_mult, tier, rarity, hw_name = 3.0, "LEGENDARY", 0.4, "MIPS"
        elif "parisc" in family_lower or "pa-risc" in family_lower:
            base_mult, tier, rarity, hw_name = 3.0, "LEGENDARY", 0.4, "PA-RISC"
        elif "core2" in arch_lower or "core 2" in arch_lower:
            base_mult, tier, rarity, hw_name = 1.5, "VINTAGE", 0.05, "Core 2"
        elif "core" in arch_lower and "duo" in arch_lower:
            base_mult, tier, rarity, hw_name = 2.0, "ANCIENT", 0.1, "Core Duo"
        elif any(x in arch_lower for x in ["m1", "m2", "m3", "apple_silicon", "apple silicon"]):
            base_mult, tier, rarity, hw_name = 0.8, "PENALTY", 0.0, "Apple Silicon"
        elif "arm" in family_lower and any(x in arch_lower for x in ["aarch64", "armv8", "cortex-a7"]):
            base_mult, tier, rarity, hw_name = 0.8, "PENALTY", 0.0, "Modern ARM"
        elif any(x in arch_lower for x in ["ryzen", "zen", "skylake", "alder", "raptor"]):
            base_mult, tier, rarity, hw_name = 0.8, "PENALTY", 0.0, "Modern x86-64"

    # Check for GPU bonus
    if gpu_id:
        gpu_entry = lookup_hardware(gpu_id, "gpu")
        if gpu_entry and gpu_entry.rarity_bonus > 0:
            rarity += gpu_entry.rarity_bonus * 0.5  # 50% of GPU rarity bonus added

    return (base_mult, tier, rarity, hw_name)

def get_total_multiplier(base_mult: float, rarity_bonus: float) -> float:
    """Calculate total multiplier including rarity bonus"""
    return base_mult + (base_mult * rarity_bonus)


# =============================================================================
# CONVENIENCE FUNCTIONS FOR RIP SERVICE
# =============================================================================

def get_poa_info_for_miner(signals: dict) -> dict:
    """
    Process miner attestation signals and return PoA info.

    Args:
        signals: Dict containing device info from attestation

    Returns:
        Dict with multiplier info for database storage
    """
    device = signals.get("device", {})
    device_family = device.get("family", signals.get("device_family", ""))
    device_arch = device.get("arch", signals.get("device_arch", ""))
    device_model = device.get("model", signals.get("device_model", ""))

    # Get chipset IDs if available
    chipset_ids = []
    if "chipset" in signals:
        chipset_ids.append(signals["chipset"])
    if "pci_ids" in signals:
        chipset_ids.extend(signals["pci_ids"])
    if "cpu_id" in signals:
        chipset_ids.append(signals["cpu_id"])

    # Get GPU ID if available
    gpu_id = signals.get("gpu", signals.get("gpu_id"))

    base_mult, tier, rarity, hw_name = calculate_poa_multiplier(
        device_family, device_arch, device_model, chipset_ids, gpu_id
    )

    total_mult = get_total_multiplier(base_mult, rarity)

    return {
        "antiquity_multiplier": round(total_mult, 2),
        "base_multiplier": base_mult,
        "rarity_bonus": round(rarity, 3),
        "tier": tier,
        "hardware_type": hw_name,
        "device_family": device_family,
        "device_arch": device_arch,
    }


# =============================================================================
# STATISTICS AND REPORTING
# =============================================================================

def get_database_stats() -> dict:
    """Get statistics about the hardware database"""
    all_dbs = {
        "x86": X86_CPUID_DATABASE,
        "powerpc": POWERPC_PVR_DATABASE,
        "m68k": M68K_DATABASE,
        "classic": CLASSIC_CHIPSET_DATABASE,
        "workstation": WORKSTATION_DATABASE,
        "arm": ARM_DATABASE,
        "graphics": GRAPHICS_DATABASE,
    }

    stats = {
        "total_entries": 0,
        "by_family": {},
        "by_tier": {
            "MYTHIC": 0,
            "LEGENDARY": 0,
            "ANCIENT": 0,
            "VINTAGE": 0,
            "STANDARD": 0,
            "PENALTY": 0,
        },
        "rarest_hardware": [],
    }

    all_entries = []
    for db_name, db in all_dbs.items():
        stats["by_family"][db_name] = len(db)
        stats["total_entries"] += len(db)

        for entry in db.values():
            stats["by_tier"][entry.tier] += 1
            all_entries.append(entry)

    # Find rarest hardware (highest rarity bonus)
    all_entries.sort(key=lambda x: x.rarity_bonus, reverse=True)
    stats["rarest_hardware"] = [
        {"name": e.name, "rarity": e.rarity_bonus, "tier": e.tier}
        for e in all_entries[:20]
    ]

    return stats


if __name__ == "__main__":
    # Print database statistics
    stats = get_database_stats()
    print("=" * 60)
    print("RustChain PoA Hardware Database Statistics")
    print("=" * 60)
    print(f"\nTotal hardware entries: {stats['total_entries']}")
    print("\nBy family:")
    for family, count in stats['by_family'].items():
        print(f"  {family:15} {count:4} entries")
    print("\nBy tier:")
    for tier, count in stats['by_tier'].items():
        print(f"  {tier:12} {count:4} entries")
    print("\nTop 10 rarest hardware (highest bonus):")
    for i, hw in enumerate(stats['rarest_hardware'][:10], 1):
        print(f"  {i:2}. {hw['name']:35} +{hw['rarity']*100:.0f}% ({hw['tier']})")

    # Test some lookups
    print("\n" + "=" * 60)
    print("Test Lookups")
    print("=" * 60)

    test_cases = [
        ("PowerPC", "G4"),
        ("x86", "486"),
        ("x86", "Pentium"),
        ("m68k", "68030"),
        ("powerpc", "601"),
        ("arm", "m1"),
        ("x86", "ryzen"),
    ]

    for family, arch in test_cases:
        base, tier, rarity, name = calculate_poa_multiplier(family, arch)
        total = get_total_multiplier(base, rarity)
        print(f"\n{family}/{arch}:")
        print(f"  Hardware: {name}")
        print(f"  Tier: {tier}")
        print(f"  Base: {base}x, Rarity: +{rarity*100:.0f}%, Total: {total:.2f}x")
