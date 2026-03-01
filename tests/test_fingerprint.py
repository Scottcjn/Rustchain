import hashlib
import pytest
import sys
import os
from pathlib import Path

# Modules are pre-loaded in conftest.py
integrated_node = sys.modules["integrated_node"]
_compute_hardware_id = integrated_node._compute_hardware_id
validate_fingerprint_data = integrated_node.validate_fingerprint_data

# ── Reusable valid check payloads ──
# Tests that focus on one check must still include the other required check
# because the hardened validate_fingerprint_data requires BOTH anti_emulation
# AND clock_drift for modern hardware (only anti_emulation for vintage).

VALID_ANTI_EMULATION = {
    "passed": True,
    "data": {"vm_indicators": [], "paths_checked": ["/proc/cpuinfo"]}
}

VALID_CLOCK_DRIFT = {
    "passed": True,
    "data": {"cv": 0.05, "samples": 50}
}


def test_compute_hardware_id_uniqueness():
    """Verify that different inputs produce different hardware IDs."""
    device1 = {"device_model": "G4", "device_arch": "ppc", "device_family": "7447", "cores": 1, "cpu_serial": "123"}
    device2 = {"device_model": "G4", "device_arch": "ppc", "device_family": "7447", "cores": 1, "cpu_serial": "456"}

    id1 = _compute_hardware_id(device1, source_ip="1.1.1.1")
    id2 = _compute_hardware_id(device2, source_ip="1.1.1.1")

    assert id1 != id2
    assert len(id1) == 32

def test_compute_hardware_id_consistency():
    """Verify that same inputs produce the same hardware ID."""
    device = {"device_model": "G5", "device_arch": "ppc64", "device_family": "970", "cores": 2, "cpu_serial": "ABC"}
    signals = {"macs": ["00:11:22:33:44:55"]}

    id1 = _compute_hardware_id(device, signals, source_ip="2.2.2.2")
    id2 = _compute_hardware_id(device, signals, source_ip="2.2.2.2")

    assert id1 == id2

def test_validate_fingerprint_data_no_data():
    """Missing fingerprint payload must fail validation."""
    passed, reason = validate_fingerprint_data(None)
    assert passed is False
    assert reason == "no_fingerprint_data"

def test_validate_fingerprint_data_vm_detection():
    """Verify detection of VM indicators."""
    fingerprint = {
        "checks": {
            "anti_emulation": {
                "passed": False,
                "data": {"vm_indicators": ["vboxguest"]}
            },
            "clock_drift": VALID_CLOCK_DRIFT,
        }
    }
    passed, reason = validate_fingerprint_data(fingerprint)
    assert passed is False
    assert "vm_detected" in reason

def test_validate_fingerprint_data_no_evidence():
    """Verify rejection if no raw evidence is provided despite claim of pass."""
    fingerprint = {
        "checks": {
            "anti_emulation": {
                "passed": True,
                "data": {"irrelevant_field": True}  # No vm_indicators/dmesg_scanned/paths_checked
            },
            "clock_drift": VALID_CLOCK_DRIFT,
        }
    }
    passed, reason = validate_fingerprint_data(fingerprint)
    assert passed is False
    assert reason == "anti_emulation_no_evidence"

def test_validate_fingerprint_data_clock_drift_threshold():
    """Verify rejection of too uniform timing (clock drift check)."""
    fingerprint = {
        "checks": {
            "anti_emulation": VALID_ANTI_EMULATION,
            "clock_drift": {
                "passed": True,
                "data": {"cv": 0.000001, "samples": 100}  # Too stable
            }
        }
    }
    passed, reason = validate_fingerprint_data(fingerprint)
    assert passed is False
    assert reason == "timing_too_uniform"

def test_validate_fingerprint_data_clock_drift_no_evidence():
    """Clock drift with zero samples and zero cv is rejected as no evidence."""
    fingerprint = {
        "checks": {
            "anti_emulation": VALID_ANTI_EMULATION,
            "clock_drift": {
                "passed": True,
                "data": {"cv": 0, "samples": 0}
            }
        }
    }
    passed, reason = validate_fingerprint_data(fingerprint)
    assert passed is False
    assert reason == "clock_drift_no_evidence"

def test_validate_fingerprint_data_vintage_stability():
    """Verify rejection of suspicious stability on vintage hardware."""
    claimed_device = {"device_arch": "G4"}
    fingerprint = {
        "checks": {
            "anti_emulation": VALID_ANTI_EMULATION,
            "clock_drift": {
                "passed": True,
                "data": {"cv": 0.001, "samples": 100}  # Too stable for G4
            }
        }
    }
    passed, reason = validate_fingerprint_data(fingerprint, claimed_device)
    assert passed is False
    assert "vintage_timing_too_stable" in reason
