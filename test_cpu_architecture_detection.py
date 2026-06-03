# SPDX-License-Identifier: MIT

import pytest

from cpu_architecture_detection import (
    CURRENT_YEAR,
    calculate_antiquity_multiplier,
    detect_cpu_architecture,
)


def test_detects_consumer_intel_generation():
    assert detect_cpu_architecture("Intel(R) Core(TM) i7-2600K CPU @ 3.40GHz") == (
        "intel",
        "sandy_bridge",
        2011,
        False,
    )


def test_detects_intel_xeon_as_server_cpu():
    assert detect_cpu_architecture("Intel(R) Xeon(R) CPU E5-1650 v2 @ 3.50GHz") == (
        "intel",
        "ivy_bridge",
        2012,
        True,
    )


def test_detects_amd_epyc_generation_and_server_flag():
    assert detect_cpu_architecture("AMD EPYC 7742 64-Core Processor") == (
        "amd",
        "modern_amd",
        2020,
        True,
    )


def test_detects_powerpc_and_unknown_fallback():
    assert detect_cpu_architecture("PowerPC G4 (7450)") == (
        "powerpc",
        "g4",
        2001,
        False,
    )
    assert detect_cpu_architecture("Mystery CPU 9000") == (
        "unknown",
        "unknown",
        CURRENT_YEAR,
        False,
    )


def test_multiplier_applies_loyalty_bonus_for_modern_cpu():
    info = calculate_antiquity_multiplier(
        "AMD Ryzen 9 7950X 16-Core Processor",
        loyalty_years=3,
        custom_year=CURRENT_YEAR,
    )

    assert info.vendor == "amd"
    assert info.architecture == "zen4"
    assert info.antiquity_multiplier == pytest.approx(1.45)


def test_multiplier_applies_server_bonus_after_detection():
    info = calculate_antiquity_multiplier(
        "Intel(R) Xeon(R) CPU E5-1650 v2 @ 3.50GHz",
        custom_year=CURRENT_YEAR,
    )

    assert info.vendor == "intel"
    assert info.architecture == "ivy_bridge"
    assert info.is_server is True
    assert info.antiquity_multiplier == pytest.approx(1.21)
