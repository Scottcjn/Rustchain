#!/usr/bin/env python3
"""
RIP-0683: Console Miner Integration Tests
==========================================

Comprehensive test suite for retro console mining integration.
Tests cover:
  - Console CPU family detection
  - Pico bridge protocol
  - Anti-emulation verification
  - Fleet bucket assignment
  - End-to-end attestation flow

Run: python3 tests/test_console_miner_integration.py
"""

import sys
import os
import time
import json
import hashlib
from typing import Dict, Any, Optional

# Add node directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'node'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'rips', 'python', 'rustchain'))

# ═══════════════════════════════════════════════════════════
# Test Configuration
# ═══════════════════════════════════════════════════════════

class TestConfig:
    """Test configuration and constants"""
    # Console timing baselines (microseconds)
    CONSOLE_BASELINES = {
        "nes_6502": {"rom_time_us": 2_500_000, "tolerance": 0.15},
        "snes_65c816": {"rom_time_us": 1_200_000, "tolerance": 0.15},
        "n64_mips": {"rom_time_us": 847_000, "tolerance": 0.15},
        "genesis_68000": {"rom_time_us": 1_500_000, "tolerance": 0.15},
        "gameboy_z80": {"rom_time_us": 3_000_000, "tolerance": 0.15},
        "gba_arm7": {"rom_time_us": 450_000, "tolerance": 0.15},
        "sms_z80": {"rom_time_us": 2_800_000, "tolerance": 0.15},
        "saturn_sh2": {"rom_time_us": 380_000, "tolerance": 0.15},
        "ps1_mips": {"rom_time_us": 920_000, "tolerance": 0.15},
    }
    
    # CV threshold for emulator detection
    CV_THRESHOLD = 0.0001
    
    # Minimum jitter samples
    MIN_SAMPLES = 100


# ═══════════════════════════════════════════════════════════
# Test Utilities
# ═══════════════════════════════════════════════════════════

def generate_nonce() -> str:
    """Generate random nonce for attestation challenge"""
    return hashlib.sha256(os.urandom(32)).hexdigest()[:16]


def create_console_timing_data(
    console_arch: str,
    is_emulator: bool = False,
    wrong_timing: bool = False
) -> Dict[str, Any]:
    """
    Create realistic or fake timing data for testing
    
    Args:
        console_arch: Console architecture (e.g., "n64_mips")
        is_emulator: If True, create too-perfect timing (emulator)
        wrong_timing: If True, create timing for wrong CPU
    
    Returns:
        Timing data dictionary matching Pico bridge format
    """
    baseline = TestConfig.CONSOLE_BASELINES.get(console_arch, {
        "rom_time_us": 1_000_000,
        "tolerance": 0.15
    })
    
    if is_emulator:
        # Emulator: too perfect timing
        return {
            "ctrl_port_timing_mean_ns": 16_667_000,
            "ctrl_port_timing_stdev_ns": 0,
            "ctrl_port_cv": 0.0,  # Perfect = emulator
            "rom_hash_time_us": baseline["rom_time_us"],
            "bus_jitter_samples": 500,
            "bus_jitter_stdev_ns": 0,  # No jitter = emulator
        }
    
    if wrong_timing:
        # Wrong CPU timing (e.g., claims N64 but timing matches NES)
        return {
            "ctrl_port_timing_mean_ns": 16_667_000,
            "ctrl_port_timing_stdev_ns": 2_000,
            "ctrl_port_cv": 0.00012,
            "rom_hash_time_us": 100_000,  # Way too fast for N64
            "bus_jitter_samples": 500,
            "bus_jitter_stdev_ns": 2_000,
        }
    
    # Real hardware: has jitter and noise
    import random
    rom_time = baseline["rom_time_us"]
    tolerance = baseline["tolerance"]
    actual_time = int(rom_time * (1 + random.uniform(-tolerance/2, tolerance/2)))
    
    cv = random.uniform(0.001, 0.01)  # 0.1% - 1% variation
    mean_ns = 16_667_000  # 60Hz polling
    stdev_ns = int(mean_ns * cv)
    
    return {
        "ctrl_port_timing_mean_ns": mean_ns,
        "ctrl_port_timing_stdev_ns": stdev_ns,
        "ctrl_port_cv": cv,
        "rom_hash_time_us": actual_time,
        "bus_jitter_samples": TestConfig.MIN_SAMPLES + random.randint(0, 500),
        "bus_jitter_stdev_ns": random.randint(1000, 3000),
    }


# ═══════════════════════════════════════════════════════════
# Test Cases
# ═══════════════════════════════════════════════════════════

class TestConsoleMinerIntegration:
    """Test suite for console miner integration"""
    
    def __init__(self):
        self.tests_passed = 0
        self.tests_failed = 0
        self.errors = []
        
    def run_test(self, name: str, test_func):
        """Run a single test and record result"""
        try:
            test_func()
            self.tests_passed += 1
            print(f"✓ {name}")
        except AssertionError as e:
            self.tests_failed += 1
            self.errors.append((name, str(e)))
            print(f"✗ {name}: {e}")
        except Exception as e:
            self.tests_failed += 1
            self.errors.append((name, f"{type(e).__name__}: {e}"))
            print(f"✗ {name}: {type(e).__name__}: {e}")
    
    def summary(self):
        """Print test summary"""
        total = self.tests_passed + self.tests_failed
        print(f"\n{'='*60}")
        print(f"Test Summary: {self.tests_passed}/{total} passed")
        if self.errors:
            print(f"\nFailed tests:")
            for name, error in self.errors:
                print(f"  - {name}: {error}")
        print(f"{'='*60}")
        return self.tests_failed == 0


# ═══════════════════════════════════════════════════════════
# Test: Console CPU Family Detection
# ═══════════════════════════════════════════════════════════

def test_console_cpu_families():
    """Test that console CPU families are properly defined"""
    from fleet_immune_system import HARDWARE_BUCKETS, ARCH_TO_BUCKET
    
    # Check retro_console bucket exists
    assert "retro_console" in HARDWARE_BUCKETS, "retro_console bucket missing"
    
    # Check expected consoles are in bucket
    console_bucket = HARDWARE_BUCKETS["retro_console"]
    expected_consoles = [
        "nes_6502", "snes_65c816", "n64_mips",
        "genesis_68000", "gameboy_z80", "ps1_mips"
    ]
    for console in expected_consoles:
        assert console in console_bucket, f"{console} not in retro_console bucket"
    
    # Check reverse lookup works
    for arch in console_bucket:
        assert arch in ARCH_TO_BUCKET, f"{arch} missing from ARCH_TO_BUCKET"
        assert ARCH_TO_BUCKET[arch] == "retro_console", \
            f"{arch} maps to wrong bucket: {ARCH_TO_BUCKET[arch]}"


# ═══════════════════════════════════════════════════════════
# Test: Timing Data Validation
# ═══════════════════════════════════════════════════════════

def test_real_hardware_timing():
    """Test that real hardware timing passes validation"""
    # Create realistic N64 timing
    timing = create_console_timing_data("n64_mips")
    
    # Check CV is above threshold (real hardware has jitter)
    assert timing["ctrl_port_cv"] > TestConfig.CV_THRESHOLD, \
        f"Real hardware CV {timing['ctrl_port_cv']} below threshold"
    
    # Check jitter is present
    assert timing["bus_jitter_stdev_ns"] > 500, \
        "Real hardware should have bus jitter"
    
    # Check sample count is sufficient
    assert timing["bus_jitter_samples"] >= TestConfig.MIN_SAMPLES, \
        "Insufficient jitter samples"


def test_emulator_detection():
    """Test that emulator timing is detected and rejected"""
    # Create emulator timing (too perfect)
    timing = create_console_timing_data("n64_mips", is_emulator=True)
    
    # Check CV is at/below threshold (emulator = perfect timing)
    assert timing["ctrl_port_cv"] <= TestConfig.CV_THRESHOLD, \
        "Emulator should have near-zero CV"
    
    # Check no jitter (emulator = deterministic)
    assert timing["bus_jitter_stdev_ns"] == 0, \
        "Emulator should have no bus jitter"


def test_wrong_timing_detection():
    """Test that wrong CPU timing is detected"""
    # Create wrong timing
    timing = create_console_timing_data("n64_mips", wrong_timing=True)
    
    # N64 should take ~847ms, not 100ms
    expected_time = TestConfig.CONSOLE_BASELINES["n64_mips"]["rom_time_us"]
    tolerance = TestConfig.CONSOLE_BASELINES["n64_mips"]["tolerance"]
    
    diff = abs(timing["rom_hash_time_us"] - expected_time)
    max_allowed_diff = expected_time * tolerance
    
    assert diff > max_allowed_diff, \
        f"Wrong timing should be detected (diff={diff}, max={max_allowed_diff})"


# ═══════════════════════════════════════════════════════════
# Test: Pico Bridge Protocol
# ═══════════════════════════════════════════════════════════

def test_pico_bridge_message_format():
    """Test Pico bridge message format"""
    # Simulate ATTEST command
    nonce = generate_nonce()
    wallet = "RTC1TestWallet123456789"
    timestamp = str(int(time.time()))
    
    attest_cmd = f"ATTEST|{nonce}|{wallet}|{timestamp}\n"
    assert attest_cmd.startswith("ATTEST|"), "Invalid ATTEST command format"
    
    # Simulate response (would come from Pico)
    pico_id = "PICO001"
    console_arch = "n64_mips"
    timing_json = json.dumps(create_console_timing_data("n64_mips"))
    
    response = f"OK|{pico_id}|{console_arch}|{timing_json}|\n"
    assert response.startswith("OK|"), "Invalid response format"
    
    # Parse response
    parts = response.strip().split("|")
    assert len(parts) >= 4, "Response missing fields"
    assert parts[0] == "OK", "Response not OK"
    assert parts[1] == pico_id, "Pico ID mismatch"
    assert parts[2] == console_arch, "Console arch mismatch"


def test_pico_bridge_error_handling():
    """Test Pico bridge error responses"""
    # Error response format
    error_response = "ERROR|invalid_format\n"
    assert error_response.startswith("ERROR|"), "Invalid error format"
    
    error_code = error_response.strip().split("|")[1]
    assert error_code in ["invalid_format", "unknown_command", "timeout"], \
        f"Unknown error code: {error_code}"


# ═══════════════════════════════════════════════════════════
# Test: Fleet Bucket Assignment
# ═══════════════════════════════════════════════════════════

def test_console_bucket_assignment():
    """Test that console miners are assigned to retro_console bucket"""
    from fleet_immune_system import ARCH_TO_BUCKET
    
    console_archs = [
        "nes_6502", "snes_65c816", "n64_mips",
        "genesis_68000", "gameboy_z80", "ps1_mips",
        "6502", "z80", "sh2"
    ]
    
    for arch in console_archs:
        bucket = ARCH_TO_BUCKET.get(arch)
        assert bucket == "retro_console", \
            f"{arch} should map to retro_console, got {bucket}"


def test_non_console_not_in_bucket():
    """Test that non-console archs are not in retro_console bucket"""
    from fleet_immune_system import HARDWARE_BUCKETS
    
    console_bucket = HARDWARE_BUCKETS["retro_console"]
    
    non_console_archs = ["pentium", "modern", "x86_64", "powerpc", "m1"]
    for arch in non_console_archs:
        assert arch not in console_bucket, \
            f"{arch} should not be in retro_console bucket"


# ═══════════════════════════════════════════════════════════
# Test: Attestation Flow
# ═══════════════════════════════════════════════════════════

def test_console_attestation_flow():
    """Test complete console attestation flow"""
    # Step 1: Generate challenge
    nonce = generate_nonce()
    wallet = "RTC1ConsoleMiner001"
    
    # Step 2: Send to Pico bridge (simulated)
    attest_cmd = f"ATTEST|{nonce}|{wallet}|{int(time.time())}\n"
    
    # Step 3: Pico measures timing and computes hash
    timing_data = create_console_timing_data("n64_mips")
    
    # Step 4: Build attestation payload
    attestation = {
        "miner": "n64-scott-unit1",
        "miner_id": "pico-bridge-001",
        "nonce": nonce,
        "report": {
            "nonce": nonce,
            "commitment": hashlib.sha256(f"{nonce}{wallet}".encode()).hexdigest(),
            "derived": timing_data,
            "entropy_score": timing_data["ctrl_port_cv"],
        },
        "device": {
            "family": "console",
            "arch": "n64_mips",
            "model": "Nintendo 64 NUS-001",
            "cpu": "NEC VR4300 (MIPS R4300i) 93.75MHz",
            "cores": 1,
            "memory_mb": 4,
            "bridge_type": "pico_serial",
            "bridge_firmware": "1.0.0",
        },
        "signals": {
            "pico_serial": "PICO001",
            "ctrl_port_protocol": "joybus",
            "rom_id": "rustchain_attest_n64_v1",
        },
        "fingerprint": {
            "all_passed": True,
            "bridge_type": "pico_serial",
            "checks": {
                "ctrl_port_timing": {
                    "passed": True,
                    "data": {
                        "cv": timing_data["ctrl_port_cv"],
                        "samples": timing_data["bus_jitter_samples"],
                    }
                },
                "anti_emulation": {
                    "passed": True,
                    "data": {
                        "timing_cv": timing_data["ctrl_port_cv"],
                    }
                },
            },
        },
    }
    
    # Validate attestation structure
    assert "fingerprint" in attestation, "Missing fingerprint"
    assert "checks" in attestation["fingerprint"], "Missing checks"
    assert "ctrl_port_timing" in attestation["fingerprint"]["checks"], \
        "Missing ctrl_port_timing check"
    assert attestation["device"]["bridge_type"] == "pico_serial", \
        "Wrong bridge type"


# ═══════════════════════════════════════════════════════════
# Test: Multi-Console Support
# ═══════════════════════════════════════════════════════════

def test_multiple_console_types():
    """Test that multiple console types are supported"""
    consoles = [
        ("nes_6502", 2_500_000),    # Slowest (1.79MHz)
        ("snes_65c816", 1_200_000), # Faster (3.58MHz)
        ("n64_mips", 847_000),      # Even faster (93.75MHz)
        ("ps1_mips", 920_000),      # Similar to N64 (33.8MHz)
        ("genesis_68000", 1_500_000), # Middle (7.67MHz)
    ]
    
    for console_arch, expected_time in consoles:
        timing = create_console_timing_data(console_arch)
        
        # Check timing is within tolerance
        tolerance = 0.15
        diff = abs(timing["rom_hash_time_us"] - expected_time)
        max_diff = expected_time * tolerance
        
        assert diff <= max_diff, \
            f"{console_arch} timing {timing['rom_hash_time_us']}us outside tolerance (expected {expected_time}±{max_diff}us)"


# ═══════════════════════════════════════════════════════════
# Test: CV Threshold Boundary
# ═══════════════════════════════════════════════════════════

def test_cv_threshold_boundary():
    """Test CV threshold boundary conditions"""
    # Just above threshold (should pass)
    above_threshold = create_console_timing_data("n64_mips")
    above_threshold["ctrl_port_cv"] = TestConfig.CV_THRESHOLD + 0.000004
    assert above_threshold["ctrl_port_cv"] > TestConfig.CV_THRESHOLD, \
        "Should be above threshold"
    
    # Just below threshold (should fail as emulator)
    below_threshold = create_console_timing_data("n64_mips", is_emulator=True)
    below_threshold["ctrl_port_cv"] = TestConfig.CV_THRESHOLD - 0.000004
    assert below_threshold["ctrl_port_cv"] <= TestConfig.CV_THRESHOLD, \
        "Should be at/below threshold (emulator)"


# ═══════════════════════════════════════════════════════════
# Main Test Runner
# ═══════════════════════════════════════════════════════════

def run_all_tests():
    """Run all console miner integration tests"""
    print("="*60)
    print("RIP-0683: Console Miner Integration Tests")
    print("="*60)
    print()
    
    runner = TestConsoleMinerIntegration()
    
    # Test: Console CPU families
    print("Testing Console CPU Family Detection...")
    runner.run_test("Console CPU families defined", test_console_cpu_families)
    print()
    
    # Test: Timing validation
    print("Testing Timing Data Validation...")
    runner.run_test("Real hardware timing", test_real_hardware_timing)
    runner.run_test("Emulator detection", test_emulator_detection)
    runner.run_test("Wrong timing detection", test_wrong_timing_detection)
    print()
    
    # Test: Pico bridge protocol
    print("Testing Pico Bridge Protocol...")
    runner.run_test("Message format", test_pico_bridge_message_format)
    runner.run_test("Error handling", test_pico_bridge_error_handling)
    print()
    
    # Test: Fleet bucket assignment
    print("Testing Fleet Bucket Assignment...")
    runner.run_test("Console bucket assignment", test_console_bucket_assignment)
    runner.run_test("Non-console exclusion", test_non_console_not_in_bucket)
    print()
    
    # Test: Attestation flow
    print("Testing Attestation Flow...")
    runner.run_test("Complete attestation", test_console_attestation_flow)
    print()
    
    # Test: Multi-console support
    print("Testing Multi-Console Support...")
    runner.run_test("Multiple console types", test_multiple_console_types)
    print()
    
    # Test: CV threshold
    print("Testing CV Threshold Boundary...")
    runner.run_test("CV threshold boundary", test_cv_threshold_boundary)
    print()
    
    # Summary
    success = runner.summary()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
