#!/usr/bin/env python3
"""
Tests for Pico Serial Bridge Validation (RIP-304)
==================================================

Tests the check_pico_bridge_attestation function in fingerprint_checks.py
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fingerprint_checks import check_pico_bridge_attestation


def test_pico_bridge_valid_attestation():
    """Test valid Pico bridge attestation passes."""
    fingerprint_data = {
        "bridge_type": "pico_serial",
        "checks": {
            "ctrl_port_timing": {
                "data": {"cv": 0.005, "samples": 500}
            },
            "rom_execution_timing": {
                "data": {"hash_time_us": 847000}
            },
            "bus_jitter": {
                "data": {"jitter_stdev_ns": 1250}
            },
            "anti_emulation": {
                "data": {"emulator_indicators": []}
            }
        }
    }

    passed, data = check_pico_bridge_attestation(fingerprint_data)

    assert passed, f"Valid attestation should pass, got: {data}"
    assert data["bridge_type"] == "pico_serial"
    assert data["ctrl_port_timing"]["passed"]
    assert data["rom_execution_timing"]["passed"]
    assert data["bus_jitter"]["passed"]
    assert data["anti_emulation"]["passed"]
    assert data["all_checks_passed"]
    print("✓ test_pico_bridge_valid_attestation passed")


def test_pico_bridge_emulation_detected_low_cv():
    """Test that low timing CV (emulator indicator) fails."""
    fingerprint_data = {
        "bridge_type": "pico_serial",
        "checks": {
            "ctrl_port_timing": {
                "data": {"cv": 0.00005, "samples": 500}  # Below 0.0001 threshold
            },
            "rom_execution_timing": {
                "data": {"hash_time_us": 847000}
            },
            "bus_jitter": {
                "data": {"jitter_stdev_ns": 1250}
            },
            "anti_emulation": {
                "data": {"emulator_indicators": ["low_timing_cv"]}
            }
        }
    }

    passed, data = check_pico_bridge_attestation(fingerprint_data)

    assert not passed, "Low CV should fail (emulator indicator)"
    assert not data["ctrl_port_timing"]["passed"]
    assert any("ctrl_port_timing_cv_too_low" in r for r in data["fail_reasons"])
    print("✓ test_pico_bridge_emulation_detected_low_cv passed")


def test_pico_bridge_rom_timing_too_fast():
    """Test that ROM execution too fast (modern CPU) fails."""
    fingerprint_data = {
        "bridge_type": "pico_serial",
        "checks": {
            "ctrl_port_timing": {
                "data": {"cv": 0.005, "samples": 500}
            },
            "rom_execution_timing": {
                "data": {"hash_time_us": 50000}  # 50ms - too fast for console
            },
            "bus_jitter": {
                "data": {"jitter_stdev_ns": 1250}
            },
            "anti_emulation": {
                "data": {"emulator_indicators": []}
            }
        }
    }

    passed, data = check_pico_bridge_attestation(fingerprint_data)

    assert not passed, "ROM timing too fast should fail"
    assert not data["rom_execution_timing"]["passed"]
    assert any("rom_execution_timing_out_of_range" in r for r in data["fail_reasons"])
    print("✓ test_pico_bridge_rom_timing_too_fast passed")


def test_pico_bridge_rom_timing_too_slow():
    """Test that ROM execution too slow (timeout) fails."""
    fingerprint_data = {
        "bridge_type": "pico_serial",
        "checks": {
            "ctrl_port_timing": {
                "data": {"cv": 0.005, "samples": 500}
            },
            "rom_execution_timing": {
                "data": {"hash_time_us": 15000000}  # 15s - too slow
            },
            "bus_jitter": {
                "data": {"jitter_stdev_ns": 1250}
            },
            "anti_emulation": {
                "data": {"emulator_indicators": []}
            }
        }
    }

    passed, data = check_pico_bridge_attestation(fingerprint_data)

    assert not passed, "ROM timing too slow should fail"
    assert not data["rom_execution_timing"]["passed"]
    print("✓ test_pico_bridge_rom_timing_too_slow passed")


def test_pico_bridge_no_bus_jitter():
    """Test that missing bus jitter (emulator indicator) fails."""
    fingerprint_data = {
        "bridge_type": "pico_serial",
        "checks": {
            "ctrl_port_timing": {
                "data": {"cv": 0.005, "samples": 500}
            },
            "rom_execution_timing": {
                "data": {"hash_time_us": 847000}
            },
            "bus_jitter": {
                "data": {"jitter_stdev_ns": 50}  # Below 100ns threshold
            },
            "anti_emulation": {
                "data": {"emulator_indicators": []}
            }
        }
    }

    passed, data = check_pico_bridge_attestation(fingerprint_data)

    assert not passed, "Low bus jitter should fail"
    assert not data["bus_jitter"]["passed"]
    assert any("bus_jitter_too_low" in r for r in data["fail_reasons"])
    print("✓ test_pico_bridge_no_bus_jitter passed")


def test_pico_bridge_emulator_indicators_present():
    """Test that emulator indicators cause failure."""
    fingerprint_data = {
        "bridge_type": "pico_serial",
        "checks": {
            "ctrl_port_timing": {
                "data": {"cv": 0.005, "samples": 500}
            },
            "rom_execution_timing": {
                "data": {"hash_time_us": 847000}
            },
            "bus_jitter": {
                "data": {"jitter_stdev_ns": 1250}
            },
            "anti_emulation": {
                "data": {"emulator_indicators": ["perfect_timing_loop", "quantized_timing"]}
            }
        }
    }

    passed, data = check_pico_bridge_attestation(fingerprint_data)

    assert not passed, "Emulator indicators should fail"
    assert not data["anti_emulation"]["passed"]
    assert any("emulator_indicators_present" in r for r in data["fail_reasons"])
    print("✓ test_pico_bridge_emulator_indicators_present passed")


def test_pico_bridge_insufficient_samples():
    """Test that insufficient timing samples fails."""
    fingerprint_data = {
        "bridge_type": "pico_serial",
        "checks": {
            "ctrl_port_timing": {
                "data": {"cv": 0.005, "samples": 50}  # Below 100 sample minimum
            },
            "rom_execution_timing": {
                "data": {"hash_time_us": 847000}
            },
            "bus_jitter": {
                "data": {"jitter_stdev_ns": 1250}
            },
            "anti_emulation": {
                "data": {"emulator_indicators": []}
            }
        }
    }

    passed, data = check_pico_bridge_attestation(fingerprint_data)

    assert not passed, "Insufficient samples should fail"
    assert not data["ctrl_port_timing"]["passed"]
    print("✓ test_pico_bridge_insufficient_samples passed")


def test_pico_bridge_not_pico_skip():
    """Test that non-Pico bridge types are skipped."""
    fingerprint_data = {
        "bridge_type": "usb_serial",  # Not pico_serial
        "checks": {}
    }

    passed, data = check_pico_bridge_attestation(fingerprint_data)

    assert passed, "Non-Pico bridge should pass (skipped)"
    assert data["skipped"]
    assert data["reason"] == "not_pico_bridge"
    print("✓ test_pico_bridge_not_pico_skip passed")


def test_pico_bridge_explicit_bridge_type_override():
    """Test explicit bridge_type parameter overrides fingerprint data."""
    fingerprint_data = {
        "bridge_type": "usb_serial",  # Wrong type
        "checks": {
            "ctrl_port_timing": {
                "data": {"cv": 0.005, "samples": 500}
            },
            "rom_execution_timing": {
                "data": {"hash_time_us": 847000}
            },
            "bus_jitter": {
                "data": {"jitter_stdev_ns": 1250}
            },
            "anti_emulation": {
                "data": {"emulator_indicators": []}
            }
        }
    }

    # Override with explicit pico_serial
    passed, data = check_pico_bridge_attestation(fingerprint_data, bridge_type="pico_serial")

    assert passed, "Explicit bridge_type should override and pass"
    assert data["bridge_type"] == "pico_serial"
    print("✓ test_pico_bridge_explicit_bridge_type_override passed")


def test_pico_bridge_n64_profile():
    """Test realistic N64 attestation data."""
    fingerprint_data = {
        "bridge_type": "pico_serial",
        "checks": {
            "ctrl_port_timing": {
                "data": {"cv": 0.005, "samples": 512}  # N64 Joybus
            },
            "rom_execution_timing": {
                "data": {"hash_time_us": 847000}  # Reference: Legend of Elya
            },
            "bus_jitter": {
                "data": {"jitter_stdev_ns": 1250}
            },
            "anti_emulation": {
                "data": {"emulator_indicators": []}
            }
        }
    }

    passed, data = check_pico_bridge_attestation(fingerprint_data)

    assert passed, "N64 profile should pass"
    assert data["ctrl_port_timing"]["cv"] == 0.005
    assert data["rom_execution_timing"]["hash_time_us"] == 847000
    print("✓ test_pico_bridge_n64_profile passed")


def test_pico_bridge_nes_profile():
    """Test realistic NES attestation data."""
    fingerprint_data = {
        "bridge_type": "pico_serial",
        "checks": {
            "ctrl_port_timing": {
                "data": {"cv": 0.0075, "samples": 480}  # NES 60Hz polling
            },
            "rom_execution_timing": {
                "data": {"hash_time_us": 4500000}  # Slow 6502
            },
            "bus_jitter": {
                "data": {"jitter_stdev_ns": 1500}
            },
            "anti_emulation": {
                "data": {"emulator_indicators": []}
            }
        }
    }

    passed, data = check_pico_bridge_attestation(fingerprint_data)

    assert passed, "NES profile should pass"
    assert data["ctrl_port_timing"]["cv"] == 0.0075
    assert data["rom_execution_timing"]["hash_time_us"] == 4500000
    print("✓ test_pico_bridge_nes_profile passed")


def test_pico_bridge_boundary_cv_threshold():
    """Test CV exactly at threshold boundary."""
    # Just above threshold
    fingerprint_data_above = {
        "bridge_type": "pico_serial",
        "checks": {
            "ctrl_port_timing": {
                "data": {"cv": 0.00011, "samples": 500}
            },
            "rom_execution_timing": {"data": {"hash_time_us": 847000}},
            "bus_jitter": {"data": {"jitter_stdev_ns": 1250}},
            "anti_emulation": {"data": {"emulator_indicators": []}}
        }
    }

    passed, data = check_pico_bridge_attestation(fingerprint_data_above)
    assert passed, "CV just above threshold should pass"

    # Just below threshold
    fingerprint_data_below = {
        "bridge_type": "pico_serial",
        "checks": {
            "ctrl_port_timing": {
                "data": {"cv": 0.00009, "samples": 500}
            },
            "rom_execution_timing": {"data": {"hash_time_us": 847000}},
            "bus_jitter": {"data": {"jitter_stdev_ns": 1250}},
            "anti_emulation": {"data": {"emulator_indicators": []}}
        }
    }

    passed, data = check_pico_bridge_attestation(fingerprint_data_below)
    assert not passed, "CV just below threshold should fail"
    print("✓ test_pico_bridge_boundary_cv_threshold passed")


def test_pico_bridge_empty_fingerprint():
    """Test handling of empty/None fingerprint data."""
    passed, data = check_pico_bridge_attestation(None)

    assert passed, "None fingerprint should pass (skipped)"
    assert data["skipped"]

    passed, data = check_pico_bridge_attestation({})

    assert passed, "Empty fingerprint should pass (skipped)"
    assert data["skipped"]
    print("✓ test_pico_bridge_empty_fingerprint passed")


def run_all_tests():
    """Run all Pico bridge validation tests."""
    print("=" * 60)
    print("Pico Serial Bridge Validation Tests (RIP-304)")
    print("=" * 60)

    tests = [
        test_pico_bridge_valid_attestation,
        test_pico_bridge_emulation_detected_low_cv,
        test_pico_bridge_rom_timing_too_fast,
        test_pico_bridge_rom_timing_too_slow,
        test_pico_bridge_no_bus_jitter,
        test_pico_bridge_emulator_indicators_present,
        test_pico_bridge_insufficient_samples,
        test_pico_bridge_not_pico_skip,
        test_pico_bridge_explicit_bridge_type_override,
        test_pico_bridge_n64_profile,
        test_pico_bridge_nes_profile,
        test_pico_bridge_boundary_cv_threshold,
        test_pico_bridge_empty_fingerprint,
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
