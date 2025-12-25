#!/usr/bin/env python3
"""
Vintage CPU Architecture Detection for RustChain RIP-200
========================================================

Extremely old CPU architectures with high antiquity multipliers.
Incentivizes preservation of vintage computing hardware (1980s-2000s).

Research Sources:
- Intel Architecture History: https://en.wikipedia.org/wiki/List_of_Intel_processors
- Motorola 68K Family: https://en.wikipedia.org/wiki/Motorola_68000_series
- Cyrix CPUs: https://en.wikipedia.org/wiki/Cyrix
- VIA CPUs: https://en.wikipedia.org/wiki/VIA_Technologies
- AMD K5/K6: https://en.wikipedia.org/wiki/AMD_K5
- Transmeta: https://en.wikipedia.org/wiki/Transmeta
- DEC Alpha: https://en.wikipedia.org/wiki/DEC_Alpha
- Sun SPARC: https://en.wikipedia.org/wiki/SPARC
- MIPS: https://en.wikipedia.org/wiki/MIPS_architecture
- PA-RISC: https://en.wikipedia.org/wiki/PA-RISC
- PowerPC Amiga: https://en.wikipedia.org/wiki/AmigaOne
"""

import re
from typing import Tuple


# =============================================================================
# PRE-PENTIUM 4 INTEL x86 (1985-2003)
# =============================================================================

VINTAGE_INTEL_X86 = {
    # 386 Era (1985-1994) - Ancient x86
    "i386": {
        "years": (1985, 1994),
        "patterns": [
            r"i386",
            r"Intel 386",
            r"80386",
            r"Intel.*386",
        ],
        "base_multiplier": 3.0,  # Maximum antiquity bonus
        "description": "Intel 80386 (Ancient x86)"
    },

    # 486 Era (1989-1997) - Early x86
    "i486": {
        "years": (1989, 1997),
        "patterns": [
            r"i486",
            r"Intel 486",
            r"80486",
            r"Intel.*486",
            r"486DX",
            r"486DX2",
            r"486DX4",
            r"486SX",
        ],
        "base_multiplier": 2.8,
        "description": "Intel 80486 (Early x86)"
    },

    # Pentium (P5) Era (1993-1999) - Original Pentium
    "pentium_p5": {
        "years": (1993, 1999),
        "patterns": [
            r"Pentium\(R\)$",  # Original Pentium (no suffix)
            r"Pentium MMX",
            r"Intel.*Pentium\s+60",
            r"Intel.*Pentium\s+66",
            r"Intel.*Pentium\s+75",
            r"Intel.*Pentium\s+90",
            r"Intel.*Pentium\s+100",
            r"Intel.*Pentium\s+120",
            r"Intel.*Pentium\s+133",
            r"Intel.*Pentium\s+150",
            r"Intel.*Pentium\s+166",
            r"Intel.*Pentium\s+200",
            r"Intel.*Pentium\s+233",
        ],
        "base_multiplier": 2.6,
        "description": "Intel Pentium P5/MMX (1st-gen Pentium)"
    },

    # Pentium Pro Era (1995-1998)
    "pentium_pro": {
        "years": (1995, 1998),
        "patterns": [
            r"Pentium\(R\) Pro",
            r"Pentium Pro",
            r"PPro",
        ],
        "base_multiplier": 2.4,
        "description": "Intel Pentium Pro (P6 architecture)"
    },

    # Pentium II Era (1997-1999)
    "pentium_ii": {
        "years": (1997, 1999),
        "patterns": [
            r"Pentium\(R\) II",
            r"Pentium II",
            r"Celeron.*[23]\d{2}MHz",  # Early Celeron (Mendocino)
        ],
        "base_multiplier": 2.2,
        "description": "Intel Pentium II (Klamath/Deschutes)"
    },

    # Pentium III Era (1999-2003)
    "pentium_iii": {
        "years": (1999, 2003),
        "patterns": [
            r"Pentium\(R\) III",
            r"Pentium III",
            r"PIII",
            r"Celeron.*[456789]\d{2}MHz",  # Later Celeron (Coppermine)
        ],
        "base_multiplier": 2.0,
        "description": "Intel Pentium III (Katmai/Coppermine/Tualatin)"
    },
}


# =============================================================================
# ODDBALL x86 VENDORS (1990s-2000s)
# =============================================================================

ODDBALL_X86_VENDORS = {
    # Cyrix CPUs (1992-1999)
    "cyrix_6x86": {
        "years": (1995, 1999),
        "patterns": [
            r"Cyrix 6x86",
            r"Cyrix.*6x86",
            r"6x86MX",
            r"Cyrix MII",
            r"Cyrix MediaGX",
            r"Cyrix.*M[I]{1,2}",
        ],
        "base_multiplier": 2.5,
        "description": "Cyrix 6x86/MII/MediaGX (Pentium competitor)"
    },

    # VIA CPUs (2001-2011)
    "via_c3": {
        "years": (2001, 2005),
        "patterns": [
            r"VIA C3",
            r"VIA.*C3",
            r"Samuel",
            r"Ezra",
        ],
        "base_multiplier": 1.9,
        "description": "VIA C3 (Low-power x86)"
    },
    "via_c7": {
        "years": (2005, 2011),
        "patterns": [
            r"VIA C7",
            r"VIA.*C7",
            r"Esther",
        ],
        "base_multiplier": 1.8,
        "description": "VIA C7 (Enhanced low-power)"
    },
    "via_nano": {
        "years": (2008, 2011),
        "patterns": [
            r"VIA Nano",
            r"VIA.*Nano",
            r"Isaiah",
        ],
        "base_multiplier": 1.7,
        "description": "VIA Nano (Isaiah microarchitecture)"
    },

    # Transmeta (2000-2007) - Software x86 emulation
    "transmeta_crusoe": {
        "years": (2000, 2004),
        "patterns": [
            r"Transmeta Crusoe",
            r"Crusoe",
            r"TM\d{4}",  # TM5400, TM5800, etc.
        ],
        "base_multiplier": 2.1,
        "description": "Transmeta Crusoe (Code morphing)"
    },
    "transmeta_efficeon": {
        "years": (2004, 2007),
        "patterns": [
            r"Transmeta Efficeon",
            r"Efficeon",
            r"TM8\d{3}",  # TM8600, TM8800
        ],
        "base_multiplier": 2.0,
        "description": "Transmeta Efficeon (2nd-gen code morphing)"
    },

    # IDT WinChip (1997-2001)
    "winchip": {
        "years": (1997, 2001),
        "patterns": [
            r"WinChip",
            r"IDT.*WinChip",
            r"Centaur.*WinChip",
            r"WinChip [C234]",
        ],
        "base_multiplier": 2.3,
        "description": "IDT/Centaur WinChip (Budget x86)"
    },
}


# =============================================================================
# VINTAGE AMD x86 (Pre-K7)
# =============================================================================

VINTAGE_AMD_X86 = {
    # AMD K5 (1996-1997) - First AMD x86
    "k5": {
        "years": (1996, 1997),
        "patterns": [
            r"AMD-K5",
            r"AMD K5",
            r"K5-PR\d{2,3}",  # K5-PR75, K5-PR100, etc.
        ],
        "base_multiplier": 2.4,
        "description": "AMD K5 (Original AMD x86)"
    },

    # AMD K6 (1997-1999) - K6/K6-2/K6-III
    "k6": {
        "years": (1997, 1999),
        "patterns": [
            r"AMD-K6",
            r"AMD K6\(",
            r"K6-2",
            r"K6-III",
            r"K6/2",
            r"K6/3",
        ],
        "base_multiplier": 2.2,
        "description": "AMD K6/K6-2/K6-III (3DNow! era)"
    },
}


# =============================================================================
# MOTOROLA 68K FAMILY (Mac and Amiga) (1979-1994)
# =============================================================================

MOTOROLA_68K = {
    # 68000 (1979-1990) - Original Mac, Amiga 500/1000
    "m68000": {
        "years": (1979, 1990),
        "patterns": [
            r"68000",
            r"MC68000",
            r"m68000",
            r"Motorola 68000",
        ],
        "base_multiplier": 3.0,  # Maximum antiquity
        "description": "Motorola 68000 (16-bit, original Mac/Amiga)"
    },

    # 68010 (1982-1988) - Minor update to 68000
    "m68010": {
        "years": (1982, 1988),
        "patterns": [
            r"68010",
            r"MC68010",
            r"m68010",
        ],
        "base_multiplier": 2.9,
        "description": "Motorola 68010 (Enhanced 68000)"
    },

    # 68020 (1984-1990) - Mac II, Amiga 1200
    "m68020": {
        "years": (1984, 1990),
        "patterns": [
            r"68020",
            r"MC68020",
            r"m68020",
            r"Motorola 68020",
        ],
        "base_multiplier": 2.8,
        "description": "Motorola 68020 (32-bit, Mac II era)"
    },

    # 68030 (1987-1994) - Mac IIx, SE/30, Amiga 3000
    "m68030": {
        "years": (1987, 1994),
        "patterns": [
            r"68030",
            r"MC68030",
            r"m68030",
            r"Motorola 68030",
        ],
        "base_multiplier": 2.6,
        "description": "Motorola 68030 (Mac IIx/SE/30, Amiga 3000)"
    },

    # 68040 (1990-1996) - Quadra, Amiga 4000
    "m68040": {
        "years": (1990, 1996),
        "patterns": [
            r"68040",
            r"MC68040",
            r"m68040",
            r"Motorola 68040",
            r"68LC040",  # Low-cost variant (no FPU)
        ],
        "base_multiplier": 2.4,
        "description": "Motorola 68040 (Quadra, Amiga 4000)"
    },

    # 68060 (1994-2000) - Amiga accelerators, rare Macs
    "m68060": {
        "years": (1994, 2000),
        "patterns": [
            r"68060",
            r"MC68060",
            r"m68060",
            r"Motorola 68060",
            r"68LC060",
        ],
        "base_multiplier": 2.2,
        "description": "Motorola 68060 (Final 68K, Amiga accelerators)"
    },
}


# =============================================================================
# POWERPC AMIGA (2002-2012) - AmigaOne, Pegasos, Sam440/460
# =============================================================================

POWERPC_AMIGA = {
    # AmigaOne G3/G4 (2002-2005)
    "amigaone_g3": {
        "years": (2002, 2005),
        "patterns": [
            r"AmigaOne.*G3",
            r"AmigaOne.*750",
            r"AmigaOne.*745\d",
        ],
        "base_multiplier": 2.4,
        "description": "AmigaOne G3 (PowerPC 750/7457)"
    },
    "amigaone_g4": {
        "years": (2003, 2006),
        "patterns": [
            r"AmigaOne.*G4",
            r"AmigaOne.*7450",
            r"AmigaOne.*7447",
        ],
        "base_multiplier": 2.3,
        "description": "AmigaOne G4 (PowerPC 7450/7447)"
    },

    # Pegasos I/II (2002-2006)
    "pegasos_g3": {
        "years": (2002, 2004),
        "patterns": [
            r"Pegasos.*G3",
            r"Pegasos I",
        ],
        "base_multiplier": 2.3,
        "description": "Pegasos I (PowerPC G3)"
    },
    "pegasos_g4": {
        "years": (2004, 2006),
        "patterns": [
            r"Pegasos.*G4",
            r"Pegasos II",
        ],
        "base_multiplier": 2.2,
        "description": "Pegasos II (PowerPC G4)"
    },

    # Sam440/460 (2007-2012) - Modern AmigaOS 4 hardware
    "sam440": {
        "years": (2007, 2010),
        "patterns": [
            r"Sam440",
            r"440EP",
            r"PPC440EP",
        ],
        "base_multiplier": 2.0,
        "description": "Sam440 (PowerPC 440EP embedded)"
    },
    "sam460": {
        "years": (2010, 2012),
        "patterns": [
            r"Sam460",
            r"460EX",
            r"PPC460EX",
        ],
        "base_multiplier": 1.9,
        "description": "Sam460 (PowerPC 460EX embedded)"
    },
}


# =============================================================================
# RISC WORKSTATION ARCHITECTURES (1990s-2000s)
# =============================================================================

RISC_WORKSTATIONS = {
    # DEC Alpha (1992-2004) - Fastest CPU of the 1990s
    "alpha_21064": {
        "years": (1992, 1995),
        "patterns": [
            r"Alpha 21064",
            r"EV4",
            r"DECchip 21064",
        ],
        "base_multiplier": 2.7,
        "description": "DEC Alpha 21064 (EV4, original Alpha)"
    },
    "alpha_21164": {
        "years": (1995, 1998),
        "patterns": [
            r"Alpha 21164",
            r"EV5",
            r"EV56",
            r"DECchip 21164",
        ],
        "base_multiplier": 2.5,
        "description": "DEC Alpha 21164 (EV5/EV56)"
    },
    "alpha_21264": {
        "years": (1998, 2004),
        "patterns": [
            r"Alpha 21264",
            r"EV6",
            r"EV67",
            r"EV68",
            r"DECchip 21264",
        ],
        "base_multiplier": 2.3,
        "description": "DEC Alpha 21264 (EV6/EV67/EV68, final Alpha)"
    },

    # Sun SPARC (1987-2017)
    "sparc_v7": {
        "years": (1987, 1992),
        "patterns": [
            r"SPARC v7",
            r"MB86900",
            r"Cypress 7C601",
        ],
        "base_multiplier": 2.9,
        "description": "SPARC v7 (Original SPARC)"
    },
    "sparc_v8": {
        "years": (1990, 1996),
        "patterns": [
            r"SPARC v8",
            r"microSPARC",
            r"SuperSPARC",
            r"hyperSPARC",
        ],
        "base_multiplier": 2.6,
        "description": "SPARC v8 (MicroSPARC/SuperSPARC)"
    },
    "sparc_v9": {
        "years": (1995, 2005),
        "patterns": [
            r"SPARC v9",
            r"UltraSPARC",
            r"UltraSPARC II",
            r"UltraSPARC III",
        ],
        "base_multiplier": 2.3,
        "description": "SPARC v9 (UltraSPARC era)"
    },
    "sparc_t1": {
        "years": (2005, 2010),
        "patterns": [
            r"UltraSPARC T1",
            r"Niagara",
        ],
        "base_multiplier": 1.9,
        "description": "UltraSPARC T1 (Niagara, CMT era)"
    },
    "sparc_t2": {
        "years": (2007, 2011),
        "patterns": [
            r"UltraSPARC T2",
            r"Niagara 2",
        ],
        "base_multiplier": 1.8,
        "description": "UltraSPARC T2 (Niagara 2)"
    },

    # MIPS (1985-2020s) - SGI workstations, embedded
    "mips_r2000": {
        "years": (1985, 1988),
        "patterns": [
            r"R2000",
            r"MIPS R2000",
        ],
        "base_multiplier": 3.0,
        "description": "MIPS R2000 (Original MIPS)"
    },
    "mips_r3000": {
        "years": (1988, 1994),
        "patterns": [
            r"R3000",
            r"MIPS R3000",
        ],
        "base_multiplier": 2.8,
        "description": "MIPS R3000 (PlayStation 1)"
    },
    "mips_r4000": {
        "years": (1991, 1997),
        "patterns": [
            r"R4000",
            r"R4400",
            r"MIPS R4000",
            r"MIPS R4400",
        ],
        "base_multiplier": 2.6,
        "description": "MIPS R4000/R4400 (64-bit SGI era)"
    },
    "mips_r5000": {
        "years": (1996, 2000),
        "patterns": [
            r"R5000",
            r"RM5200",
            r"RM7000",
            r"MIPS R5000",
        ],
        "base_multiplier": 2.3,
        "description": "MIPS R5000/RM7000 (SGI O2/Indy)"
    },
    "mips_r10000": {
        "years": (1996, 2004),
        "patterns": [
            r"R10000",
            r"R12000",
            r"R14000",
            r"R16000",
            r"MIPS R10000",
        ],
        "base_multiplier": 2.4,
        "description": "MIPS R10000 series (SGI Origin/Octane)"
    },

    # HP PA-RISC (1986-2008)
    "pa_risc_1.0": {
        "years": (1986, 1990),
        "patterns": [
            r"PA-RISC 1\.0",
            r"PA7000",
        ],
        "base_multiplier": 2.9,
        "description": "PA-RISC 1.0 (HP 9000)"
    },
    "pa_risc_1.1": {
        "years": (1990, 1996),
        "patterns": [
            r"PA-RISC 1\.1",
            r"PA7100",
            r"PA7200",
        ],
        "base_multiplier": 2.6,
        "description": "PA-RISC 1.1 (HP 9000 Series 700/800)"
    },
    "pa_risc_2.0": {
        "years": (1996, 2008),
        "patterns": [
            r"PA-RISC 2\.0",
            r"PA8000",
            r"PA8200",
            r"PA8500",
            r"PA8600",
            r"PA8700",
            r"PA8800",
            r"PA8900",
        ],
        "base_multiplier": 2.3,
        "description": "PA-RISC 2.0 (64-bit, final generation)"
    },

    # IBM POWER (Pre-POWER8)
    "power1": {
        "years": (1990, 1993),
        "patterns": [
            r"POWER1",
            r"RIOS",
        ],
        "base_multiplier": 2.8,
        "description": "IBM POWER1 (RIOS, original POWER)"
    },
    "power2": {
        "years": (1993, 1996),
        "patterns": [
            r"POWER2",
            r"P2SC",
        ],
        "base_multiplier": 2.6,
        "description": "IBM POWER2 (RS/6000 era)"
    },
    "power3": {
        "years": (1998, 2001),
        "patterns": [
            r"POWER3",
        ],
        "base_multiplier": 2.4,
        "description": "IBM POWER3 (64-bit, pSeries)"
    },
    "power4": {
        "years": (2001, 2004),
        "patterns": [
            r"POWER4",
            r"POWER4\+",
        ],
        "base_multiplier": 2.2,
        "description": "IBM POWER4/4+ (First dual-core)"
    },
    "power5": {
        "years": (2004, 2007),
        "patterns": [
            r"POWER5",
            r"POWER5\+",
        ],
        "base_multiplier": 2.0,
        "description": "IBM POWER5/5+ (SMT, virtualization)"
    },
    "power6": {
        "years": (2007, 2010),
        "patterns": [
            r"POWER6",
        ],
        "base_multiplier": 1.9,
        "description": "IBM POWER6 (High frequency)"
    },
    "power7": {
        "years": (2010, 2013),
        "patterns": [
            r"POWER7",
            r"POWER7\+",
        ],
        "base_multiplier": 1.8,
        "description": "IBM POWER7/7+ (TurboCore)"
    },
}


# =============================================================================
# DETECTION HELPER FUNCTIONS
# =============================================================================

def detect_vintage_architecture(brand_string: str) -> Tuple[str, str, int, float]:
    """
    Detect vintage CPU architecture from brand string

    Returns: (vendor, architecture, year, base_multiplier)

    Checks in order of specificity:
    1. RISC workstations (most distinctive patterns)
    2. Motorola 68K (Mac/Amiga)
    3. PowerPC Amiga
    4. Vintage Intel x86
    5. Oddball x86 vendors
    6. Vintage AMD x86

    Returns None if no vintage architecture detected (use modern detection)
    """
    brand_string = brand_string.strip()

    # Check RISC workstations first (most distinctive)
    for arch_name, arch_info in RISC_WORKSTATIONS.items():
        for pattern in arch_info["patterns"]:
            if re.search(pattern, brand_string, re.IGNORECASE):
                vendor = arch_name.split("_")[0]  # Extract vendor prefix
                return (vendor, arch_name, arch_info["years"][0], arch_info["base_multiplier"])

    # Check Motorola 68K
    for arch_name, arch_info in MOTOROLA_68K.items():
        for pattern in arch_info["patterns"]:
            if re.search(pattern, brand_string, re.IGNORECASE):
                return ("motorola", arch_name, arch_info["years"][0], arch_info["base_multiplier"])

    # Check PowerPC Amiga
    for arch_name, arch_info in POWERPC_AMIGA.items():
        for pattern in arch_info["patterns"]:
            if re.search(pattern, brand_string, re.IGNORECASE):
                return ("powerpc_amiga", arch_name, arch_info["years"][0], arch_info["base_multiplier"])

    # Check vintage Intel x86
    for arch_name, arch_info in VINTAGE_INTEL_X86.items():
        for pattern in arch_info["patterns"]:
            if re.search(pattern, brand_string, re.IGNORECASE):
                return ("intel", arch_name, arch_info["years"][0], arch_info["base_multiplier"])

    # Check oddball x86 vendors
    for arch_name, arch_info in ODDBALL_X86_VENDORS.items():
        for pattern in arch_info["patterns"]:
            if re.search(pattern, brand_string, re.IGNORECASE):
                vendor = arch_name.split("_")[0]  # Extract vendor prefix
                return (vendor, arch_name, arch_info["years"][0], arch_info["base_multiplier"])

    # Check vintage AMD x86
    for arch_name, arch_info in VINTAGE_AMD_X86.items():
        for pattern in arch_info["patterns"]:
            if re.search(pattern, brand_string, re.IGNORECASE):
                return ("amd", arch_name, arch_info["years"][0], arch_info["base_multiplier"])

    # No vintage architecture detected
    return None


def get_vintage_description(architecture: str) -> str:
    """Get human-readable description for vintage architecture"""
    all_archs = {
        **VINTAGE_INTEL_X86,
        **ODDBALL_X86_VENDORS,
        **VINTAGE_AMD_X86,
        **MOTOROLA_68K,
        **POWERPC_AMIGA,
        **RISC_WORKSTATIONS,
    }

    if architecture in all_archs:
        return all_archs[architecture]["description"]

    return "Unknown vintage CPU"


# =============================================================================
# TEST/DEMO CODE
# =============================================================================

def demo_vintage_detection():
    """Demo vintage CPU detection with real-world examples"""
    test_cpus = [
        # Ancient Intel x86
        "Intel 80386DX @ 33MHz",
        "Intel 80486DX2-66",
        "Intel Pentium 200MHz MMX",
        "Intel Pentium Pro 200MHz",
        "Intel Pentium II 450MHz",
        "Intel(R) Pentium(R) III CPU 1000MHz",

        # Oddball x86
        "Cyrix 6x86MX PR200",
        "VIA C3 Samuel 2 800MHz",
        "VIA C7-D 1.5GHz",
        "VIA Nano U2250 1.3GHz",
        "Transmeta Crusoe TM5800",
        "Transmeta Efficeon TM8600",
        "IDT WinChip C6-240",

        # Vintage AMD
        "AMD-K5-PR100",
        "AMD K6-2 350MHz",
        "AMD K6-III 450MHz",

        # Motorola 68K
        "Motorola 68000 @ 8MHz",
        "MC68020 @ 16MHz",
        "MC68030 @ 25MHz",
        "MC68040 @ 33MHz",
        "MC68060 @ 50MHz",

        # PowerPC Amiga
        "AmigaOne G3 750GX @ 800MHz",
        "AmigaOne G4 7447 @ 1GHz",
        "Pegasos II G4",
        "Sam440EP @ 667MHz",
        "Sam460EX @ 1.15GHz",

        # RISC Workstations
        "Alpha 21064 @ 150MHz",
        "Alpha 21164A @ 500MHz",
        "Alpha 21264 @ 667MHz",
        "SPARC v7 @ 20MHz",
        "UltraSPARC @ 143MHz",
        "UltraSPARC II @ 300MHz",
        "UltraSPARC T1 @ 1.2GHz",
        "MIPS R2000 @ 8MHz",
        "MIPS R3000 @ 33MHz",
        "MIPS R4000 @ 100MHz",
        "MIPS R10000 @ 195MHz",
        "PA-RISC 1.0 PA7000",
        "PA-RISC 2.0 PA8500",
        "IBM POWER1 @ 25MHz",
        "IBM POWER2 @ 66MHz",
        "IBM POWER4 @ 1.3GHz",
        "IBM POWER7 @ 3.55GHz",
    ]

    print("=" * 80)
    print("VINTAGE CPU ARCHITECTURE DETECTION DEMO")
    print("=" * 80)
    print()

    for cpu in test_cpus:
        result = detect_vintage_architecture(cpu)
        if result:
            vendor, arch, year, multiplier = result
            desc = get_vintage_description(arch)
            age = 2025 - year
            print(f"CPU: {cpu}")
            print(f"  → Vendor: {vendor.upper()}")
            print(f"  → Architecture: {arch}")
            print(f"  → Description: {desc}")
            print(f"  → Year: {year} (Age: {age} years)")
            print(f"  → Base Antiquity Multiplier: {multiplier}x")
            print()
        else:
            print(f"CPU: {cpu}")
            print(f"  → NOT DETECTED (use modern detection)")
            print()

    # Multiplier ranking
    print("=" * 80)
    print("ANTIQUITY MULTIPLIER RANKING (Highest to Lowest)")
    print("=" * 80)
    print()

    all_archs = []
    for archs_dict in [VINTAGE_INTEL_X86, ODDBALL_X86_VENDORS, VINTAGE_AMD_X86,
                       MOTOROLA_68K, POWERPC_AMIGA, RISC_WORKSTATIONS]:
        for arch_name, arch_info in archs_dict.items():
            all_archs.append((
                arch_info["base_multiplier"],
                arch_info["years"][0],
                arch_name,
                arch_info["description"]
            ))

    # Sort by multiplier (descending), then by year (ascending)
    all_archs.sort(key=lambda x: (-x[0], x[1]))

    for multiplier, year, arch_name, desc in all_archs:
        print(f"{multiplier}x - {year:4d} - {arch_name:20s} - {desc}")


if __name__ == "__main__":
    demo_vintage_detection()
