"""
Test suite for hardware fingerprint validation in RustChain.

This module tests the hardware fingerprinting system which ensures
miners are running on genuine vintage hardware.

Author: Atlas (AI Bounty Hunter)
Date: 2026-02-28
Reward: 10 RTC for first merged PR
"""

import hashlib
import pytest
import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

# Modules are pre-loaded in conftest.py
integrated_node = sys.modules["integrated_node"]
_compute_hardware_id = integrated_node._compute_hardware_id
validate_fingerprint_data = integrated_node.validate_fingerprint_data


class TestHardwareIDUniqueness:
    """Test that hardware IDs are unique for different inputs."""

    def test_different_serial_numbers_produce_different_ids(self):
        """Verify that different CPU serials produce different hardware IDs."""
        device1 = {
            "device_model": "G4",
            "device_arch": "ppc",
            "device_family": "7447",
            "cores": 1,
            "cpu_serial": "1234567890"
        }
        device2 = {
            "device_model": "G4",
            "device_arch": "ppc",
            "device_family": "7447",
            "cores": 1,
            "cpu_serial": "0987654321"
        }

        id1 = _compute_hardware_id(device1, source_ip="1.1.1.1")
        id2 = _compute_hardware_id(device2, source_ip="1.1.1.1")

        assert id1 != id2, "Different serial numbers should produce different IDs"
        assert len(id1) == 32, "Hardware ID should be 32 characters"

    def test_different_core_counts_produce_different_ids(self):
        """Verify that different core counts produce different hardware IDs."""
        device1 = {
            "device_model": "G5",
            "device_arch": "ppc64",
            "device_family": "970",
            "cores": 1,
            "cpu_serial": "ABC123"
        }
        device2 = {
            "device_model": "G5",
            "device_arch": "ppc64",
            "device_family": "970",
            "cores": 2,
            "cpu_serial": "ABC123"
        }

        id1 = _compute_hardware_id(device1, source_ip="1.1.1.1")
        id2 = _compute_hardware_id(device2, source_ip="1.1.1.1")

        assert id1 != id2, "Different core counts should produce different IDs"

    def test_different_architectures_produce_different_ids(self):
        """Verify that different architectures produce different hardware IDs."""
        device1 = {
            "device_model": "G4",
            "device_arch": "ppc",
            "device_family": "7447",
            "cores": 2,
            "cpu_serial": "SERIAL1"
        }
        device2 = {
            "device_model": "G5",
            "device_arch": "ppc64",
            "device_family": "970",
            "cores": 2,
            "cpu_serial": "SERIAL2"
        }

        id1 = _compute_hardware_id(device1, source_ip="1.1.1.1")
        id2 = _compute_hardware_id(device2, source_ip="1.1.1.1")

        assert id1 != id2, "Different architectures should produce different IDs"


class TestHardwareIDConsistency:
    """Test that hardware IDs are consistent for same inputs."""

    def test_same_device_same_ip_produces_same_id(self):
        """Verify that identical inputs with same IP produce identical IDs."""
        device = {
            "device_model": "G5",
            "device_arch": "ppc64",
            "device_family": "970",
            "cores": 2,
            "cpu_serial": "ABC123"
        }
        signals = {"macs": ["00:11:22:33:44:55"]}

        id1 = _compute_hardware_id(device, signals, source_ip="2.2.2.2")
        id2 = _compute_hardware_id(device, signals, source_ip="2.2.2.2")

        assert id1 == id2, "Same device with same IP should produce same ID"

    def test_same_device_different_ip_produces_different_id(self):
        """Verify that same device with different IP produces different ID."""
        device = {
            "device_model": "G4",
            "device_arch": "ppc",
            "device_family": "7447",
            "cores": 1,
            "cpu_serial": "TEST123"
        }
        signals = {"macs": ["AA:BB:CC:DD:EE:FF"]}

        id1 = _compute_hardware_id(device, signals, source_ip="192.168.1.1")
        id2 = _compute_hardware_id(device, signals, source_ip="10.0.0.1")

        assert id1 != id2, "Same device with different IP should produce different ID"


class TestFingerprintValidation:
    """Test fingerprint validation logic."""

    def test_validate_fingerprint_data_no_data(self):
        """Missing fingerprint payload must fail validation."""
        passed, reason = validate_fingerprint_data(None)
        assert passed is False, "None data should fail validation"
        assert reason == "missing_fingerprint_data", "Error should indicate missing data"

    def test_validate_fingerprint_data_empty_dict(self):
        """Empty dictionary should fail validation."""
        passed, reason = validate_fingerprint_data({})
        assert passed is False, "Empty dict should fail validation"

    def test_validate_fingerprint_data_valid_data(self):
        """Valid fingerprint data should pass validation."""
        fingerprint = {
            "checks": {
                "anti_emulation": {
                    "passed": True,
                    "data": {
                        "vm_indicators": [],
                        "dmesg_scanned": True,
                        "paths_checked": 42,
                        "passed": True
                    }
                }
            }
        }
        passed, reason = validate_fingerprint_data(fingerprint)
        assert passed is True, "Valid fingerprint should pass"


class TestAntiEmulationDetection:
    """Test VM detection and anti-emulation checks."""

    def test_vm_detection_with_vboxguest(self):
        """Verify detection of VirtualBox guest indicators."""
        fingerprint = {
            "checks": {
                "anti_emulation": {
                    "passed": False,
                    "data": {
                        "vm_indicators": ["vboxguest"],
                        "passed": False
                    }
                }
            }
        }
        passed, reason = validate_fingerprint_data(fingerprint)
        assert passed is False, "VM detection should fail with vboxguest"
        assert "vm_detected" in reason, "Reason should mention VM detection"

    def test_vm_detection_with_no_indicators(self):
        """Verify no false positives when real hardware reports no VM indicators."""
        fingerprint = {
            "checks": {
                "anti_emulation": {
                    "passed": True,
                    "data": {
                        "vm_indicators": [],
                        "dmesg_scanned": True,
                        "paths_checked": 38,
                        "passed": True
                    }
                }
            }
        }
        passed, reason = validate_fingerprint_data(fingerprint)
        assert passed is True, "No VM indicators should pass validation"

    def test_vm_detection_with_multiple_indicators(self):
        """Verify detection with multiple VM indicators."""
        fingerprint = {
            "checks": {
                "anti_emulation": {
                    "passed": False,
                    "data": {
                        "vm_indicators": ["vboxguest", "vmware", "parallels"],
                        "passed": False
                    }
                }
            }
        }
        passed, reason = validate_fingerprint_data(fingerprint)
        assert passed is False, "Multiple VM indicators should fail"


class TestEvidenceRequirements:
    """Test that evidence is required for all checks."""

    def test_no_evidence_fails(self):
        """Verify rejection if no raw evidence is provided."""
        fingerprint = {
            "checks": {
                "anti_emulation": {
                    "passed": True,
                    "data": {}  # Missing evidence
                }
            }
        }
        passed, reason = validate_fingerprint_data(fingerprint)
        assert passed is False, "Checks with no evidence should fail"
        assert reason == "anti_emulation_no_evidence", "Error should indicate missing evidence"

    def test_empty_evidence_fails(self):
        """Verify rejection if evidence list is empty."""
        fingerprint = {
            "checks": {
                "anti_emulation": {
                    "passed": True,
                    "data": {
                        "vm_indicators": [],
                        "passed": True
                    }
                }
            }
        }
        passed, reason = validate_fingerprint_data(fingerprint)
        assert passed is False, "Empty evidence should fail"


class TestClockDriftDetection:
    """Test clock drift detection and timing validation."""

    def test_timing_too_uniform_fails(self):
        """Verify rejection of too uniform timing (clock drift check)."""
        fingerprint = {
            "checks": {
                "clock_drift": {
                    "passed": True,
                    "data": {
                        "cv": 0.000001,  # Too stable
                        "samples": 100
                    }
                }
            }
        }
        passed, reason = validate_fingerprint_data(fingerprint)
        assert passed is False, "Too uniform timing should fail"
        assert "timing_too_uniform" in reason, "Reason should mention timing issue"

    def test_clock_drift_insufficient_samples(self):
        """Clock drift cannot pass with extremely low sample count."""
        fingerprint = {
            "checks": {
                "clock_drift": {
                    "passed": True,
                    "data": {
                        "cv": 0.02,
                        "samples": 1  # Too few samples
                    }
                }
            }
        }
        passed, reason = validate_fingerprint_data(fingerprint)
        assert passed is False, "Insufficient samples should fail"
        assert reason.startswith("clock_drift_insufficient_samples"), "Error should mention samples"

    def test_valid_clock_drift_passes(self):
        """Valid clock drift data should pass."""
        fingerprint = {
            "checks": {
                "clock_drift": {
                    "passed": True,
                    "data": {
                        "cv": 0.15,  # Reasonable variation
                        "samples": 50
                    }
                }
            }
        }
        passed, reason = validate_fingerprint_data(fingerprint)
        assert passed is True, "Valid clock drift should pass"


class TestVintageHardwareTiming:
    """Test vintage hardware-specific timing requirements."""

    def test_vintage_stability_too_high(self):
        """Verify rejection of suspicious stability on vintage hardware."""
        claimed_device = {
            "device_arch": "G4"
        }
        fingerprint = {
            "checks": {
                "clock_drift": {
                    "passed": True,
                    "data": {
                        "cv": 0.001,  # Too stable for G4
                        "samples": 100
                    }
                }
            }
        }
        passed, reason = validate_fingerprint_data(fingerprint, claimed_device)
        assert passed is False, "Suspiciously stable vintage timing should fail"
        assert "vintage_timing_too_stable" in reason, "Reason should mention vintage timing"

    def test_vintage_normal_variation_passes(self):
        """Normal variation for vintage hardware should pass."""
        claimed_device = {
            "device_arch": "G4"
        }
        fingerprint = {
            "checks": {
                "clock_drift": {
                    "passed": True,
                    "data": {
                        "cv": 0.05,  # Normal variation
                        "samples": 100
                    }
                }
            }
        }
        passed, reason = validate_fingerprint_data(fingerprint, claimed_device)
        assert passed is True, "Normal vintage timing should pass"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_unicode_serial_number(self):
        """Verify handling of Unicode serial numbers."""
        device = {
            "device_model": "G5",
            "device_arch": "ppc64",
            "device_family": "970",
            "cores": 2,
            "cpu_serial": "ABC123_测试"
        }
        id1 = _compute_hardware_id(device, source_ip="1.1.1.1")
        id2 = _compute_hardware_id(device, source_ip="1.1.1.1")
        assert id1 == id2, "Unicode serial should be handled consistently"

    def test_empty_signals(self):
        """Verify handling of empty signals dictionary."""
        device = {
            "device_model": "G4",
            "device_arch": "ppc",
            "device_family": "7447",
            "cores": 1,
            "cpu_serial": "SERIAL"
        }
        signals = {}
        id1 = _compute_hardware_id(device, signals, source_ip="1.1.1.1")
        assert len(id1) == 32, "Empty signals should still produce valid ID"

    def test_multiple_mac_addresses(self):
        """Verify handling of multiple MAC addresses."""
        device = {
            "device_model": "G5",
            "device_arch": "ppc64",
            "device_family": "970",
            "cores": 2,
            "cpu_serial": "MAC123"
        }
        signals = {
            "macs": [
                "00:11:22:33:44:55",
                "AA:BB:CC:DD:EE:FF",
                "11:22:33:44:55:66"
            ]
        }
        id1 = _compute_hardware_id(device, signals, source_ip="1.1.1.1")
        assert len(id1) == 32, "Multiple MACs should produce valid ID"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
