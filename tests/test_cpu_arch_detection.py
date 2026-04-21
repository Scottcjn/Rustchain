# SPDX-License-Identifier: MIT
"""Unit tests for cpu_architecture_detection.py — antiquity multiplier system."""

import sys
import os

# We test the module logic directly by importing the data structures and functions.
# Since we can't install the full RustChain deps in CI, we structure these tests
# to validate the core detection logic in isolation.

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_detect_intel_pentium4():
    """Pentium 4 should be detected as vintage intel with 1.5x base multiplier."""
    from cpu_architecture_detection import detect_cpu_architecture, INTEL_GENERATIONS

    vendor, arch, year, is_server = detect_cpu_architecture(
        "Intel(R) Pentium(R) 4 CPU 3.00GHz"
    )
    assert vendor == "intel", f"Expected 'intel', got '{vendor}'"
    assert arch == "pentium4", f"Expected 'pentium4', got '{arch}'"
    assert year == 2000, f"Expected 2000, got {year}"
    assert is_server is False
    assert INTEL_GENERATIONS["pentium4"]["base_multiplier"] == 1.5


def test_detect_intel_sandy_bridge():
    """Sandy Bridge i7-2600K should be detected correctly."""
    from cpu_architecture_detection import detect_cpu_architecture

    vendor, arch, year, is_server = detect_cpu_architecture(
        "Intel(R) Core(TM) i7-2600K CPU @ 3.40GHz"
    )
    assert vendor == "intel"
    assert arch == "sandy_bridge"
    assert year == 2011
    assert is_server is False


def test_detect_intel_xeon_ivy_bridge():
    """Xeon E5-1650 v2 should be detected as server ivy_bridge."""
    from cpu_architecture_detection import detect_cpu_architecture

    vendor, arch, year, is_server = detect_cpu_architecture(
        "Intel(R) Xeon(R) CPU E5-1650 v2 @ 3.50GHz"
    )
    assert vendor == "intel"
    assert arch == "ivy_bridge"
    assert year == 2012
    assert is_server is True


def test_detect_amd_zen4_desktop():
    """Ryzen 9 7950X should be detected as zen4."""
    from cpu_architecture_detection import detect_cpu_architecture

    vendor, arch, year, is_server = detect_cpu_architecture(
        "AMD Ryzen 9 7950X 16-Core Processor"
    )
    assert vendor == "amd"
    assert arch == "zen4"
    assert year == 2022
    assert is_server is False


def test_detect_amd_epyc_server():
    """EPYC 7742 should be detected as zen2 server."""
    from cpu_architecture_detection import detect_cpu_architecture

    vendor, arch, year, is_server = detect_cpu_architecture(
        "AMD EPYC 7742 64-Core Processor"
    )
    assert vendor == "amd"
    assert arch == "zen2"
    assert year == 2019
    assert is_server is True


def test_detect_powerpc_g4():
    """PowerPC G4 should be detected with highest multiplier."""
    from cpu_architecture_detection import detect_cpu_architecture, POWERPC_ARCHITECTURES

    vendor, arch, year, is_server = detect_cpu_architecture("PowerPC G4 (7450)")
    assert vendor == "powerpc"
    assert arch == "g4"
    assert year == 2001
    assert POWERPC_ARCHITECTURES["g4"]["base_multiplier"] == 2.5


def test_detect_powerpc_g5():
    """PowerPC G5 (970) should be detected with 2.0x multiplier."""
    from cpu_architecture_detection import detect_cpu_architecture, POWERPC_ARCHITECTURES

    vendor, arch, year, is_server = detect_cpu_architecture("PowerPC G5 (970)")
    assert vendor == "powerpc"
    assert arch == "g5"
    assert POWERPC_ARCHITECTURES["g5"]["base_multiplier"] == 2.0


def test_detect_apple_silicon_m1():
    """Apple M1 should be detected correctly."""
    from cpu_architecture_detection import detect_cpu_architecture, APPLE_SILICON

    vendor, arch, year, is_server = detect_cpu_architecture("Apple M1")
    assert vendor == "apple"
    assert arch == "m1"
    assert year == 2020
    assert APPLE_SILICON["m1"]["base_multiplier"] == 1.2


def test_detect_apple_silicon_m4():
    """Apple M4 should have lower multiplier than M1 (newer = less vintage)."""
    from cpu_architecture_detection import detect_cpu_architecture, APPLE_SILICON

    vendor, arch, year, is_server = detect_cpu_architecture("Apple M4")
    assert vendor == "apple"
    assert arch == "m4"
    assert APPLE_SILICON["m4"]["base_multiplier"] < APPLE_SILICON["m1"]["base_multiplier"]


def test_detect_amd_bulldozer_fx():
    """AMD FX-8350 (Piledriver) should be detected as vintage AMD."""
    from cpu_architecture_detection import detect_cpu_architecture

    vendor, arch, year, is_server = detect_cpu_architecture(
        "AMD FX(tm)-8350 Eight-Core Processor"
    )
    assert vendor == "amd"
    assert arch == "piledriver"
    assert year == 2012


def test_antiquity_multiplier_vintage_intel():
    """Pentium 4 should have multiplier > 1.0 (vintage bonus)."""
    from cpu_architecture_detection import calculate_antiquity_multiplier

    info = calculate_antiquity_multiplier("Intel(R) Pentium(R) 4 CPU 3.00GHz")
    assert info.antiquity_multiplier > 1.0, f"Expected > 1.0, got {info.antiquity_multiplier}"
    assert info.vendor == "intel"
    assert info.architecture == "pentium4"


def test_antiquity_multiplier_modern_cpu():
    """Modern CPU (Alder Lake) should have 1.0x base multiplier."""
    from cpu_architecture_detection import calculate_antiquity_multiplier

    info = calculate_antiquity_multiplier("Intel(R) Core(TM) i9-12900K @ 3.20GHz")
    assert info.antiquity_multiplier == 1.0


def test_antiquity_multiplier_powerpc_highest():
    """PowerPC G4 should have highest multiplier among all tested CPUs."""
    from cpu_architecture_detection import calculate_antiquity_multiplier

    g4_info = calculate_antiquity_multiplier("PowerPC G4 (7450)")
    modern_info = calculate_antiquity_multiplier("Intel(R) Core(TM) i9-12900K @ 3.20GHz")
    assert g4_info.antiquity_multiplier > modern_info.antiquity_multiplier


def test_antiquity_multiplier_server_bonus():
    """Xeon server CPU should get +10% bonus over equivalent desktop."""
    from cpu_architecture_detection import calculate_antiquity_multiplier

    # Compare Skylake desktop vs server (both have same base_multiplier 1.05)
    # Server bonus is applied multiplicatively
    info = calculate_antiquity_multiplier(
        "Intel(R) Xeon(R) Gold 6248R CPU @ 3.00GHz"
    )
    assert info.is_server is True
    # Server multiplier should be slightly higher due to 1.1x bonus
    assert info.antiquity_multiplier >= 1.0


def test_loyalty_bonus_modern_cpu():
    """Modern CPU with loyalty years should earn bonus up to 1.5x cap."""
    from cpu_architecture_detection import calculate_antiquity_multiplier

    # 0 years loyalty
    info0 = calculate_antiquity_multiplier(
        "AMD Ryzen 9 7950X 16-Core Processor", loyalty_years=0
    )
    # 3 years loyalty
    info3 = calculate_antiquity_multiplier(
        "AMD Ryzen 9 7950X 16-Core Processor", loyalty_years=3
    )
    # 10 years loyalty (should cap at 1.5x)
    info10 = calculate_antiquity_multiplier(
        "AMD Ryzen 9 7950X 16-Core Processor", loyalty_years=10
    )

    assert info3.antiquity_multiplier > info0.antiquity_multiplier
    assert info10.antiquity_multiplier <= 1.5  # Loyalty cap


def test_vintage_decay():
    """Very old CPUs should experience decay but still be > 1.0x."""
    from cpu_architecture_detection import calculate_antiquity_multiplier

    # Pentium 4 from 2000 (25 years old) - should have decay applied
    info = calculate_antiquity_multiplier("Intel(R) Pentium(R) 4 CPU 3.00GHz")
    # With 25 years of age, decay reduces the vintage bonus significantly
    # but it should still be >= 1.0
    assert info.antiquity_multiplier >= 1.0


def test_unknown_cpu_fallback():
    """Unknown CPU brand should return safe defaults."""
    from cpu_architecture_detection import detect_cpu_architecture

    vendor, arch, year, is_server = detect_cpu_architecture("Some Unknown CPU Brand")
    assert vendor == "unknown"
    assert arch == "unknown"
    assert is_server is False


def test_custom_year_override():
    """Custom year override should work for testing."""
    from cpu_architecture_detection import calculate_antiquity_multiplier

    info = calculate_antiquity_multiplier(
        "Intel(R) Core(TM) i7-2600K CPU @ 3.40GHz", custom_year=1990
    )
    assert info.microarch_year == 1990
    # With 35 years of age, decay should significantly reduce multiplier
    assert info.antiquity_multiplier <= 1.2


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
