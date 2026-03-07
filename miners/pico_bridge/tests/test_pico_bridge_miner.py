#!/usr/bin/env python3
"""
Tests for Pico Bridge Miner (RIP-304)
======================================

Tests the PicoSimulator and attestation payload builder.
"""

import sys
import os
import hashlib

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'miners', 'pico_bridge'))

from pico_bridge_miner import (
    PicoSimulator,
    build_attestation_payload,
    CONSOLE_PROFILES,
)


def test_pico_simulator_connection():
    """Test PicoSimulator can connect."""
    sim = PicoSimulator("n64_mips")
    result = sim.connect()

    assert result, "Simulator should connect successfully"
    assert sim.board_id is not None
    assert sim.board_id.startswith("RP2040-SIM-")
    print("✓ test_pico_simulator_connection passed")


def test_pico_simulator_challenge():
    """Test PicoSimulator can process challenge."""
    sim = PicoSimulator("n64_mips")
    sim.connect()

    nonce = hashlib.sha256(b"test_nonce").hexdigest()
    result = sim.send_challenge(nonce)

    assert result, "Simulator should accept challenge"
    print("✓ test_pico_simulator_challenge passed")


def test_pico_simulator_attestation():
    """Test PicoSimulator generates valid attestation data."""
    sim = PicoSimulator("n64_mips")
    sim.connect()
    sim.send_challenge("test_nonce")

    data = sim.read_attestation()

    assert data is not None, "Should generate attestation data"
    assert "ctrl_port_timing" in data
    assert "rom_execution" in data
    assert "bus_jitter" in data
    assert "board_id" in data

    # Verify CV is above emulation threshold
    cv = data["ctrl_port_timing"]["cv"]
    assert cv > 0.0001, f"CV should be > 0.0001, got {cv}"

    # Verify ROM hash time is in realistic range
    hash_time = data["rom_execution"]["time_us"]
    assert 100000 <= hash_time <= 10000000, f"Hash time out of range: {hash_time}"

    print("✓ test_pico_simulator_attestation passed")


def test_pico_simulator_different_consoles():
    """Test PicoSimulator with different console types."""
    for console_type in ["nes_6502", "snes_65c816", "genesis_68000", "ps1_mips"]:
        sim = PicoSimulator(console_type)
        sim.connect()
        data = sim.read_attestation()

        assert data is not None, f"Should generate data for {console_type}"

        # Verify timing matches console profile
        profile = CONSOLE_PROFILES[console_type]
        expected_time = profile["rom_hash_time_us"]
        actual_time = data["rom_execution"]["time_us"]

        # Should be within ±10% of expected
        ratio = actual_time / expected_time
        assert 0.9 <= ratio <= 1.1, f"Timing mismatch for {console_type}: {ratio}"

    print("✓ test_pico_simulator_different_consoles passed")


def test_build_attestation_payload_structure():
    """Test attestation payload has correct structure."""
    pico_data = {
        "ctrl_port_timing": {"mean_ns": 250000, "stdev_ns": 1250, "cv": 0.005, "samples": 500},
        "rom_execution": {"hash_result": "abc123", "time_us": 847000},
        "bus_jitter": {"stdev_ns": 1250, "samples": 500},
        "board_id": "RP2040-TEST-123",
        "firmware_version": "1.0.0",
    }

    payload = build_attestation_payload(
        miner_name="test-miner",
        wallet_id="RTCtest123",
        console_type="n64_mips",
        pico_data=pico_data,
        nonce="test_nonce",
    )

    # Verify top-level structure
    assert "miner" in payload
    assert "miner_id" in payload
    assert "wallet" in payload
    assert "nonce" in payload
    assert "report" in payload
    assert "device" in payload
    assert "signals" in payload
    assert "fingerprint" in payload

    # Verify device info
    assert payload["device"]["family"] == "console"
    assert payload["device"]["arch"] == "n64_mips"
    assert payload["device"]["bridge_type"] == "pico_serial"

    # Verify fingerprint
    assert payload["fingerprint"]["bridge_type"] == "pico_serial"
    assert "checks" in payload["fingerprint"]

    print("✓ test_build_attestation_payload_structure passed")


def test_build_attestation_payload_entropy_score():
    """Test entropy score calculation."""
    # High CV = high entropy
    pico_data_high = {
        "ctrl_port_timing": {"cv": 0.01, "samples": 500},
        "rom_execution": {"hash_result": "abc", "time_us": 847000},
        "bus_jitter": {"stdev_ns": 1250, "samples": 500},
        "board_id": "TEST",
        "firmware_version": "1.0.0",
    }

    payload_high = build_attestation_payload(
        "test", "RTCtest", "n64_mips", pico_data_high, "nonce"
    )

    # Low CV = low entropy (but still above threshold)
    pico_data_low = {
        "ctrl_port_timing": {"cv": 0.0002, "samples": 500},
        "rom_execution": {"hash_result": "abc", "time_us": 847000},
        "bus_jitter": {"stdev_ns": 1250, "samples": 500},
        "board_id": "TEST",
        "firmware_version": "1.0.0",
    }

    payload_low = build_attestation_payload(
        "test", "RTCtest", "n64_mips", pico_data_low, "nonce"
    )

    assert payload_high["report"]["entropy_score"] > payload_low["report"]["entropy_score"]
    print("✓ test_build_attestation_payload_entropy_score passed")


def test_build_attestation_payload_checks():
    """Test fingerprint checks are properly built."""
    pico_data = {
        "ctrl_port_timing": {"cv": 0.005, "samples": 500},
        "rom_execution": {"hash_result": "abc", "time_us": 847000},
        "bus_jitter": {"stdev_ns": 1250, "samples": 500},
        "board_id": "TEST",
        "firmware_version": "1.0.0",
    }

    payload = build_attestation_payload("test", "RTCtest", "n64_mips", pico_data, "nonce")

    checks = payload["fingerprint"]["checks"]

    # All checks should pass with good data
    assert checks["ctrl_port_timing"]["passed"]
    assert checks["rom_execution_timing"]["passed"]
    assert checks["bus_jitter"]["passed"]
    assert checks["anti_emulation"]["passed"]
    assert payload["fingerprint"]["all_passed"]

    print("✓ test_build_attestation_payload_checks passed")


def test_build_attestation_payload_emulation_detection():
    """Test that low CV triggers emulation detection."""
    pico_data_emulator = {
        "ctrl_port_timing": {"cv": 0.00005, "samples": 500},  # Below threshold
        "rom_execution": {"hash_result": "abc", "time_us": 847000},
        "bus_jitter": {"stdev_ns": 1250, "samples": 500},
        "board_id": "TEST",
        "firmware_version": "1.0.0",
    }

    payload = build_attestation_payload("test", "RTCtest", "n64_mips", pico_data_emulator, "nonce")

    checks = payload["fingerprint"]["checks"]

    assert not checks["ctrl_port_timing"]["passed"]
    assert not checks["anti_emulation"]["passed"]
    assert not payload["fingerprint"]["all_passed"]
    assert "low_timing_cv" in checks["anti_emulation"]["data"]["emulator_indicators"]

    print("✓ test_build_attestation_payload_emulation_detection passed")


def test_console_profiles_complete():
    """Test all RIP-304 consoles have profiles."""
    required_consoles = [
        "nes_6502",
        "snes_65c816",
        "n64_mips",
        "gameboy_z80",
        "gameboy_color_z80",
        "gba_arm7",
        "sms_z80",
        "genesis_68000",
        "saturn_sh2",
        "ps1_mips",
    ]

    for console in required_consoles:
        assert console in CONSOLE_PROFILES, f"Missing profile for {console}"

        profile = CONSOLE_PROFILES[console]
        assert "model" in profile
        assert "cpu" in profile
        assert "protocol" in profile
        assert "rom_hash_time_us" in profile

    print("✓ test_console_profiles_complete passed")


def run_all_tests():
    """Run all Pico bridge miner tests."""
    print("=" * 60)
    print("Pico Bridge Miner Tests (RIP-304)")
    print("=" * 60)

    tests = [
        test_pico_simulator_connection,
        test_pico_simulator_challenge,
        test_pico_simulator_attestation,
        test_pico_simulator_different_consoles,
        test_build_attestation_payload_structure,
        test_build_attestation_payload_entropy_score,
        test_build_attestation_payload_checks,
        test_build_attestation_payload_emulation_detection,
        test_console_profiles_complete,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} ERROR: {e}")
            failed += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
