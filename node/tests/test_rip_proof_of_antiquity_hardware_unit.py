# SPDX-License-Identifier: AGPL-3.0-or-later

from node.rip_proof_of_antiquity_hardware import (
    analyze_cpu_timing,
    analyze_ram_patterns,
    calculate_entropy_score,
    calculate_shannon_entropy,
    get_antiquity_multiplier,
    server_side_validation,
    validate_hardware_proof,
)


def test_shannon_entropy_handles_empty_and_repeated_bytes():
    assert calculate_shannon_entropy(b"") == 0.0
    assert calculate_shannon_entropy(b"\x00" * 16) == 0.0


def test_cpu_timing_matches_ppc_g4_classic_profile():
    signals = {"cpu_timing": {"samples": [8500] * 10, "variance": 300}}

    result = analyze_cpu_timing(signals)

    assert result["valid"] is True
    assert result["profile"] == "ppc_g4"
    assert result["tier"] == "classic"
    assert result["confidence"] == 1.0


def test_cpu_timing_rejects_insufficient_samples():
    result = analyze_cpu_timing({"cpu_timing": {"samples": [500, 501]}})

    assert result == {
        "valid": False,
        "reason": "insufficient_timing_samples",
        "tier": "modern",
        "confidence": 0.0,
    }


def test_ram_patterns_count_vintage_indicators():
    result = analyze_ram_patterns(
        {"ram_timing": {"sequential_ns": 250, "random_ns": 1000, "cache_hit_rate": 0.5}}
    )

    assert result["valid"] is True
    assert result["vintage_indicators"] == 3
    assert result["confidence"] == 1.0


def test_entropy_score_combines_entropy_cpu_ram_and_mac_signals():
    signals = {
        "entropy_samples": bytes(range(16)).hex(),
        "cpu_timing": {"samples": [500] * 10, "variance": 20},
        "ram_timing": {"sequential_ns": 250, "random_ns": 1000, "cache_hit_rate": 0.5},
        "macs": ["00:11:22:33:44:55"],
    }

    score = calculate_entropy_score(signals)

    assert 0.75 < score <= 1.0


def test_validate_hardware_proof_warns_on_claimed_arch_mismatch():
    signals = {
        "entropy_samples": bytes(range(64)).hex(),
        "cpu_timing": {"samples": [500] * 10, "variance": 20},
        "ram_timing": {"sequential_ns": 100, "random_ns": 150, "cache_hit_rate": 0.9},
    }

    is_valid, analysis = validate_hardware_proof(signals, "ppc_g4")

    assert is_valid is True
    assert analysis["antiquity_tier"] == "modern"
    assert "arch_timing_mismatch" in analysis["warnings"]
    assert analysis["tier_confidence"] == 0.5


def test_server_side_validation_returns_multiplier_and_rejection_reason():
    is_valid, result = server_side_validation({"device": {"arch": "unknown"}, "signals": {}})

    assert is_valid is False
    assert result["accepted"] is False
    assert result["reward_multiplier"] == get_antiquity_multiplier("modern")
    assert result["reason"] == "hardware_proof_insufficient"
