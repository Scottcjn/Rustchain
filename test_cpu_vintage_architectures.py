"""
Tests for cpu_vintage_architectures.py

Unit tests for vintage CPU architecture detection and description helpers.
"""

import pytest
from cpu_vintage_architectures import (
    detect_vintage_architecture,
    get_vintage_description,
    VINTAGE_INTEL_X86,
    ODDBALL_X86_VENDORS,
    VINTAGE_AMD_X86,
    MOTOROLA_68K,
    POWERPC_AMIGA,
    RISC_WORKSTATIONS,
)


class TestDetectVintageArchitecture:
    """Tests for detect_vintage_architecture()"""

    # --- Intel x86 ---

    def test_detect_i386(self):
        result = detect_vintage_architecture("Intel 80386DX @ 33MHz")
        assert result is not None
        assert result[0] == "intel"
        assert result[1] == "i386"
        assert result[2] == 1985
        assert result[3] == 3.0

    def test_detect_i486(self):
        result = detect_vintage_architecture("Intel 80486DX2-66")
        assert result is not None
        assert result[1] == "i486"
        assert result[3] == 2.8

    def test_detect_pentium_mmx(self):
        result = detect_vintage_architecture("Intel Pentium 200MHz MMX")
        assert result is not None
        assert result[1] == "pentium_mmx"
        assert result[3] == 2.6

    def test_detect_pentium_pro(self):
        result = detect_vintage_architecture("Intel(R) Pentium(R) Pro 200MHz")
        assert result is not None
        assert result[1] == "pentium_pro"
        assert result[3] == 2.4

    def test_detect_pentium_ii(self):
        result = detect_vintage_architecture("Intel Pentium II 450MHz")
        assert result is not None
        assert result[1] == "pentium_ii"
        assert result[3] == 2.2

    def test_detect_pentium_iii(self):
        result = detect_vintage_architecture("Intel(R) Pentium(R) III CPU 1000MHz")
        assert result is not None
        assert result[1] == "pentium_iii"
        assert result[3] == 2.0

    # --- Oddball x86 ---

    def test_detect_cyrix(self):
        result = detect_vintage_architecture("Cyrix 6x86MX PR200")
        assert result is not None
        assert result[1] == "cyrix_6x86"
        assert result[3] == 2.5

    def test_detect_via_c3(self):
        result = detect_vintage_architecture("VIA C3 Samuel 2 800MHz")
        assert result is not None
        assert result[1] == "via_c3"

    def test_detect_transmeta(self):
        result = detect_vintage_architecture("Transmeta Crusoe TM5800")
        assert result is not None
        assert result[1] == "transmeta_crusoe"

    # --- AMD ---

    def test_detect_amd_k5(self):
        result = detect_vintage_architecture("AMD-K5-PR100")
        assert result is not None
        assert result[0] == "amd"
        assert result[1] == "k5"
        assert result[3] == 2.4

    def test_detect_amd_k6(self):
        result = detect_vintage_architecture("AMD K6-2 350MHz")
        assert result is not None
        assert result[1] == "k6"
        assert result[3] == 2.2

    # --- Motorola 68K ---

    def test_detect_m68000(self):
        result = detect_vintage_architecture("Motorola 68000 @ 8MHz")
        assert result is not None
        assert result[0] == "motorola"
        assert result[1] == "m68000"
        assert result[3] == 3.0

    def test_detect_m68040(self):
        result = detect_vintage_architecture("MC68040 @ 33MHz")
        assert result is not None
        assert result[1] == "m68040"

    # --- PowerPC Amiga ---

    def test_detect_amigaone_g3(self):
        result = detect_vintage_architecture("AmigaOne G3 750GX @ 800MHz")
        assert result is not None
        assert result[0] == "powerpc_amiga"
        assert result[1] == "amigaone_g3"

    def test_detect_pegasos(self):
        result = detect_vintage_architecture("Pegasos II G4")
        assert result is not None
        assert result[1] == "pegasos_g4"

    # --- RISC Workstations ---

    def test_detect_mips_r3000(self):
        result = detect_vintage_architecture("MIPS R3000 @ 33MHz")
        assert result is not None
        assert result[1] == "mips_r3000"
        assert result[3] == 2.8

    def test_detect_sparc_v8(self):
        result = detect_vintage_architecture("SuperSPARC @ 60MHz")
        assert result is not None
        assert result[1] == "sparc_v8"
        assert result[3] == 2.6

    def test_detect_alpha(self):
        result = detect_vintage_architecture("DEC Alpha 21064")
        assert result is not None
        assert result[1] == "alpha_21064"

    def test_detect_riscv(self):
        result = detect_vintage_architecture("StarFive JH7110")
        assert result is not None
        assert result[1] == "riscv_starfive_jh7110"
        assert result[3] == 1.4

    # --- Negative cases ---

    def test_no_match_modern_cpu(self):
        result = detect_vintage_architecture("Intel Core i9-12900K")
        assert result is None

    def test_no_match_amd_ryzen(self):
        result = detect_vintage_architecture("AMD Ryzen 9 5950X")
        assert result is None

    def test_no_match_empty_string(self):
        result = detect_vintage_architecture("")
        assert result is None

    def test_no_match_whitespace_only(self):
        result = detect_vintage_architecture("   ")
        assert result is None


class TestGetVintageDescription:
    """Tests for get_vintage_description()"""

    def test_description_known_arch(self):
        desc = get_vintage_description("i386")
        assert "Intel 80386" in desc

    def test_description_amd_k5(self):
        desc = get_vintage_description("k5")
        assert "AMD K5" in desc

    def test_description_m68000(self):
        desc = get_vintage_description("m68000")
        assert "Motorola 68000" in desc

    def test_description_unknown(self):
        desc = get_vintage_description("nonexistent_arch")
        assert desc == "Unknown vintage CPU"


class TestDataConsistency:
    """Tests verifying dictionary data consistency"""

    def test_all_archs_have_required_keys(self):
        all_archs = {
            **VINTAGE_INTEL_X86,
            **ODDBALL_X86_VENDORS,
            **VINTAGE_AMD_X86,
            **MOTOROLA_68K,
            **POWERPC_AMIGA,
            **RISC_WORKSTATIONS,
        }
        for name, info in all_archs.items():
            assert "years" in info, f"{name} missing 'years'"
            assert "patterns" in info, f"{name} missing 'patterns'"
            assert "base_multiplier" in info, f"{name} missing 'base_multiplier'"
            assert "description" in info, f"{name} missing 'description'"
            assert isinstance(info["years"], tuple) and len(info["years"]) == 2
            assert isinstance(info["patterns"], list) and len(info["patterns"]) > 0
            assert isinstance(info["base_multiplier"], float)
            assert isinstance(info["description"], str)

    def test_multiplier_bounds(self):
        all_archs = {
            **VINTAGE_INTEL_X86,
            **ODDBALL_X86_VENDORS,
            **VINTAGE_AMD_X86,
            **MOTOROLA_68K,
            **POWERPC_AMIGA,
            **RISC_WORKSTATIONS,
        }
        for name, info in all_archs.items():
            mult = info["base_multiplier"]
            assert 1.0 <= mult <= 3.0, f"{name} multiplier {mult} out of bounds"

    def test_year_ranges_valid(self):
        all_archs = {
            **VINTAGE_INTEL_X86,
            **ODDBALL_X86_VENDORS,
            **VINTAGE_AMD_X86,
            **MOTOROLA_68K,
            **POWERPC_AMIGA,
            **RISC_WORKSTATIONS,
        }
        for name, info in all_archs.items():
            start, end = info["years"]
            assert start <= end, f"{name} year range invalid: {start} > {end}"
            assert start >= 1970, f"{name} start year too early"
            assert end <= 2025, f"{name} end year too late"


class TestEdgeCases:
    """Edge-case and robustness tests"""

    def test_case_insensitive_matching(self):
        result = detect_vintage_architecture("INTEL 80386")
        assert result is not None
        assert result[1] == "i386"

    def test_partial_match_inside_string(self):
        result = detect_vintage_architecture("My old Intel 80486DX machine")
        assert result is not None
        assert result[1] == "i486"

    def test_multiple_patterns_all_match(self):
        # Pentium III has multiple patterns; any should match
        result = detect_vintage_architecture("PIII 1000MHz")
        assert result is not None
        assert result[1] == "pentium_iii"
