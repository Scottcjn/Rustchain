# SPDX-License-Identifier: MIT

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rip_proof_of_antiquity_hardware import (
    analyze_cpu_timing,
    analyze_ram_patterns,
    calculate_entropy_score,
    server_side_validation,
)


def test_server_side_validation_rejects_non_object_payload():
    valid, result = server_side_validation(["not", "an", "object"])

    assert valid is False
    assert result["accepted"] is False
    assert result["reason"] == "invalid_payload"
    assert result["warnings"] == ["invalid_payload"]


def test_server_side_validation_handles_malformed_device_and_signals():
    valid, result = server_side_validation({
        "device": ["not", "an", "object"],
        "signals": ["not", "an", "object"],
    })

    assert valid is False
    assert result["accepted"] is False
    assert result["reason"] == "hardware_proof_insufficient"
    assert "cpu_timing_invalid" in result["warnings"]
    assert "ram_timing_missing" in result["warnings"]


def test_signal_analyzers_reject_non_object_shapes():
    assert analyze_cpu_timing([])["reason"] == "invalid_signals"
    assert analyze_cpu_timing({"cpu_timing": []})["reason"] == "invalid_cpu_timing"
    assert analyze_ram_patterns([])["reason"] == "invalid_signals"
    assert analyze_ram_patterns({"ram_timing": []})["reason"] == "invalid_ram_timing"
    assert calculate_entropy_score([]) == 0.0
