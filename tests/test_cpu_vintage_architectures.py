# SPDX-License-Identifier: MIT
"""
Unit tests for cpu_vintage_architectures.py
Covers 2+ edge cases per function as required by bounty #1589 (2 RTC/test file)

Run: pytest test_cpu_vintage_architectures.py -v
"""

import sys
import pytest

sys.path.insert(0, ".")
import cpu_vintage_architectures as cpu_arch


class TestDetectVintageArchitecture:
    """Test detect_vintage_architecture() with 2+ edge cases per category"""

    # ── Intel x86 (1985-2006) ──────────────────────────────────────────

    def test_i386_exact_match(self):
        """i386: exact brand string"""
        result = cpu_arch.detect_vintage_architecture("i386")
        assert result == ("intel", "i386", 1985, 3.0)

    def test_i386_intel_brand(self):
        """i386: Intel brand variant"""
        result = cpu_arch.detect_vintage_architecture("Intel 80386 DX-33")
        assert result == ("intel", "i386", 1985, 3.0)

    def test_i386_partial(self):
        """i386: partial match in longer string"""
        result = cpu_arch.detect_vintage_architecture("Some old CPU i386 laptop")
        assert result == ("intel", "i386", 1985, 3.0)

    def test_i486(self):
        """i486: standard match"""
        result = cpu_arch.detect_vintage_architecture("i486")
        assert result == ("intel", "i486", 1989, 2.8)

    def test_i486_variations(self):
        """i486: DX and SX variants"""
        assert cpu_arch.detect_vintage_architecture("i486DX-33") == ("intel", "i486", 1989, 2.8)

    # ── AMD x86 (1996-1999) ───────────────────────────────────────────

    def test_amd_k5(self):
        """AMD K5: PR-rated CPU"""
        result = cpu_arch.detect_vintage_architecture("AMD-K5 PR150")
        assert result == ("amd", "k5", 1996, 2.4)

    def test_amd_k5_variant(self):
        """AMD K5: space variant"""
        result = cpu_arch.detect_vintage_architecture("AMD K5 PR200")
        assert result == ("amd", "k5", 1996, 2.4)

    def test_amd_k6_dash(self):
        """AMD K6: dash variant"""
        result = cpu_arch.detect_vintage_architecture("AMD-K6-III 400")
        assert result == ("amd", "k6", 1997, 2.2)

    def test_amd_k6_k6_2(self):
        """AMD K6: K6-2 variant"""
        result = cpu_arch.detect_vintage_architecture("AMD K6-2 500")
        assert result == ("amd", "k6", 1997, 2.2)

    def test_amd_k6_k6_3(self):
        """AMD K6: K6-III variant"""
        result = cpu_arch.detect_vintage_architecture("AMD K6/3")
        assert result == ("amd", "k6", 1997, 2.2)

    def test_amd_no_match_plain_string(self):
        """AMD K6 without proper suffix does not match"""
        assert cpu_arch.detect_vintage_architecture("AMD K6") is None
        assert cpu_arch.detect_vintage_architecture("AMD K7") is None

    # ── Motorola 68K (1979-1994) ─────────────────────────────────────

    def test_motorola_68000(self):
        """Motorola 68000: the original"""
        result = cpu_arch.detect_vintage_architecture("Motorola 68000")
        assert result == ("motorola", "m68000", 1979, 3.0)

    def test_motorola_68010(self):
        """Motorola 68010"""
        result = cpu_arch.detect_vintage_architecture("MC68010")
        assert result == ("motorola", "m68010", 1982, 2.9)

    def test_motorola_68020(self):
        """Motorola 68020"""
        result = cpu_arch.detect_vintage_architecture("Motorola 68020")
        assert result == ("motorola", "m68020", 1984, 2.8)

    def test_motorola_68030(self):
        """Motorola 68030"""
        result = cpu_arch.detect_vintage_architecture("68030")
        assert result == ("motorola", "m68030", 1987, 2.6)

    def test_motorola_68040(self):
        """Motorola 68040"""
        result = cpu_arch.detect_vintage_architecture("Motorola 68040")
        assert result == ("motorola", "m68040", 1990, 2.4)

    def test_motorola_68060(self):
        """Motorola 68060"""
        result = cpu_arch.detect_vintage_architecture("Motorola 68060")
        assert result == ("motorola", "m68060", 1994, 2.2)

    # ── Cyrix (1995-2005) ─────────────────────────────────────────────

    def test_cyrix_6x86(self):
        """Cyrix 6x86"""
        result = cpu_arch.detect_vintage_architecture("Cyrix 6x86 MX-PR200")
        assert result == ("cyrix", "cyrix_6x86", 1995, 2.5)

    def test_cyrix_mediaGX(self):
        """Cyrix MediaGX"""
        result = cpu_arch.detect_vintage_architecture("Cyrix MediaGX")
        assert result == ("cyrix", "cyrix_6x86", 1995, 2.5)

    # ── Transmeta (2000-2007) ────────────────────────────────────────

    def test_transmeta_crusoe(self):
        """Transmeta Crusoe: first gen code-morphing"""
        result = cpu_arch.detect_vintage_architecture("Transmeta Crusoe TM5600")
        assert result == ("transmeta", "transmeta_crusoe", 2000, 2.1)

    def test_transmeta_efficeon(self):
        """Transmeta Efficeon TM8000: falls back to Crusoe TM\\d{4} pattern"""
        result = cpu_arch.detect_vintage_architecture("Transmeta Efficeon TM8000")
        assert result == ("transmeta", "transmeta_crusoe", 2000, 2.1)

    # ── RISC Workstations ──────────────────────────────────────────────

    def test_mips_r2000(self):
        """MIPS R2000: first MIPS architecture"""
        result = cpu_arch.detect_vintage_architecture("R2000")
        assert result == ("mips", "mips_r2000", 1985, 3.0)

    def test_mips_r3000(self):
        """MIPS R3000: PlayStation 1 era"""
        result = cpu_arch.detect_vintage_architecture("MIPS R3000")
        assert result == ("mips", "mips_r3000", 1988, 2.8)

    def test_mips_r4000(self):
        """MIPS R4000: R4400 is a common R4000 implementation"""
        result = cpu_arch.detect_vintage_architecture("R4400")
        assert result == ("mips", "mips_r4000", 1991, 2.6)

    def test_mips_r10000(self):
        """MIPS R10000: late MIPS workstation"""
        result = cpu_arch.detect_vintage_architecture("R10000")
        assert result == ("mips", "mips_r10000", 1996, 2.4)

    def test_sparc_v8(self):
        """SPARC v8: Sun microsystems"""
        result = cpu_arch.detect_vintage_architecture("SPARC v8")
        assert result == ("sparc", "sparc_v8", 1990, 2.6)

    def test_sparc_v7(self):
        """SPARC v7: early Sun"""
        result = cpu_arch.detect_vintage_architecture("SPARC v7")
        assert result == ("sparc", "sparc_v7", 1987, 2.9)

    def test_alpha_21064(self):
        """DEC Alpha 21064: early 64-bit RISC"""
        result = cpu_arch.detect_vintage_architecture("Alpha 21064")
        assert result == ("alpha", "alpha_21064", 1992, 2.7)

    def test_alpha_21164(self):
        """DEC Alpha 21164"""
        result = cpu_arch.detect_vintage_architecture("Alpha 21164")
        assert result == ("alpha", "alpha_21164", 1995, 2.5)

    def test_alpha_21264(self):
        """DEC Alpha 21264"""
        result = cpu_arch.detect_vintage_architecture("Alpha 21264")
        assert result == ("alpha", "alpha_21264", 1998, 2.3)

    def test_pa_risc_1_0(self):
        """HP PA-RISC 1.0"""
        result = cpu_arch.detect_vintage_architecture("PA-RISC 1.0")
        assert result == ("pa", "pa_risc_1.0", 1986, 2.9)

    def test_pa_risc_2_0(self):
        """HP PA-RISC 2.0"""
        result = cpu_arch.detect_vintage_architecture("PA-RISC 2.0")
        assert result == ("pa", "pa_risc_2.0", 1996, 2.3)

    def test_hp_pa7100(self):
        """HP PA-7100 (PA-RISC 1.1)"""
        result = cpu_arch.detect_vintage_architecture("PA7100")
        assert result == ("pa", "pa_risc_1.1", 1990, 2.6)

    def test_power1(self):
        """IBM POWER1"""
        result = cpu_arch.detect_vintage_architecture("POWER1")
        assert result == ("power1", "power1", 1990, 2.8)

    def test_power4(self):
        """IBM POWER4"""
        result = cpu_arch.detect_vintage_architecture("POWER4")
        assert result == ("power4", "power4", 2001, 2.2)

    def test_sparc_ultrasparc_t1(self):
        """Sun UltraSPARC T1: matches sparc_v9 first due to "UltraSPARC" pattern"""
        result = cpu_arch.detect_vintage_architecture("UltraSPARC T1")
        assert result == ("sparc", "sparc_v9", 1995, 2.3)

    def test_riscv_sifive_u74(self):
        """RISC-V SiFive U74 board marker"""
        result = cpu_arch.detect_vintage_architecture("SiFive Freedom U740 RV64GC")
        assert result == ("sifive", "sifive_u74", 2020, 1.4)

    def test_riscv_starfive_jh7110(self):
        """RISC-V StarFive JH7110 board marker"""
        result = cpu_arch.detect_vintage_architecture("StarFive JH7110 riscv64 board")
        assert result == ("starfive", "starfive_jh7110", 2022, 1.35)

    def test_riscv_rv32_profile(self):
        """RISC-V RV32IM profile gets the 32-bit exotic weight"""
        result = cpu_arch.detect_vintage_architecture("RV32IMAC embedded board")
        assert result == ("riscv", "riscv_rv32im", 2014, 1.5)

    def test_riscv_vector_modern_marker(self):
        """RISC-V vector extension is recognized as a modernity marker"""
        result = cpu_arch.detect_vintage_architecture("RISC-V RV64GCV vector board")
        assert result == ("riscv", "riscv_vector", 2021, 1.0)

    # ── Edge cases ────────────────────────────────────────────────────

    def test_empty_string_returns_none(self):
        """Empty input returns None gracefully"""
        assert cpu_arch.detect_vintage_architecture("") is None

    def test_whitespace_stripped(self):
        """Input whitespace is stripped before matching"""
        assert cpu_arch.detect_vintage_architecture("  i486  ") == ("intel", "i486", 1989, 2.8)

    def test_case_insensitive(self):
        """Matching is case-insensitive"""
        assert cpu_arch.detect_vintage_architecture("MOTOROLA 68000") == ("motorola", "m68000", 1979, 3.0)

    def test_modern_intel_returns_none(self):
        """Modern Intel CPUs (Core, Xeon) are not detected"""
        assert cpu_arch.detect_vintage_architecture("Intel Core i7-12700K") is None
        assert cpu_arch.detect_vintage_architecture("Intel Xeon Gold 6248") is None

    def test_modern_amd_returns_none(self):
        """Modern AMD CPUs (Ryzen, EPYC) are not detected"""
        assert cpu_arch.detect_vintage_architecture("AMD Ryzen 9 5950X") is None
        assert cpu_arch.detect_vintage_architecture("AMD EPYC 7763") is None

    def test_totally_unknown_returns_none(self):
        """Completely unrelated strings return None gracefully"""
        assert cpu_arch.detect_vintage_architecture("totally random text xyz123") is None

    def test_arm_not_matched(self):
        """ARM CPUs are not in vintage detection scope"""
        assert cpu_arch.detect_vintage_architecture("ARM Cortex-A72") is None
        assert cpu_arch.detect_vintage_architecture("Apple M1") is None


class TestGetVintageDescription:
    """Test get_vintage_description() with 2+ edge cases"""

    def test_i386(self):
        """i386 description"""
        result = cpu_arch.get_vintage_description("i386")
        assert "80386" in result

    def test_i486(self):
        """i486 description"""
        result = cpu_arch.get_vintage_description("i486")
        assert "80486" in result

    def test_mips_r2000(self):
        """MIPS R2000 description"""
        result = cpu_arch.get_vintage_description("mips_r2000")
        assert "R2000" in result

    def test_mips_r3000(self):
        """MIPS R3000 (PlayStation 1)"""
        result = cpu_arch.get_vintage_description("mips_r3000")
        assert "R3000" in result

    def test_sparc_v8(self):
        """SPARC v8 description"""
        result = cpu_arch.get_vintage_description("sparc_v8")
        assert "SPARC" in result

    def test_alpha(self):
        """DEC Alpha description"""
        result = cpu_arch.get_vintage_description("alpha_21064")
        assert "Alpha" in result

    def test_transmeta_crusoe(self):
        """Transmeta Crusoe description"""
        result = cpu_arch.get_vintage_description("transmeta_crusoe")
        assert "Crusoe" in result

    def test_pa_risc(self):
        """HP PA-RISC description"""
        result = cpu_arch.get_vintage_description("pa_risc_1.0")
        assert "PA-RISC" in result or "PA-RISC" in cpu_arch.get_vintage_description("pa_risc_1.0")

    def test_riscv_description(self):
        """RISC-V description"""
        result = cpu_arch.get_vintage_description("sifive_u74")
        assert "RISC-V" in result

    def test_unknown_architecture_returns_fallback(self):
        """Unknown architecture returns a fallback string (not exception)"""
        result = cpu_arch.get_vintage_description("totally_fake_arch_xyz")
        assert isinstance(result, str)
        assert len(result) > 0  # returns a string, not empty


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
