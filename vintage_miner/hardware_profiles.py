#!/usr/bin/env python3
"""
Vintage Hardware Profiles for RustChain Mining
===============================================

Pre-2000 CPU profiles with timing characteristics, multipliers, and fingerprints.
Used by vintage_miner_client.py to simulate authentic vintage hardware behavior.
"""

from typing import Dict, Tuple, List
from dataclasses import dataclass


@dataclass
class VintageProfile:
    """Profile for a vintage CPU architecture"""
    name: str
    manufacturer: str
    years: Tuple[int, int]
    base_multiplier: float
    timing_variance: Tuple[float, float]  # (min_jitter, max_jitter) in ms
    stability_window: Tuple[float, float]  # (min_stability, max_stability)
    fingerprint_patterns: List[str]
    os_support: List[str]
    notes: str = ""


# =============================================================================
# VINTAGE PROFILES (Pre-2000)
# =============================================================================

VINTAGE_PROFILES: Dict[str, VintageProfile] = {
    # =========================================================================
    # ULTRA-VINTAGE (1985-1995) - 3.0x to 2.5x
    # =========================================================================
    
    "intel_386": VintageProfile(
        name="Intel 80386",
        manufacturer="Intel",
        years=(1985, 1994),
        base_multiplier=3.0,
        timing_variance=(3.0, 8.0),  # High jitter due to slow clock
        stability_window=(0.85, 0.95),
        fingerprint_patterns=[
            r"i386", r"Intel 386", r"80386", r"Intel.*386",
        ],
        os_support=["Linux 1.x", "Linux 2.0.x", "MS-DOS", "Windows 3.1"],
        notes="First 32-bit x86, max antiquity bonus"
    ),
    
    "intel_486": VintageProfile(
        name="Intel 80486",
        manufacturer="Intel",
        years=(1989, 1997),
        base_multiplier=2.9,
        timing_variance=(2.0, 6.0),
        stability_window=(0.87, 0.96),
        fingerprint_patterns=[
            r"i486", r"Intel 486", r"80486", r"486DX", r"486DX2", r"486SX",
        ],
        os_support=["Linux 1.x", "Linux 2.0.x", "Linux 2.2.x", "MS-DOS", "Windows 95"],
        notes="First x86 with integrated FPU"
    ),
    
    "motorola_68000": VintageProfile(
        name="Motorola 68000",
        manufacturer="Motorola",
        years=(1979, 1990),
        base_multiplier=3.0,
        timing_variance=(4.0, 10.0),
        stability_window=(0.82, 0.93),
        fingerprint_patterns=[
            r"68000", r"MC68000", r"68010", r"68020", r"68030", r"68040", r"68060",
        ],
        os_support=["AmigaOS", "Atari TOS", "Macintosh System", "Linux/m68k"],
        notes="Original Mac/Amiga CPU, 16/32-bit hybrid"
    ),
    
    "mips_r3000": VintageProfile(
        name="MIPS R3000",
        manufacturer="MIPS Technologies",
        years=(1988, 1995),
        base_multiplier=2.9,
        timing_variance=(2.5, 7.0),
        stability_window=(0.86, 0.95),
        fingerprint_patterns=[
            r"MIPS R3000", r"MIPS r3000", r"mips_r3000",
        ],
        os_support=["Ultrix", "IRIX 4.x", "Linux/mips"],
        notes="First commercial RISC, used in DECstation/SGI"
    ),
    
    "mos_6502": VintageProfile(
        name="MOS 6502",
        manufacturer="MOS Technology",
        years=(1975, 1985),
        base_multiplier=2.8,
        timing_variance=(5.0, 15.0),  # Very high jitter
        stability_window=(0.80, 0.92),
        fingerprint_patterns=[
            r"6502", r"65C02", r"65C816", r"6510",
        ],
        os_support=["Commodore KERNAL", "Apple DOS", "Atari DOS"],
        notes="Apple II, Commodore 64, NES CPU"
    ),
    
    # =========================================================================
    # VINTAGE X86 (1993-1999) - 2.5x to 2.0x
    # =========================================================================
    
    "pentium": VintageProfile(
        name="Intel Pentium",
        manufacturer="Intel",
        years=(1993, 1996),
        base_multiplier=2.5,
        timing_variance=(1.5, 4.0),
        stability_window=(0.88, 0.96),
        fingerprint_patterns=[
            r"Pentium", r"Intel.*Pentium\s+\d+", r"P54C",
        ],
        os_support=["Linux 2.0.x", "Linux 2.2.x", "Windows 95", "Windows NT 4.0"],
        notes="Original Pentium (P5 architecture)"
    ),
    
    "pentium_mmx": VintageProfile(
        name="Intel Pentium MMX",
        manufacturer="Intel",
        years=(1996, 1997),
        base_multiplier=2.4,
        timing_variance=(1.2, 3.5),
        stability_window=(0.89, 0.97),
        fingerprint_patterns=[
            r"Pentium.*MMX", r"P55C",
        ],
        os_support=["Linux 2.0.x", "Linux 2.2.x", "Windows 95 OSR2", "Windows 98"],
        notes="Pentium with MMX instructions"
    ),
    
    "pentium_pro": VintageProfile(
        name="Intel Pentium Pro",
        manufacturer="Intel",
        years=(1995, 1998),
        base_multiplier=2.3,
        timing_variance=(1.0, 3.0),
        stability_window=(0.90, 0.97),
        fingerprint_patterns=[
            r"Pentium Pro", r"P6", r"686",
        ],
        os_support=["Linux 2.0.x", "Linux 2.2.x", "Windows NT 4.0", "Windows 2000"],
        notes="First P6 architecture, server-focused"
    ),
    
    "pentium_ii": VintageProfile(
        name="Intel Pentium II",
        manufacturer="Intel",
        years=(1997, 1999),
        base_multiplier=2.2,
        timing_variance=(0.8, 2.5),
        stability_window=(0.91, 0.98),
        fingerprint_patterns=[
            r"Pentium II", r"Pentium\(R\) II", r"Klamath", r"Deschutes",
        ],
        os_support=["Linux 2.0.x", "Linux 2.2.x", "Windows 98", "Windows NT 4.0"],
        notes="Slot 1 cartridge, MMX enhanced"
    ),
    
    "pentium_iii": VintageProfile(
        name="Intel Pentium III",
        manufacturer="Intel",
        years=(1997, 1999),  # Katmai core launched 1997, Coppermine 1999
        base_multiplier=2.0,
        timing_variance=(0.6, 2.0),
        stability_window=(0.92, 0.98),
        fingerprint_patterns=[
            r"Pentium III", r"Pentium\(R\) III", r"Katmai", r"Coppermine",
        ],
        os_support=["Linux 2.2.x", "Linux 2.4.x", "Windows 98", "Windows 2000"],
        notes="Added SSE instructions, only 1999 models qualify for bounty"
    ),
    
    # =========================================================================
    # AMD VINTAGE (1996-1999) - 2.4x to 2.1x
    # =========================================================================
    
    "amd_k5": VintageProfile(
        name="AMD K5",
        manufacturer="AMD",
        years=(1996, 1997),
        base_multiplier=2.4,
        timing_variance=(1.5, 4.5),
        stability_window=(0.87, 0.96),
        fingerprint_patterns=[
            r"AMD-K5", r"AMD K5", r"5k86",
        ],
        os_support=["Linux 2.0.x", "Linux 2.2.x", "Windows 95"],
        notes="AMD's first x86-compatible CPU"
    ),
    
    "amd_k6": VintageProfile(
        name="AMD K6",
        manufacturer="AMD",
        years=(1997, 1999),
        base_multiplier=2.3,
        timing_variance=(1.2, 3.8),
        stability_window=(0.88, 0.97),
        fingerprint_patterns=[
            r"AMD-K6", r"AMD K6", r"AMD K6-2", r"AMD K6-III",
        ],
        os_support=["Linux 2.0.x", "Linux 2.2.x", "Windows 98"],
        notes="Socket 7, competed with Pentium II"
    ),
    
    # =========================================================================
    # CYRIX/ODDBALL X86 (1995-1999) - 2.5x to 2.2x
    # =========================================================================
    
    "cyrix_6x86": VintageProfile(
        name="Cyrix 6x86",
        manufacturer="Cyrix",
        years=(1996, 1998),
        base_multiplier=2.5,
        timing_variance=(1.8, 5.0),
        stability_window=(0.86, 0.95),
        fingerprint_patterns=[
            r"Cyrix 6x86", r"6x86", r"M1",
        ],
        os_support=["Linux 2.0.x", "Linux 2.2.x", "Windows 95"],
        notes="PR rating system, high integer perf"
    ),
    
    "cyrix_mii": VintageProfile(
        name="Cyrix MII",
        manufacturer="Cyrix",
        years=(1998, 1999),
        base_multiplier=2.3,
        timing_variance=(1.5, 4.2),
        stability_window=(0.87, 0.96),
        fingerprint_patterns=[
            r"Cyrix MII", r"MII",
        ],
        os_support=["Linux 2.2.x", "Windows 98"],
        notes="6x86MX rebrand, MMX support"
    ),
    
    # =========================================================================
    # POWERPC (1991-1999) - 2.5x to 1.8x
    # =========================================================================
    
    "powerpc_601": VintageProfile(
        name="PowerPC 601",
        manufacturer="IBM/Motorola",
        years=(1993, 1995),
        base_multiplier=2.5,
        timing_variance=(1.5, 4.0),
        stability_window=(0.87, 0.96),
        fingerprint_patterns=[
            r"PowerPC 601", r"PPC601", r"601",
        ],
        os_support=["Mac OS 7.1-8.1", "AIX", "Linux/ppc"],
        notes="First PowerPC, used in Power Mac 6100/7100/8100"
    ),
    
    "powerpc_603": VintageProfile(
        name="PowerPC 603",
        manufacturer="IBM/Motorola",
        years=(1994, 1997),
        base_multiplier=2.4,
        timing_variance=(1.2, 3.5),
        stability_window=(0.88, 0.97),
        fingerprint_patterns=[
            r"PowerPC 603", r"PPC603", r"603e",
        ],
        os_support=["Mac OS 7.5-8.6", "Linux/ppc"],
        notes="Low-power variant, used in PowerBook"
    ),
    
    "powerpc_604": VintageProfile(
        name="PowerPC 604",
        manufacturer="IBM/Motorola",
        years=(1995, 1997),
        base_multiplier=2.3,
        timing_variance=(1.0, 3.0),
        stability_window=(0.89, 0.97),
        fingerprint_patterns=[
            r"PowerPC 604", r"PPC604", r"604e",
        ],
        os_support=["Mac OS 7.5-8.6", "AIX", "Linux/ppc"],
        notes="High-end desktop PowerPC"
    ),
    
    "powerpc_750": VintageProfile(
        name="PowerPC 750 (G3)",
        manufacturer="IBM/Motorola",
        years=(1997, 1999),
        base_multiplier=1.8,
        timing_variance=(0.8, 2.5),
        stability_window=(0.91, 0.98),
        fingerprint_patterns=[
            r"PowerPC 750", r"PPC750", r"G3",
        ],
        os_support=["Mac OS 8.5-9.2", "Mac OS X 10.0-10.4", "Linux/ppc"],
        notes="Note: G3 (1997-1999) qualifies, G4 (2000+) does not"
    ),
    
    # =========================================================================
    # GAME CONSOLE CPUs (1983-1999) - 2.8x to 2.3x
    # =========================================================================
    
    "nes_6502": VintageProfile(
        name="Ricoh 2A03 (NES)",
        manufacturer="Ricoh",
        years=(1983, 1995),
        base_multiplier=2.8,
        timing_variance=(4.0, 12.0),
        stability_window=(0.82, 0.94),
        fingerprint_patterns=[
            r"2A03", r"NES CPU", r"Ricoh 2A03",
        ],
        os_support=["NES OS"],
        notes="NES/Famicom CPU, 6502 derivative @ 1.79 MHz"
    ),
    
    "snes_65c816": VintageProfile(
        name="Ricoh 5A22 (SNES)",
        manufacturer="Ricoh",
        years=(1990, 1996),
        base_multiplier=2.7,
        timing_variance=(3.5, 10.0),
        stability_window=(0.83, 0.95),
        fingerprint_patterns=[
            r"5A22", r"SNES CPU", r"Ricoh 5A22",
        ],
        os_support=["SNES OS"],
        notes="SNES CPU, 65C816 derivative @ 3.58 MHz"
    ),
    
    "genesis_68000": VintageProfile(
        name="Motorola 68000 (Genesis)",
        manufacturer="Motorola",
        years=(1988, 1997),
        base_multiplier=2.5,
        timing_variance=(3.0, 9.0),
        stability_window=(0.84, 0.95),
        fingerprint_patterns=[
            r"Genesis CPU", r"68000", r"MC68000",
        ],
        os_support=["Genesis OS"],
        notes="Sega Genesis/Mega Drive @ 7.67 MHz"
    ),
    
    "gameboy_z80": VintageProfile(
        name="Sharp LR35902 (Game Boy)",
        manufacturer="Sharp",
        years=(1989, 1999),  # Original Game Boy production ended ~1999
        base_multiplier=2.6,
        timing_variance=(4.5, 13.0),
        stability_window=(0.81, 0.93),
        fingerprint_patterns=[
            r"Game Boy CPU", r"LR35902", r"GB Z80",
        ],
        os_support=["Game Boy OS"],
        notes="Game Boy Z80 derivative @ 4.19 MHz, original DMG model"
    ),
    
    "ps1_mips": VintageProfile(
        name="MIPS R3000A (PlayStation)",
        manufacturer="NEC",
        years=(1994, 1999),  # Original PlayStation (SCPH-1000 to SCPH-9000)
        base_multiplier=2.8,
        timing_variance=(2.0, 6.0),
        stability_window=(0.86, 0.95),
        fingerprint_patterns=[
            r"PlayStation CPU", r"R3000A", r"MIPS R3000A",
        ],
        os_support=["PlayStation OS"],
        notes="PlayStation 1 CPU @ 33.87 MHz, original SCPH-1000-9000 models"
    ),
    
    "dreamcast_sh4": VintageProfile(
        name="Hitachi SH-4 (Dreamcast)",
        manufacturer="Hitachi",
        years=(1998, 1999),  # Dreamcast launched 1998-1999 (pre-2000 models)
        base_multiplier=2.3,
        timing_variance=(1.5, 4.5),
        stability_window=(0.88, 0.96),
        fingerprint_patterns=[
            r"SH-4", r"SH4", r"Dreamcast CPU", r"Hitachi SH-4",
        ],
        os_support=["Dreamcast OS", "KallistiOS"],
        notes="Sega Dreamcast @ 200 MHz, superscalar, Japanese launch models"
    ),
    
    # =========================================================================
    # EXOTIC ARCHITECTURES (1977-1995) - 3.5x to 2.5x
    # =========================================================================
    
    "dec_vax": VintageProfile(
        name="DEC VAX",
        manufacturer="Digital Equipment Corporation",
        years=(1977, 1994),
        base_multiplier=3.5,
        timing_variance=(5.0, 15.0),
        stability_window=(0.80, 0.92),
        fingerprint_patterns=[
            r"VAX", r"VAX-11", r"VAX 8800", r"MicroVAX",
        ],
        os_support=["VMS", "Ultrix", "BSD"],
        notes="Minicomputer legend, 32-bit CISC"
    ),
    
    "transputer": VintageProfile(
        name="Inmos Transputer",
        manufacturer="Inmos",
        years=(1984, 1990),
        base_multiplier=3.5,
        timing_variance=(4.0, 12.0),
        stability_window=(0.81, 0.93),
        fingerprint_patterns=[
            r"Transputer", r"T800", r"T414", r"IMS T800",
        ],
        os_support=["Occam", "Helios"],
        notes="Parallel computing pioneer, had built-in links"
    ),
    
    "intel_i860": VintageProfile(
        name="Intel i860",
        manufacturer="Intel",
        years=(1989, 1996),
        base_multiplier=3.0,
        timing_variance=(3.0, 9.0),
        stability_window=(0.83, 0.94),
        fingerprint_patterns=[
            r"i860", r"Intel i860", r"860",
        ],
        os_support=["OSF/1", "Mach"],
        notes="Failed 'Cray on a chip', VLIW architecture"
    ),
    
    "clipper": VintageProfile(
        name="Fairchild Clipper",
        manufacturer="Fairchild",
        years=(1986, 1990),
        base_multiplier=3.5,
        timing_variance=(4.5, 13.0),
        stability_window=(0.80, 0.92),
        fingerprint_patterns=[
            r"Clipper", r"C100", r"C300", r"C400",
        ],
        os_support=["CX/UX", "UniPlus+"],
        notes="Workstation RISC, ultra-rare"
    ),
    
    "sparc_v8": VintageProfile(
        name="Sun SPARC V8",
        manufacturer="Sun Microsystems",
        years=(1987, 1995),
        base_multiplier=2.7,
        timing_variance=(2.0, 6.0),
        stability_window=(0.86, 0.95),
        fingerprint_patterns=[
            r"SPARC", r"sparc64", r"UltraSPARC",
        ],
        os_support=["SunOS 4.x", "Solaris 2.x"],
        notes="RISC architecture, used in SPARCstation"
    ),
    
    "dec_alpha": VintageProfile(
        name="DEC Alpha",
        manufacturer="Digital Equipment Corporation",
        years=(1992, 1999),  # Only pre-2000 Alpha models qualify
        base_multiplier=2.5,
        timing_variance=(1.5, 4.5),
        stability_window=(0.87, 0.96),
        fingerprint_patterns=[
            r"Alpha", r"DEC Alpha", r"AXP", r"21064", r"21164",
        ],
        os_support=["Digital UNIX", "OpenVMS", "Windows NT"],
        notes="Fastest 1990s CPU, 64-bit RISC, pre-2000 models only"
    ),
}


def get_profile(arch_name: str) -> VintageProfile:
    """Get profile by architecture name"""
    if arch_name not in VINTAGE_PROFILES:
        raise ValueError(f"Unknown vintage profile: {arch_name}")
    return VINTAGE_PROFILES[arch_name]


def get_multiplier(arch_name: str) -> float:
    """Get base multiplier for architecture"""
    return get_profile(arch_name).base_multiplier


def get_era(arch_name: str) -> str:
    """Get era classification for bounty calculation
    
    Uses the START year of the CPU to determine era, as that represents
    when the hardware was first introduced (manufacturing date).
    """
    profile = get_profile(arch_name)
    start_year = profile.years[0]  # Use start year, not end year
    
    if start_year < 1985:
        return "Pre-1985"
    elif start_year < 1990:
        return "1985-1989"
    elif start_year < 1995:
        return "1990-1994"
    else:
        return "1995-1999"


def get_bounty(arch_name: str) -> int:
    """Calculate bounty based on era"""
    era = get_era(arch_name)
    bounty_map = {
        "Pre-1985": 300,
        "1985-1989": 200,
        "1990-1994": 150,
        "1995-1999": 100,
    }
    return bounty_map.get(era, 100)


def list_profiles() -> List[str]:
    """List all available vintage profiles"""
    return list(VINTAGE_PROFILES.keys())


def demo_profiles():
    """Display all vintage profiles"""
    print("=" * 80)
    print("VINTAGE HARDWARE PROFILES FOR RUSTCHAIN MINING")
    print("=" * 80)
    print()
    
    for arch_name, profile in sorted(VINTAGE_PROFILES.items()):
        era = get_era(arch_name)
        bounty = get_bounty(arch_name)
        
        print(f"{profile.name} ({arch_name})")
        print(f"  Manufacturer: {profile.manufacturer}")
        print(f"  Years: {profile.years[0]}-{profile.years[1]}")
        print(f"  Era: {era}")
        print(f"  Multiplier: {profile.base_multiplier}x")
        print(f"  Bounty: {bounty} RTC")
        print(f"  Timing Variance: {profile.timing_variance[0]}-{profile.timing_variance[1]} ms")
        print(f"  Stability: {profile.stability_window[0]}-{profile.stability_window[1]}")
        print(f"  OS Support: {', '.join(profile.os_support)}")
        if profile.notes:
            print(f"  Notes: {profile.notes}")
        print()


if __name__ == "__main__":
    demo_profiles()
