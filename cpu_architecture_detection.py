#!/usr/bin/env python3
"""
CPU Architecture Detection & Antiquity Multiplier System
=========================================================

Comprehensive CPU generation detection for RustChain RIP-200 antiquity rewards.
Older hardware = higher multipliers to incentivize preservation of vintage systems.

Based on extensive research of Intel and AMD CPU microarchitecture timeline (2000-2025).

Sources:
- Intel CPU Timeline: https://en.wikipedia.org/wiki/List_of_Intel_CPU_microarchitectures
- AMD CPU Timeline: https://en.wikipedia.org/wiki/List_of_AMD_CPU_microarchitectures
- Intel Xeon Generations: https://en.wikipedia.org/wiki/List_of_Intel_Xeon_processors
- AMD EPYC History: https://en.wikipedia.org/wiki/Epyc
"""

import re
from typing import Tuple, Optional, Dict
from dataclasses import dataclass
from datetime import datetime

CURRENT_YEAR = 2025


@dataclass
class CPUInfo:
    """Detected CPU information"""
    brand_string: str
    vendor: str  # "intel" or "amd"
    architecture: str  # e.g., "sandy_bridge", "zen2", "pentium4"
    microarch_year: int  # Year the microarchitecture was released
    model_year: int  # Estimated year this specific model was released
    generation: str  # Human-readable generation name
    is_server: bool  # Server/workstation CPU
    antiquity_multiplier: float  # Final calculated multiplier


# =============================================================================
# INTEL CPU GENERATIONS & MULTIPLIERS
# =============================================================================

INTEL_GENERATIONS = {
    # NetBurst Era (2000-2006) - Pentium 4
    "pentium4": {
        "years": (2000, 2006),
        "patterns": [
            r"Pentium\(R\) 4",
            r"Pentium 4",
            r"P4",
        ],
        "base_multiplier": 1.5,
        "description": "Intel Pentium 4 (NetBurst)"
    },
    "pentium_d": {
        "years": (2005, 2006),
        "patterns": [r"Pentium\(R\) D", r"Pentium D"],
        "base_multiplier": 1.5,
        "description": "Intel Pentium D (Dual-core NetBurst)"
    },

    # Core 2 Era (2006-2008)
    "core2": {
        "years": (2006, 2008),
        "patterns": [
            r"Core\(TM\)2",
            r"Core 2 Duo",
            r"Core 2 Quad",
            r"Core2",
        ],
        "base_multiplier": 1.3,
        "description": "Intel Core 2 Duo/Quad"
    },

    # Nehalem (2008-2010) - First-gen Core i3/i5/i7
    "nehalem": {
        "years": (2008, 2010),
        "patterns": [
            r"Core\(TM\) i[3579]-[789]\d{2}",  # i7-920, i5-750, etc.
            r"Xeon\(R\).*[EWX]55\d{2}",  # Xeon X5570, W5580, etc.
        ],
        "base_multiplier": 1.2,
        "description": "Intel Nehalem (1st-gen Core i)"
    },
    "westmere": {
        "years": (2010, 2011),
        "patterns": [
            r"Core\(TM\) i[3579]-[89]\d{2}",  # i7-980, i5-880, etc.
            r"Xeon\(R\).*[EWX]56\d{2}",  # Xeon X5675, etc.
        ],
        "base_multiplier": 1.2,
        "description": "Intel Westmere (32nm Nehalem)"
    },

    # Sandy Bridge (2011-2012) - 2nd-gen Core i
    "sandy_bridge": {
        "years": (2011, 2012),
        "patterns": [
            r"Core\(TM\) i[3579]-2\d{3}",  # i7-2600K, i5-2500, etc.
            r"Xeon\(R\).*E3-12\d{2}(?!\s*v)",  # E3-1230 (no v-suffix)
            r"Xeon\(R\).*E5-[124]6\d{2}(?!\s*v)",  # E5-1650, E5-2670 (no v-suffix)
        ],
        "base_multiplier": 1.1,
        "description": "Intel Sandy Bridge (2nd-gen Core i)"
    },

    # Ivy Bridge (2012-2013) - 3rd-gen Core i
    "ivy_bridge": {
        "years": (2012, 2013),
        "patterns": [
            r"Core\(TM\) i[3579]-3\d{3}",  # i7-3770K, i5-3570, etc.
            r"Xeon\(R\).*E3-12\d{2}\s*v2",  # E3-1230 v2
            r"Xeon\(R\).*E5-[124]6\d{2}\s*v2",  # E5-1650 v2, E5-2670 v2
            r"Xeon\(R\).*E7-[248]8\d{2}\s*v2",  # E7-4870 v2, E7-8870 v2
        ],
        "base_multiplier": 1.1,
        "description": "Intel Ivy Bridge (3rd-gen Core i)"
    },

    # Haswell (2013-2015) - 4th-gen Core i
    "haswell": {
        "years": (2013, 2015),
        "patterns": [
            r"Core\(TM\) i[3579]-4\d{3}",  # i7-4770K, i5-4590, etc.
            r"Xeon\(R\).*E3-12\d{2}\s*v3",  # E3-1231 v3
            r"Xeon\(R\).*E5-[124]6\d{2}\s*v3",  # E5-1650 v3, E5-2680 v3
            r"Xeon\(R\).*E7-[248]8\d{2}\s*v3",  # E7-4880 v3
        ],
        "base_multiplier": 1.1,
        "description": "Intel Haswell (4th-gen Core i)"
    },

    # Broadwell (2014-2015) - 5th-gen Core i
    "broadwell": {
        "years": (2014, 2015),
        "patterns": [
            r"Core\(TM\) i[3579]-5\d{3}",  # i7-5775C, i5-5675C
            r"Xeon\(R\).*E3-12\d{2}\s*v4",  # E3-1240 v4
            r"Xeon\(R\).*E5-[124]6\d{2}\s*v4",  # E5-2680 v4
            r"Xeon\(R\).*E7-[248]8\d{2}\s*v4",  # E7-8890 v4
        ],
        "base_multiplier": 1.05,
        "description": "Intel Broadwell (5th-gen Core i)"
    },

    # Skylake (2015-2017) - 6th-gen Core i
    "skylake": {
        "years": (2015, 2017),
        "patterns": [
            r"Core\(TM\) i[3579]-6\d{3}",  # i7-6700K, i5-6600K
            r"Xeon\(R\).*E3-12\d{2}\s*v[56]",  # E3-1230 v5/v6
            r"Xeon\(R\).*(Gold|Silver|Bronze|Platinum)\s*\d{4}(?!\w)",  # Scalable 1st-gen (no letter suffix)
        ],
        "base_multiplier": 1.05,
        "description": "Intel Skylake (6th-gen Core i / Xeon Scalable 1st-gen)"
    },

    # Kaby Lake (2016-2018) - 7th-gen Core i
    "kaby_lake": {
        "years": (2016, 2018),
        "patterns": [
            r"Core\(TM\) i[3579]-7\d{3}",  # i7-7700K, i5-7600K
        ],
        "base_multiplier": 1.0,
        "description": "Intel Kaby Lake (7th-gen Core i)"
    },

    # Coffee Lake (2017-2019) - 8th/9th-gen Core i
    "coffee_lake": {
        "years": (2017, 2019),
        "patterns": [
            r"Core\(TM\) i[3579]-[89]\d{3}",  # i7-8700K, i9-9900K
        ],
        "base_multiplier": 1.0,
        "description": "Intel Coffee Lake (8th/9th-gen Core i)"
    },

    # Cascade Lake (2019) - Xeon Scalable 2nd-gen
    "cascade_lake": {
        "years": (2019, 2020),
        "patterns": [
            r"Xeon\(R\).*(Gold|Silver|Bronze|Platinum)\s*\d{4}[A-Z]",  # Scalable 2nd-gen (letter suffix)
        ],
        "base_multiplier": 1.0,
        "description": "Intel Cascade Lake (Xeon Scalable 2nd-gen)"
    },

    # Comet Lake (2020) - 10th-gen Core i
    "comet_lake": {
        "years": (2020, 2020),
        "patterns": [
            r"Core\(TM\) i[3579]-10\d{3}",  # i7-10700K, i9-10900K
        ],
        "base_multiplier": 1.0,
        "description": "Intel Comet Lake (10th-gen Core i)"
    },

    # Rocket Lake (2021) - 11th-gen Core i
    "rocket_lake": {
        "years": (2021, 2021),
        "patterns": [
            r"Core\(TM\) i[3579]-11\d{3}",  # i7-11700K, i9-11900K
        ],
        "base_multiplier": 1.0,
        "description": "Intel Rocket Lake (11th-gen Core i)"
    },

    # Alder Lake (2021-2022) - 12th-gen Core i (Hybrid P/E cores)
    "alder_lake": {
        "years": (2021, 2022),
        "patterns": [
            r"Core\(TM\) i[3579]-12\d{3}",  # i7-12700K, i9-12900K
            r"Core\(TM\) [3579]\s*12\d{3}",  # New naming: Core 5 12600K
        ],
        "base_multiplier": 1.0,
        "description": "Intel Alder Lake (12th-gen Core i)"
    },

    # Raptor Lake (2022-2023) - 13th/14th-gen Core i
    "raptor_lake": {
        "years": (2022, 2024),
        "patterns": [
            r"Core\(TM\) i[3579]-1[34]\d{3}",  # i7-13700K, i9-14900K
            r"Core\(TM\) [3579]\s*1[34]\d{3}",  # New naming
        ],
        "base_multiplier": 1.0,
        "description": "Intel Raptor Lake (13th/14th-gen Core i)"
    },

    # Sapphire Rapids (2023) - Xeon Scalable 4th-gen
    "sapphire_rapids": {
        "years": (2023, 2024),
        "patterns": [
            r"Xeon\(R\).*(Gold|Silver|Bronze|Platinum)\s*[89]\d{3}",  # Scalable 4th-gen (8xxx/9xxx)
        ],
        "base_multiplier": 1.0,
        "description": "Intel Sapphire Rapids (Xeon Scalable 4th-gen)"
    },

    # Meteor Lake (2023-2024) - Core Ultra (Mobile)
    "meteor_lake": {
        "years": (2023, 2024),
        "patterns": [
            r"Core\(TM\) Ultra\s*[579]",  # Core Ultra 5/7/9
        ],
        "base_multiplier": 1.0,
        "description": "Intel Meteor Lake (Core Ultra)"
    },

    # Arrow Lake (2024) - 15th-gen Core Ultra
    "arrow_lake": {
        "years": (2024, 2025),
        "patterns": [
            r"Core\(TM\) i[3579]-15\d{3}",  # i9-15900K (if released)
            r"Core\(TM\) Ultra\s*[579]\s*2\d{2}",  # Core Ultra 9 285K
        ],
        "base_multiplier": 1.0,
        "description": "Intel Arrow Lake (15th-gen / Core Ultra 2xx)"
    },

    # Generic modern Intel fallback
    "modern_intel": {
        "years": (2020, 2025),
        "patterns": [
            r"Intel",  # Catch-all
        ],
        "base_multiplier": 1.0,
        "description": "Modern Intel CPU (generic)"
    },
}


# =============================================================================
# AMD CPU GENERATIONS & MULTIPLIERS
# =============================================================================

AMD_GENERATIONS = {
    # K7 Era (1999-2005) - Athlon/Duron
    "k7_athlon": {
        "years": (1999, 2005),
        "patterns": [
            r"AMD Athlon\(tm\)",
            r"AMD Athlon XP",
            r"AMD Duron",
            r"Athlon 64 X2",  # Early dual-core
        ],
        "base_multiplier": 1.5,
        "description": "AMD K7 (Athlon/Duron)"
    },

    # K8 Era (2003-2007) - Athlon 64/Opteron
    "k8_athlon64": {
        "years": (2003, 2007),
        "patterns": [
            r"AMD Athlon\(tm\) 64",
            r"Athlon 64",
            r"Opteron\(tm\)",
            r"Turion 64",
        ],
        "base_multiplier": 1.5,
        "description": "AMD K8 (Athlon 64/Opteron)"
    },

    # K10 Era (2007-2011) - Phenom
    "k10_phenom": {
        "years": (2007, 2011),
        "patterns": [
            r"Phenom",
            r"Phenom II",
            r"Athlon II",
        ],
        "base_multiplier": 1.4,
        "description": "AMD K10 (Phenom/Phenom II)"
    },

    # Bulldozer Family (2011-2016) - FX Series
    "bulldozer": {
        "years": (2011, 2012),
        "patterns": [
            r"AMD FX\(tm\)-\d{4}(?!\s*\w)",  # FX-8150, FX-6100 (no suffix)
        ],
        "base_multiplier": 1.3,
        "description": "AMD Bulldozer (FX 1st-gen)"
    },
    "piledriver": {
        "years": (2012, 2014),
        "patterns": [
            r"AMD FX\(tm\)-\d{4}\s*[A-Z]",  # FX-8350, FX-6300 (with suffix)
        ],
        "base_multiplier": 1.3,
        "description": "AMD Piledriver (FX 2nd-gen)"
    },
    "steamroller": {
        "years": (2014, 2015),
        "patterns": [
            r"AMD A[468]-\d{4}[A-Z]?",  # A10-7850K, A8-7600
        ],
        "base_multiplier": 1.2,
        "description": "AMD Steamroller (APU)"
    },
    "excavator": {
        "years": (2015, 2016),
        "patterns": [
            r"AMD A[468]-\d{4}[A-Z]\s*(?:PRO)?",  # A12-9800, A10-9700
        ],
        "base_multiplier": 1.2,
        "description": "AMD Excavator (APU final Bulldozer)"
    },

    # Zen Era (2017-present) - Ryzen
    "zen": {
        "years": (2017, 2018),
        "patterns": [
            r"AMD Ryzen\s*[3579]\s*1\d{3}",  # Ryzen 7 1700X, Ryzen 5 1600
            r"EPYC 7[0-2]\d{2}",  # EPYC 7001 series (Naples)
        ],
        "base_multiplier": 1.1,
        "description": "AMD Zen (Ryzen 1000 / EPYC Naples)"
    },
    "zen_plus": {
        "years": (2018, 2019),
        "patterns": [
            r"AMD Ryzen\s*[3579]\s*2\d{3}",  # Ryzen 7 2700X, Ryzen 5 2600
        ],
        "base_multiplier": 1.1,
        "description": "AMD Zen+ (Ryzen 2000)"
    },
    "zen2": {
        "years": (2019, 2020),
        "patterns": [
            r"AMD Ryzen\s*[3579]\s*3\d{3}",  # Ryzen 9 3900X, Ryzen 7 3700X
            r"EPYC 7[2-4]\d{2}",  # EPYC 7002 series (Rome)
        ],
        "base_multiplier": 1.05,
        "description": "AMD Zen 2 (Ryzen 3000 / EPYC Rome)"
    },
    "zen3": {
        "years": (2020, 2022),
        "patterns": [
            r"AMD Ryzen\s*[3579]\s*5\d{3}",  # Ryzen 9 5950X, Ryzen 7 5800X
            r"EPYC 7[3-5]\d{2}",  # EPYC 7003 series (Milan)
        ],
        "base_multiplier": 1.0,
        "description": "AMD Zen 3 (Ryzen 5000 / EPYC Milan)"
    },
    "zen4": {
        "years": (2022, 2024),
        "patterns": [
            r"AMD Ryzen\s*[3579]\s*7\d{3}",  # Ryzen 9 7950X, Ryzen 7 7700X
            r"AMD Ryzen\s*[3579]\s*8\d{3}",  # Ryzen 5 8645HS (mobile Zen4)
            r"EPYC 9[0-4]\d{2}",  # EPYC 9004 series (Genoa)
            r"EPYC 8[0-4]\d{2}",  # EPYC 8004 series (Siena)
        ],
        "base_multiplier": 1.0,
        "description": "AMD Zen 4 (Ryzen 7000/8000 / EPYC Genoa)"
    },
    "zen5": {
        "years": (2024, 2025),
        "patterns": [
            r"AMD Ryzen\s*[3579]\s*9\d{3}",  # Ryzen 9 9950X, Ryzen 7 9700X
            r"EPYC 9[5-9]\d{2}",  # EPYC 9005 series (Turin)
        ],
        "base_multiplier": 1.0,
        "description": "AMD Zen 5 (Ryzen 9000 / EPYC Turin)"
    },

    # Generic modern AMD fallback
    "modern_amd": {
        "years": (2020, 2025),
        "patterns": [
            r"AMD",  # Catch-all
        ],
        "base_multiplier": 1.0,
        "description": "Modern AMD CPU (generic)"
    },
}


# =============================================================================
# POWERPC ARCHITECTURES (from existing RustChain code)
# =============================================================================

POWERPC_ARCHITECTURES = {
    "g4": {
        "years": (2001, 2005),
        "patterns": [
            r"7450",
            r"7447",
            r"7455",
            r"PowerPC G4",
            r"Power Macintosh",
        ],
        "base_multiplier": 2.5,
        "description": "PowerPC G4 (7450/7447/7455)"
    },
    "g5": {
        "years": (2003, 2006),
        "patterns": [
            r"970",
            r"PowerPC G5",
            r"PowerPC G5 \(970\)",
        ],
        "base_multiplier": 2.0,
        "description": "PowerPC G5 (970)"
    },
    "g3": {
        "years": (1997, 2003),
        "patterns": [
            r"750",
            r"PowerPC G3",
            r"PowerPC G3 \(750\)",
        ],
        "base_multiplier": 1.8,
        "description": "PowerPC G3 (750)"
    },
}


# =============================================================================
# APPLE SILICON (from existing RustChain code)
# =============================================================================

APPLE_SILICON = {
    "m1": {
        "years": (2020, 2021),
        "patterns": [r"Apple M1"],
        "base_multiplier": 1.2,
        "description": "Apple M1 (ARM64)"
    },
    "m2": {
        "years": (2022, 2023),
        "patterns": [r"Apple M2"],
        "base_multiplier": 1.15,
        "description": "Apple M2 (ARM64)"
    },
    "m3": {
        "years": (2023, 2024),
        "patterns": [r"Apple M3"],
        "base_multiplier": 1.1,
        "description": "Apple M3 (ARM64)"
    },
    "m4": {
        "years": (2024, 2025),
        "patterns": [r"Apple M4"],
        "base_multiplier": 1.05,
        "description": "Apple M4 (ARM64)"
    },
}


# =============================================================================
# DETECTION FUNCTIONS
# =============================================================================

def detect_cpu_architecture(brand_string: str) -> Tuple[str, str, int, bool]:
    """
    Detect CPU architecture from brand string

    Returns: (vendor, architecture, microarch_year, is_server)

    Examples:
        "Intel(R) Xeon(R) CPU E5-1650 v2 @ 3.50GHz" → ("intel", "ivy_bridge", 2012, True)
        "Intel(R) Core(TM) i7-2600K CPU @ 3.40GHz" → ("intel", "sandy_bridge", 2011, False)
        "AMD Ryzen 5 8645HS" → ("amd", "zen4", 2022, False)
        "Apple M1" → ("apple", "m1", 2020, False)
        "PowerPC G4" → ("powerpc", "g4", 2001, False)
    """
    brand_string = brand_string.strip()

    # Check PowerPC first (most distinctive)
    for arch_name, arch_info in POWERPC_ARCHITECTURES.items():
        for pattern in arch_info["patterns"]:
            if re.search(pattern, brand_string, re.IGNORECASE):
                return ("powerpc", arch_name, arch_info["years"][0], False)

    # Check Apple Silicon
    for arch_name, arch_info in APPLE_SILICON.items():
        for pattern in arch_info["patterns"]:
            if re.search(pattern, brand_string, re.IGNORECASE):
                return ("apple", arch_name, arch_info["years"][0], False)

    # Check Intel CPUs (order matters - check specific patterns first)
    if re.search(r"Intel", brand_string, re.IGNORECASE):
        # Check server patterns first (Xeon)
        is_server = bool(re.search(r"Xeon", brand_string, re.IGNORECASE))

        for arch_name, arch_info in INTEL_GENERATIONS.items():
            if arch_name == "modern_intel":
                continue  # Skip fallback for now

            for pattern in arch_info["patterns"]:
                if re.search(pattern, brand_string, re.IGNORECASE):
                    return ("intel", arch_name, arch_info["years"][0], is_server)

        # Fallback to modern Intel
        return ("intel", "modern_intel", 2020, is_server)

    # Check AMD CPUs (order matters - check specific patterns first)
    if re.search(r"AMD", brand_string, re.IGNORECASE):
        # Check server patterns first (EPYC, Opteron)
        is_server = bool(re.search(r"EPYC|Opteron", brand_string, re.IGNORECASE))

        for arch_name, arch_info in AMD_GENERATIONS.items():
            if arch_name == "modern_amd":
                continue  # Skip fallback for now

            for pattern in arch_info["patterns"]:
                if re.search(pattern, brand_string, re.IGNORECASE):
                    return ("amd", arch_name, arch_info["years"][0], is_server)

        # Fallback to modern AMD
        return ("amd", "modern_amd", 2020, is_server)

    # Unknown CPU - assume modern
    return ("unknown", "unknown", CURRENT_YEAR, False)


def calculate_antiquity_multiplier(
    brand_string: str,
    loyalty_years: float = 0.0,
    custom_year: Optional[int] = None
) -> CPUInfo:
    """
    Calculate antiquity multiplier for a CPU based on its architecture and age

    Parameters:
        brand_string: CPU brand string from /proc/cpuinfo or system API
        loyalty_years: Years of consistent uptime (for modern x86 loyalty bonus)
        custom_year: Override detected year (for testing)

    Returns:
        CPUInfo object with detected details and calculated multiplier

    Multiplier Logic:
        - PowerPC (G3/G4/G5): High base multipliers (1.8-2.5x)
        - Apple Silicon: Premium but modern (1.05-1.2x based on generation)
        - Vintage Intel/AMD (pre-2010): 1.3-1.5x
        - Mid-range (2010-2018): 1.0-1.2x
        - Modern (2019+): 1.0x base, can earn loyalty bonus up to 1.5x
        - Server CPUs: +0.1x bonus for enterprise hardware

    Time Decay:
        - Vintage bonuses decay 15% per year (incentivize early adoption)
        - Modern CPUs earn 15% loyalty bonus per year (reward consistency)
    """
    vendor, architecture, microarch_year, is_server = detect_cpu_architecture(brand_string)

    # Override year if provided (for testing)
    if custom_year:
        microarch_year = custom_year

    # Calculate hardware age
    hardware_age = CURRENT_YEAR - microarch_year

    # Get base multiplier from architecture tables
    base_multiplier = 1.0  # Default fallback

    if vendor == "powerpc":
        base_multiplier = POWERPC_ARCHITECTURES[architecture]["base_multiplier"]
    elif vendor == "apple":
        base_multiplier = APPLE_SILICON[architecture]["base_multiplier"]
    elif vendor == "intel":
        base_multiplier = INTEL_GENERATIONS[architecture]["base_multiplier"]
    elif vendor == "amd":
        base_multiplier = AMD_GENERATIONS[architecture]["base_multiplier"]

    # Apply time decay for vintage hardware (>5 years old)
    # Decay formula: aged = 1.0 + (base - 1.0) * (1 - 0.15 * years_since_genesis)
    # Full decay after ~6.67 years (vintage bonus → 0, then multiplier = 1.0)
    final_multiplier = base_multiplier

    if hardware_age > 5 and base_multiplier > 1.0:
        # Calculate chain age (in RustChain context, use genesis timestamp)
        # For now, use hardware age as proxy
        decay_factor = max(0.0, 1.0 - (0.15 * (hardware_age - 5) / 5.0))
        vintage_bonus = base_multiplier - 1.0
        final_multiplier = 1.0 + (vintage_bonus * decay_factor)

    # Apply loyalty bonus for modern hardware (<5 years old)
    # Loyalty formula: +15% per year of uptime, max +50% (capped at 1.5x total)
    if hardware_age <= 5 and loyalty_years > 0:
        loyalty_bonus = min(0.5, loyalty_years * 0.15)  # Cap at +50%
        final_multiplier = min(1.5, final_multiplier + loyalty_bonus)

    # Server hardware bonus: +10% for enterprise-class CPUs
    if is_server:
        final_multiplier *= 1.1

    # Get human-readable generation name
    generation_name = ""
    if vendor == "powerpc":
        generation_name = POWERPC_ARCHITECTURES[architecture]["description"]
    elif vendor == "apple":
        generation_name = APPLE_SILICON[architecture]["description"]
    elif vendor == "intel":
        generation_name = INTEL_GENERATIONS[architecture]["description"]
    elif vendor == "amd":
        generation_name = AMD_GENERATIONS[architecture]["description"]
    else:
        generation_name = "Unknown CPU"

    return CPUInfo(
        brand_string=brand_string,
        vendor=vendor,
        architecture=architecture,
        microarch_year=microarch_year,
        model_year=microarch_year,  # Simplified - could be more granular
        generation=generation_name,
        is_server=is_server,
        antiquity_multiplier=round(final_multiplier, 4)
    )


# =============================================================================
# TEST/DEMO CODE
# =============================================================================

def demo_detection():
    """Demo CPU detection with real-world examples"""
    test_cpus = [
        # Vintage Intel
        "Intel(R) Pentium(R) 4 CPU 3.00GHz",
        "Intel(R) Core(TM)2 Duo CPU E8400 @ 3.00GHz",
        "Intel(R) Core(TM) i7-2600K CPU @ 3.40GHz",  # Sandy Bridge
        "Intel(R) Core(TM) i7-4770K CPU @ 3.50GHz",  # Haswell

        # Modern Intel
        "Intel(R) Core(TM) i7-10700K CPU @ 3.80GHz",  # Comet Lake
        "Intel(R) Core(TM) i9-12900K @ 3.20GHz",  # Alder Lake
        "Intel(R) Core(TM) Ultra 9 285K",  # Arrow Lake

        # Intel Xeon
        "Intel(R) Xeon(R) CPU E5-1650 v2 @ 3.50GHz",  # Ivy Bridge-EP
        "Intel(R) Xeon(R) Gold 6248R CPU @ 3.00GHz",  # Cascade Lake

        # AMD Vintage
        "AMD Athlon(tm) 64 X2 Dual Core Processor 4200+",
        "AMD Phenom(tm) II X6 1090T Processor",
        "AMD FX(tm)-8350 Eight-Core Processor",

        # AMD Modern
        "AMD Ryzen 5 8645HS",  # Zen4 mobile
        "AMD Ryzen 9 5950X 16-Core Processor",  # Zen3
        "AMD Ryzen 9 7950X 16-Core Processor",  # Zen4
        "AMD Ryzen 9 9950X 16-Core Processor",  # Zen5

        # AMD Server
        "AMD EPYC 7742 64-Core Processor",  # Rome (Zen2)
        "AMD EPYC 9654 96-Core Processor",  # Genoa (Zen4)

        # PowerPC
        "PowerPC G4 (7450)",
        "PowerPC G5 (970)",

        # Apple Silicon
        "Apple M1",
        "Apple M2",
        "Apple M3",
    ]

    print("=" * 80)
    print("CPU ARCHITECTURE DETECTION & ANTIQUITY MULTIPLIER DEMO")
    print("=" * 80)
    print()

    for cpu in test_cpus:
        info = calculate_antiquity_multiplier(cpu)
        print(f"CPU: {cpu}")
        print(f"  → Vendor: {info.vendor.upper()}")
        print(f"  → Architecture: {info.architecture}")
        print(f"  → Generation: {info.generation}")
        print(f"  → Year: {info.microarch_year} (Age: {CURRENT_YEAR - info.microarch_year} years)")
        print(f"  → Server: {'Yes' if info.is_server else 'No'}")
        print(f"  → Antiquity Multiplier: {info.antiquity_multiplier}x")
        print()

    # Demo loyalty bonus
    print("=" * 80)
    print("LOYALTY BONUS DEMO (Modern x86 with uptime)")
    print("=" * 80)
    print()

    modern_cpu = "AMD Ryzen 9 7950X 16-Core Processor"
    for years in [0, 1, 2, 3, 5, 10]:
        info = calculate_antiquity_multiplier(modern_cpu, loyalty_years=years)
        print(f"Ryzen 9 7950X with {years} years uptime → {info.antiquity_multiplier}x")


if __name__ == "__main__":
    demo_detection()
