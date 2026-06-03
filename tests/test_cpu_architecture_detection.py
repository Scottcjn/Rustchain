# SPDX-License-Identifier: MIT
"""
Unit tests for cpu_architecture_detection.py
Covers 2+ edge cases per function as required by bounty #1589 (2 RTC/test file)

Run: pytest tests/test_cpu_architecture_detection.py -v
"""

import sys
import pytest
from datetime import datetime

sys.path.insert(0, ".")
import cpu_architecture_detection as cpu_arch


class TestDetectCpuArchitecture:
    """Test detect_cpu_architecture() with 2+ edge cases per category"""

    # ── PowerPC ─────────────────────────────────────────────────────

    def test_powerpc_g4_exact(self):
        """PowerPC G4: exact brand string"""
        result = cpu_arch.detect_cpu_architecture("PowerPC G4 (7450)")
        assert result == ("powerpc", "g4", 2001, False)

    def test_powerpc_g4_number(self):
        """PowerPC G4: numeric pattern match"""
        result = cpu_arch.detect_cpu_architecture("Some CPU with 7450 chip")
        assert result == ("powerpc", "g4", 2001, False)

    def test_powerpc_g5(self):
        """PowerPC G5: 970 pattern"""
        result = cpu_arch.detect_cpu_architecture("PowerPC G5 (970)")
        assert result == ("powerpc", "g5", 2003, False)

    def test_powerpc_g3(self):
        """PowerPC G3: 750 pattern"""
        result = cpu_arch.detect_cpu_architecture("PowerPC G3 (750)")
        assert result == ("powerpc", "g3", 1997, False)

    def test_powerpc_case_insensitive(self):
        """PowerPC: case-insensitive matching"""
        result = cpu_arch.detect_cpu_architecture("powerpc g4 7450")
        assert result == ("powerpc", "g4", 2001, False)

    # ── Apple Silicon ──────────────────────────────────────────────

    def test_apple_m1(self):
        """Apple M1: exact match"""
        result = cpu_arch.detect_cpu_architecture("Apple M1")
        assert result == ("apple", "m1", 2020, False)

    def test_apple_m2(self):
        """Apple M2: exact match"""
        result = cpu_arch.detect_cpu_architecture("Apple M2")
        assert result == ("apple", "m2", 2022, False)

    def test_apple_m3(self):
        """Apple M3: exact match"""
        result = cpu_arch.detect_cpu_architecture("Apple M3 Pro")
        assert result == ("apple", "m3", 2023, False)

    def test_apple_m4(self):
        """Apple M4: exact match"""
        result = cpu_arch.detect_cpu_architecture("Apple M4 Max")
        assert result == ("apple", "m4", 2024, False)

    def test_apple_case_insensitive(self):
        """Apple Silicon: case-insensitive matching"""
        result = cpu_arch.detect_cpu_architecture("APPLE M1 PRO")
        assert result == ("apple", "m1", 2020, False)

    # ── Intel — Vintage (NetBurst / Core 2) ───────────────────────

    def test_intel_pentium4(self):
        """Intel Pentium 4: exact match"""
        result = cpu_arch.detect_cpu_architecture("Intel(R) Pentium(R) 4 CPU 3.00GHz")
        assert result == ("intel", "pentium4", 2000, False)

    def test_intel_pentium4_tm(self):
        """Intel Pentium 4: (TM) variant"""
        result = cpu_arch.detect_cpu_architecture("Pentium(R) 4")
        assert result == ("intel", "pentium4", 2000, False)

    def test_intel_pentium_d(self):
        """Intel Pentium D: dual-core variant"""
        result = cpu_arch.detect_cpu_architecture("Pentium(R) D")
        assert result == ("intel", "pentium_d", 2005, False)

    def test_intel_core2_duo(self):
        """Intel Core 2 Duo: exact match"""
        result = cpu_arch.detect_cpu_architecture("Intel(R) Core(TM)2 Duo CPU E8400 @ 3.00GHz")
        assert result == ("intel", "core2", 2006, False)

    def test_intel_core2_quad(self):
        """Intel Core 2 Quad: quad-core variant"""
        result = cpu_arch.detect_cpu_architecture("Intel Core 2 Quad")
        assert result == ("intel", "core2", 2006, False)

    def test_intel_core2_tm_variant(self):
        """Intel Core 2: (TM) variant"""
        result = cpu_arch.detect_cpu_architecture("Core(TM)2")
        assert result == ("intel", "core2", 2006, False)

    # ── Intel — Nehalem / Westmere ─────────────────────────────────

    def test_intel_nehalem_i7(self):
        """Intel Nehalem: i7-900 series"""
        result = cpu_arch.detect_cpu_architecture("Intel(R) Core(TM) i7-920 CPU @ 2.66GHz")
        assert result == ("intel", "nehalem", 2008, False)

    def test_intel_nehalem_xeon(self):
        """Intel Nehalem: Xeon E55xx"""
        result = cpu_arch.detect_cpu_architecture("Intel(R) Xeon(R) CPU X5570 @ 2.93GHz")
        assert result == ("intel", "nehalem", 2008, True)

    def test_intel_westmere_i7(self):
        """Intel Westmere: i7-900 series (8xxx)"""
        result = cpu_arch.detect_cpu_architecture("Intel(R) Core(TM) i7-980 CPU @ 3.33GHz")
        assert result == ("intel", "westmere", 2010, False)

    def test_intel_westmere_xeon(self):
        """Intel Westmere: Xeon E56xx"""
        result = cpu_arch.detect_cpu_architecture("Intel(R) Xeon(R) CPU E5675 @ 3.07GHz")
        assert result == ("intel", "westmere", 2010, True)

    # ── Intel — Sandy Bridge / Ivy Bridge ──────────────────────────

    def test_intel_sandy_bridge_i7(self):
        """Intel Sandy Bridge: i7-2000 series"""
        result = cpu_arch.detect_cpu_architecture("Intel(R) Core(TM) i7-2600K CPU @ 3.40GHz")
        assert result == ("intel", "sandy_bridge", 2011, False)

    def test_intel_sandy_bridge_xeon_e3(self):
        """Intel Sandy Bridge: Xeon E3-12xx (no v-suffix)"""
        result = cpu_arch.detect_cpu_architecture("Intel Xeon E3-1230")
        assert result == ("intel", "sandy_bridge", 2011, True)

    def test_intel_sandy_bridge_xeon_e5(self):
        """Intel Sandy Bridge: Xeon E5-2400/1600/2600 (no v-suffix)"""
        result = cpu_arch.detect_cpu_architecture("Intel Xeon E5-2670")
        assert result == ("intel", "sandy_bridge", 2011, True)

    def test_intel_ivy_bridge_i7(self):
        """Intel Ivy Bridge: i7-3000 series"""
        result = cpu_arch.detect_cpu_architecture("Intel(R) Core(TM) i7-3770K CPU @ 3.50GHz")
        assert result == ("intel", "ivy_bridge", 2012, False)

    def test_intel_ivy_bridge_xeon_v2(self):
        """Intel Ivy Bridge: Xeon with v2 suffix"""
        result = cpu_arch.detect_cpu_architecture("Intel Xeon E3-1230 v2")
        assert result == ("intel", "ivy_bridge", 2012, True)

    def test_intel_ivy_bridge_xeon_e5_v2(self):
        """Intel Ivy Bridge: Xeon E5 v2"""
        result = cpu_arch.detect_cpu_architecture("Intel Xeon E5-2670 v2")
        assert result == ("intel", "ivy_bridge", 2012, True)

    def test_intel_ivy_bridge_xeon_e7_v2(self):
        """Intel Ivy Bridge: Xeon E7 v2"""
        result = cpu_arch.detect_cpu_architecture("Intel Xeon E7-4870 v2")
        assert result == ("intel", "ivy_bridge", 2012, True)

    # ── Intel — Haswell / Broadwell ────────────────────────────────

    def test_intel_haswell_i7(self):
        """Intel Haswell: i7-4000 series"""
        result = cpu_arch.detect_cpu_architecture("Intel(R) Core(TM) i7-4770K CPU @ 3.50GHz")
        assert result == ("intel", "haswell", 2013, False)

    def test_intel_haswell_xeon_v3(self):
        """Intel Haswell: Xeon with v3 suffix"""
        result = cpu_arch.detect_cpu_architecture("Intel Xeon E3-1231 v3")
        assert result == ("intel", "haswell", 2013, True)

    def test_intel_broadwell_i7(self):
        """Intel Broadwell: i7-5000 series"""
        result = cpu_arch.detect_cpu_architecture("Intel(R) Core(TM) i7-5775C CPU @ 3.30GHz")
        assert result == ("intel", "broadwell", 2014, False)

    def test_intel_broadwell_xeon_v4(self):
        """Intel Broadwell: Xeon with v4 suffix"""
        result = cpu_arch.detect_cpu_architecture("Intel Xeon E3-1240 v4")
        assert result == ("intel", "broadwell", 2014, True)

    # ── Intel — Skylake / Kaby Lake / Coffee Lake ─────────────────

    def test_intel_skylake_i7(self):
        """Intel Skylake: i7-6000 series"""
        result = cpu_arch.detect_cpu_architecture("Intel(R) Core(TM) i7-6700K CPU @ 4.00GHz")
        assert result == ("intel", "skylake", 2015, False)

    def test_intel_skylake_xeon_scalable_gold(self):
        """Intel Skylake: Xeon Scalable Gold/Silver/Platinum (1st gen, no letter suffix)"""
        result = cpu_arch.detect_cpu_architecture("Intel Xeon Gold 6248")
        assert result == ("intel", "skylake", 2015, True)

    def test_intel_kaby_lake_i7(self):
        """Intel Kaby Lake: i7-7000 series"""
        result = cpu_arch.detect_cpu_architecture("Intel(R) Core(TM) i7-7700K CPU @ 4.20GHz")
        assert result == ("intel", "kaby_lake", 2016, False)

    def test_intel_coffee_lake_i9(self):
        """Intel Coffee Lake: i9-9000 series"""
        result = cpu_arch.detect_cpu_architecture("Intel(R) Core(TM) i9-9900K CPU @ 3.60GHz")
        assert result == ("intel", "coffee_lake", 2017, False)

    # ── Intel — Comet Lake / Rocket Lake / Alder Lake ─────────────

    def test_intel_comet_lake_i7(self):
        """Intel Comet Lake: i7-10000 series"""
        result = cpu_arch.detect_cpu_architecture("Intel(R) Core(TM) i7-10700K CPU @ 3.80GHz")
        assert result == ("intel", "comet_lake", 2020, False)

    def test_intel_rocket_lake_i7(self):
        """Intel Rocket Lake: i7-11000 series"""
        result = cpu_arch.detect_cpu_architecture("Intel(R) Core(TM) i7-11700K CPU @ 2.60GHz")
        assert result == ("intel", "rocket_lake", 2021, False)

    def test_intel_alder_lake_i9(self):
        """Intel Alder Lake: i9-12000 series (Hybrid P/E cores)"""
        result = cpu_arch.detect_cpu_architecture("Intel(R) Core(TM) i9-12900K CPU @ 3.20GHz")
        assert result == ("intel", "alder_lake", 2021, False)

    def test_intel_alder_lake_new_naming(self):
        """Intel Alder Lake: new Core 5/7/9 naming convention"""
        result = cpu_arch.detect_cpu_architecture("Intel Core 5 12600K")
        assert result == ("intel", "alder_lake", 2021, False)

    # ── Intel — Raptor Lake / Sapphire Rapids / Meteor/Arrow Lake ─

    def test_intel_raptor_lake_i9(self):
        """Intel Raptor Lake: i9-13000/14000 series"""
        result = cpu_arch.detect_cpu_architecture("Intel(R) Core(TM) i9-13900K CPU @ 3.00GHz")
        assert result == ("intel", "raptor_lake", 2022, False)

    def test_intel_raptor_lake_new_naming(self):
        """Intel Raptor Lake: new naming Core 7 13700K"""
        result = cpu_arch.detect_cpu_architecture("Core 7 13700K")
        assert result == ("intel", "raptor_lake", 2022, False)

    def test_intel_sapphire_rapids_xeon(self):
        """Intel Sapphire Rapids: Xeon Scalable 4th gen (Gold/Silver 8xxx/9xxx)"""
        result = cpu_arch.detect_cpu_architecture("Intel Xeon Gold 6248R")
        assert result == ("intel", "sapphire_rapids", 2023, True)

    def test_intel_meteor_lake_core_ultra(self):
        """Intel Meteor Lake: Core Ultra naming"""
        result = cpu_arch.detect_cpu_architecture("Intel Core Ultra 7")
        assert result == ("intel", "meteor_lake", 2023, False)

    def test_intel_arrow_lake_core_ultra_2xx(self):
        """Intel Arrow Lake: Core Ultra 2xx series"""
        result = cpu_arch.detect_cpu_architecture("Intel Core Ultra 9 285K")
        assert result == ("intel", "arrow_lake", 2024, False)

    # ── AMD — K7 / K8 / K10 Era ───────────────────────────────────

    def test_amd_k7_athlon_xp(self):
        """AMD K7 Athlon XP"""
        result = cpu_arch.detect_cpu_architecture("AMD Athlon(tm) XP 1800+")
        assert result == ("amd", "k7_athlon", 1999, False)

    def test_amd_k7_duron(self):
        """AMD K7 Duron"""
        result = cpu_arch.detect_cpu_architecture("AMD Duron")
        assert result == ("amd", "k7_athlon", 1999, False)

    def test_amd_k8_athlon64(self):
        """AMD K8 Athlon 64"""
        result = cpu_arch.detect_cpu_architecture("AMD Athlon(tm) 64 X2")
        assert result == ("amd", "k8_athlon64", 2003, False)

    def test_amd_k8_opteron(self):
        """AMD K8 Opteron"""
        result = cpu_arch.detect_cpu_architecture("Opteron(tm) 2376")
        assert result == ("amd", "k8_athlon64", 2003, True)

    def test_amd_k10_phenom(self):
        """AMD K10 Phenom"""
        result = cpu_arch.detect_cpu_architecture("AMD Phenom(tm) II X6 1090T")
        assert result == ("amd", "k10_phenom", 2007, False)

    def test_amd_k10_athlonii(self):
        """AMD K10 Athlon II"""
        result = cpu_arch.detect_cpu_architecture("AMD Athlon II X4 630")
        assert result == ("amd", "k10_phenom", 2007, False)

    # ── AMD — Bulldozer Family ─────────────────────────────────────

    def test_amd_bulldozer_fx_1st(self):
        """AMD Bulldozer: FX-8xxx (no suffix)"""
        result = cpu_arch.detect_cpu_architecture("AMD FX(tm)-8150")
        assert result == ("amd", "bulldozer", 2011, False)

    def test_amd_piledriver_fx(self):
        """AMD Piledriver: FX-6xxx with letter suffix"""
        result = cpu_arch.detect_cpu_architecture("AMD FX(tm)-8350 ")
        assert result == ("amd", "piledriver", 2012, False)

    def test_amd_piledriver_fx_6300(self):
        """AMD Piledriver: FX-6300 with suffix"""
        result = cpu_arch.detect_cpu_architecture("AMD FX-6300 Six-Core")
        assert result == ("amd", "piledriver", 2012, False)

    def test_amd_steamroller_apu(self):
        """AMD Steamroller: A-series APU"""
        result = cpu_arch.detect_cpu_architecture("AMD A10-7850K")
        assert result == ("amd", "steamroller", 2014, False)

    def test_amd_excavator_apu(self):
        """AMD Excavator: A-series APU with letter suffix"""
        result = cpu_arch.detect_cpu_architecture("AMD A12-9800")
        assert result == ("amd", "excavator", 2015, False)

    # ── AMD — Zen Era ──────────────────────────────────────────────

    def test_amd_zen_ryzen_1000(self):
        """AMD Zen: Ryzen 1000 series"""
        result = cpu_arch.detect_cpu_architecture("AMD Ryzen 7 1700X")
        assert result == ("amd", "zen", 2017, False)

    def test_amd_zen_ryzen_1600(self):
        """AMD Zen: Ryzen 5 1600"""
        result = cpu_arch.detect_cpu_architecture("AMD Ryzen 5 1600")
        assert result == ("amd", "zen", 2017, False)

    def test_amd_zen_epyc_naples(self):
        """AMD Zen: EPYC 7001 series (Naples)"""
        result = cpu_arch.detect_cpu_architecture("AMD EPYC 7281")
        assert result == ("amd", "zen", 2017, True)

    def test_amd_zen_plus_ryzen_2700x(self):
        """AMD Zen+: Ryzen 2000 series"""
        result = cpu_arch.detect_cpu_architecture("AMD Ryzen 7 2700X")
        assert result == ("amd", "zen_plus", 2018, False)

    def test_amd_zen2_ryzen_3000(self):
        """AMD Zen 2: Ryzen 3000 series"""
        result = cpu_arch.detect_cpu_architecture("AMD Ryzen 9 3900X")
        assert result == ("amd", "zen2", 2019, False)

    def test_amd_zen2_epyc_rome(self):
        """AMD Zen 2: EPYC 7002 series (Rome)"""
        result = cpu_arch.detect_cpu_architecture("AMD EPYC 7742")
        assert result == ("amd", "zen2", 2019, True)

    def test_amd_zen3_ryzen_5000(self):
        """AMD Zen 3: Ryzen 5000 series"""
        result = cpu_arch.detect_cpu_architecture("AMD Ryzen 9 5950X")
        assert result == ("amd", "zen3", 2020, False)

    def test_amd_zen3_epyc_milan(self):
        """AMD Zen 3: EPYC 7003 series (Milan)"""
        result = cpu_arch.detect_cpu_architecture("AMD EPYC 7713")
        assert result == ("amd", "zen3", 2020, True)

    def test_amd_zen4_ryzen_7000(self):
        """AMD Zen 4: Ryzen 7000 series"""
        result = cpu_arch.detect_cpu_architecture("AMD Ryzen 9 7950X")
        assert result == ("amd", "zen4", 2022, False)

    def test_amd_zen4_ryzen_mobile(self):
        """AMD Zen 4: Ryzen mobile 8000 series (8645HS)"""
        result = cpu_arch.detect_cpu_architecture("AMD Ryzen 5 8645HS")
        assert result == ("amd", "zen4", 2022, False)

    def test_amd_zen4_epyc_genoa(self):
        """AMD Zen 4: EPYC 9004 series (Genoa)"""
        result = cpu_arch.detect_cpu_architecture("AMD EPYC 9654")
        assert result == ("amd", "zen4", 2022, True)

    def test_amd_zen4_epyc_siena(self):
        """AMD Zen 4: EPYC 8004 series (Siena)"""
        result = cpu_arch.detect_cpu_architecture("AMD EPYC 8324")
        assert result == ("amd", "zen4", 2022, True)

    def test_amd_zen5_ryzen_9000(self):
        """AMD Zen 5: Ryzen 9000 series"""
        result = cpu_arch.detect_cpu_architecture("AMD Ryzen 9 9950X")
        assert result == ("amd", "zen5", 2024, False)

    def test_amd_zen5_epyc_turin(self):
        """AMD Zen 5: EPYC 9005 series (Turin)"""
        result = cpu_arch.detect_cpu_architecture("AMD EPYC 9555")
        assert result == ("amd", "zen5", 2024, True)

    # ── Unknown / Fallback ──────────────────────────────────────────

    def test_unknown_cpu_fallback(self):
        """Unknown CPU: fallback to modern unknown"""
        result = cpu_arch.detect_cpu_architecture("Some obscure CPU XYZ123")
        assert result == ("unknown", "unknown", datetime.now().year, False)

    def test_empty_string(self):
        """Empty brand string: fallback to current year"""
        result = cpu_arch.detect_cpu_architecture("")
        assert result[0] == "unknown"
        assert result[1] == "unknown"
        assert result[2] == datetime.now().year


class TestCalculateAntiquityMultiplier:
    """Test calculate_antiquity_multiplier() — 2+ edge cases per scenario"""

    # ── Vintage hardware (high multiplier, decays over time) ───────

    def test_pentium4_high_multiplier_no_decay(self):
        """Pentium 4: base multiplier 1.5, no decay when hardware_age <= 5"""
        result = cpu_arch.calculate_antiquity_multiplier("Pentium(R) 4", custom_year=2000)
        assert result.vendor == "intel"
        assert result.architecture == "pentium4"
        assert result.antiquity_multiplier > 1.0  # Should have vintage bonus

    def test_pentium4_vintage_decay(self):
        """Pentium 4: 1.5 base, decays after 5 years"""
        result = cpu_arch.calculate_antiquity_multiplier("Pentium(R) 4", custom_year=2000)
        # Hardware age > 5 years: vintage bonus decays
        assert result.antiquity_multiplier < 1.5

    def test_powerpc_g5_high_multiplier(self):
        """PowerPC G5: high base multiplier (2.0)"""
        result = cpu_arch.calculate_antiquity_multiplier("PowerPC G5 (970)")
        assert result.vendor == "powerpc"
        assert result.architecture == "g5"
        assert result.antiquity_multiplier >= 1.8  # Base 2.0

    def test_powerpc_g4_high_multiplier(self):
        """PowerPC G4: highest base multiplier (2.5)"""
        result = cpu_arch.calculate_antiquity_multiplier("PowerPC G4 (7450)")
        assert result.vendor == "powerpc"
        assert result.architecture == "g4"
        assert result.antiquity_multiplier >= 2.0  # Base 2.5

    def test_core2_vintage_multiplier(self):
        """Intel Core 2: base multiplier 1.3, should have vintage bonus"""
        result = cpu_arch.calculate_antiquity_multiplier("Intel Core 2 Duo")
        assert result.vendor == "intel"
        assert result.architecture == "core2"
        assert result.antiquity_multiplier > 1.0

    # ── Modern hardware (loyalty bonus) ────────────────────────────

    def test_modern_cpu_no_loyalty(self):
        """Modern CPU (2022): no loyalty bonus when loyalty_years=0"""
        result = cpu_arch.calculate_antiquity_multiplier(
            "AMD Ryzen 9 7950X", loyalty_years=0.0, custom_year=2022
        )
        assert result.vendor == "amd"
        assert result.architecture == "zen4"

    def test_modern_cpu_loyalty_bonus(self):
        """Modern CPU (2022): loyalty bonus accrues +15% per year, capped at +50%"""
        result_no_loyalty = cpu_arch.calculate_antiquity_multiplier(
            "AMD Ryzen 9 7950X", loyalty_years=0.0, custom_year=2022
        )
        result_with_loyalty = cpu_arch.calculate_antiquity_multiplier(
            "AMD Ryzen 9 7950X", loyalty_years=3.0, custom_year=2022
        )
        assert result_with_loyalty.antiquity_multiplier > result_no_loyalty.antiquity_multiplier

    def test_loyalty_bonus_capped_at_1_5x(self):
        """Loyalty bonus capped at +50% (max 1.5x total)"""
        result = cpu_arch.calculate_antiquity_multiplier(
            "AMD Ryzen 9 7950X", loyalty_years=100.0, custom_year=2022
        )
        assert result.antiquity_multiplier <= 1.5

    def test_loyalty_bonus_1_year(self):
        """1 year loyalty: +15% (0.15 * 1)"""
        result = cpu_arch.calculate_antiquity_multiplier(
            "AMD Ryzen 9 7950X", loyalty_years=1.0, custom_year=2022
        )
        # Should be 1.0 + 0.15 = 1.15 (approximately)
        assert result.antiquity_multiplier >= 1.15

    # ── Server hardware bonus (+10%) ──────────────────────────────

    def test_server_cpu_bonus(self):
        """Server Xeon: +10% bonus on top of base multiplier"""
        result_server = cpu_arch.calculate_antiquity_multiplier(
            "Intel Xeon E3-1230 v2"  # Ivy Bridge Xeon (server)
        )
        result_desktop = cpu_arch.calculate_antiquity_multiplier(
            "Intel(R) Core(TM) i7-3770K CPU"  # Ivy Bridge Desktop
        )
        # Same architecture (ivy_bridge), but server gets +10%
        assert result_server.antiquity_multiplier > result_desktop.antiquity_multiplier

    # ── CPUInfo dataclass fields ──────────────────────────────────

    def test_cpu_info_fields(self):
        """CPUInfo dataclass returns all expected fields"""
        result = cpu_arch.calculate_antiquity_multiplier(
            "AMD Ryzen 9 7950X", loyalty_years=2.0, custom_year=2022
        )
        assert result.brand_string == "AMD Ryzen 9 7950X"
        assert result.vendor == "amd"
        assert result.architecture == "zen4"
        assert result.microarch_year == 2022
        assert result.model_year == 2022
        assert isinstance(result.generation, str)
        assert isinstance(result.antiquity_multiplier, float)
        assert isinstance(result.is_server, bool)

    def test_custom_year_override(self):
        """custom_year parameter overrides detected year"""
        result = cpu_arch.calculate_antiquity_multiplier(
            "AMD Ryzen 9 7950X", custom_year=2010
        )
        assert result.microarch_year == 2010

    def test_vintage_hardware_age_based_decay(self):
        """Vintage hardware (age > 5 years): bonus decays over time"""
        result_very_old = cpu_arch.calculate_antiquity_multiplier(
            "Pentium(R) 4", custom_year=2010
        )
        result_recent_vintage = cpu_arch.calculate_antiquity_multiplier(
            "Pentium(R) 4", custom_year=2018
        )
        # Very old should have less bonus than recent vintage
        assert result_very_old.antiquity_multiplier < result_recent_vintage.antiquity_multiplier

    # ── Edge cases ────────────────────────────────────────────────

    def test_negative_loyalty_years(self):
        """Negative loyalty_years: should not cause errors"""
        result = cpu_arch.calculate_antiquity_multiplier(
            "AMD Ryzen 9 7950X", loyalty_years=-5.0, custom_year=2022
        )
        assert isinstance(result.antiquity_multiplier, float)

    def test_zero_loyalty_modern_cpu(self):
        """Modern CPU with 0 loyalty: base multiplier only (1.0)"""
        result = cpu_arch.calculate_antiquity_multiplier(
            "AMD Ryzen 9 7950X", loyalty_years=0.0, custom_year=2024
        )
        assert result.antiquity_multiplier >= 1.0

    def test_vintage_mixed_decay_and_loyalty(self):
        """Vintage hardware: loyalty bonus does NOT apply (only modern hardware)"""
        result = cpu_arch.calculate_antiquity_multiplier(
            "Pentium(R) 4", loyalty_years=10.0, custom_year=2000
        )
        # Should be < 1.5 (vintage bonus decayed) and NOT have loyalty bonus added
        assert result.antiquity_multiplier < 1.5
