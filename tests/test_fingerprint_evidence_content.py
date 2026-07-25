# SPDX-License-Identifier: MIT
"""Fix A: validate_fingerprint_data must inspect evidence CONTENT, not just presence.

Before this fix, the 2026-02-02 hardening only verified that evidence fields
EXISTED. A payload like

    {"passed": true, "data": {"vm_indicators": ["qemu", "hypervisor"]}}

was accepted: has_evidence was satisfied because vm_indicators was present,
and the verdict was not literally False. The server held the string "qemu"
and never looked at it.

Also covers the "== False" -> "is not True" verdict hardening: omitting the
"passed" key entirely used to skip both the pass branch and the fail branch.
Bool-format (C miner) checks must keep working.
"""
import sys

integrated_node = sys.modules["integrated_node"]
validate_fingerprint_data = integrated_node.validate_fingerprint_data

MODERN_DEVICE = {"device_arch": "modern", "device_family": "x86_64"}


def clean_fingerprint():
    """A payload shaped like the real fingerprint_checks.py output on honest
    real hardware: vm_indicators is an EMPTY list, cv/samples are real."""
    return {
        "all_passed": True,
        "checks": {
            "anti_emulation": {
                "passed": True,
                "data": {"vm_indicators": [], "indicator_count": 0, "is_likely_vm": False},
            },
            "clock_drift": {"passed": True, "data": {"cv": 0.09, "samples": 200}},
            "cache_timing": {"passed": True, "data": {"levels_detected": 3}},
            "simd_identity": {"passed": True, "data": {"features": ["sse2", "avx2"]}},
            "thermal_drift": {"passed": True, "data": {"variance": 0.4}},
            "instruction_jitter": {"passed": True, "data": {"stdev_ns": 140.0}},
        },
    }


# ── The headline case: QEMU self-report with a forged pass verdict ──

def test_qemu_self_report_with_forged_pass_is_rejected():
    fp = clean_fingerprint()
    fp["checks"]["anti_emulation"] = {
        "passed": True,
        "data": {"vm_indicators": ["qemu", "hypervisor"]},
    }
    passed, reason = validate_fingerprint_data(fp, MODERN_DEVICE)
    assert passed is False
    assert reason.startswith("vm_self_reported:")
    assert "qemu" in reason


def test_is_likely_vm_with_forged_pass_is_rejected():
    fp = clean_fingerprint()
    fp["checks"]["anti_emulation"] = {
        "passed": True,
        "data": {"vm_indicators": [], "is_likely_vm": True},
    }
    passed, reason = validate_fingerprint_data(fp, MODERN_DEVICE)
    assert passed is False
    assert reason == "vm_self_reported:is_likely_vm"


def test_clean_payload_still_passes():
    passed, reason = validate_fingerprint_data(clean_fingerprint(), MODERN_DEVICE)
    assert passed is True
    assert reason == "valid"


def test_honest_vm_failure_keeps_vm_detected_reason():
    fp = clean_fingerprint()
    fp["all_passed"] = False
    fp["checks"]["anti_emulation"] = {
        "passed": False,
        "data": {"vm_indicators": ["cpuinfo:hypervisor"], "fail_reason": "vm_detected"},
    }
    passed, reason = validate_fingerprint_data(fp, MODERN_DEVICE)
    assert passed is False
    assert reason.startswith("vm_detected:")


# ── "is not True" verdict hardening (missing "passed" no longer sails through) ──

def test_anti_emulation_missing_verdict_rejected():
    fp = clean_fingerprint()
    fp["checks"]["anti_emulation"] = {
        "data": {"vm_indicators": [], "paths_checked": ["/proc/cpuinfo"]},
    }
    passed, reason = validate_fingerprint_data(fp, MODERN_DEVICE)
    assert passed is False
    assert reason == "anti_emulation_no_verdict"


def test_clock_drift_missing_verdict_rejected():
    fp = clean_fingerprint()
    fp["checks"]["clock_drift"] = {"data": {"cv": 0.09, "samples": 200}}
    passed, reason = validate_fingerprint_data(fp, MODERN_DEVICE)
    assert passed is False
    assert reason == "clock_drift_no_verdict"


def test_rom_null_verdict_rejected():
    fp = clean_fingerprint()
    fp["checks"]["rom_fingerprint"] = {
        "passed": None,
        "data": {"rom_hashes": {"boot": "abc"}},
    }
    passed, reason = validate_fingerprint_data(fp, MODERN_DEVICE)
    assert passed is False
    assert reason == "rom_check_no_verdict"


# ── C-format bool checks (Apple II / i386 miners) must keep working ──

def test_bool_format_checks_still_accepted():
    fp = {"checks": {"anti_emulation": True, "clock_drift": True}}
    passed, reason = validate_fingerprint_data(fp, MODERN_DEVICE)
    assert passed is True


def test_bool_format_anti_emulation_false_still_rejected():
    fp = {"checks": {"anti_emulation": False, "clock_drift": True}}
    passed, reason = validate_fingerprint_data(fp, MODERN_DEVICE)
    assert passed is False
    assert reason == "anti_emulation_failed_bool"


def test_bool_format_clock_drift_false_still_rejected():
    fp = {"checks": {"anti_emulation": True, "clock_drift": False}}
    passed, reason = validate_fingerprint_data(fp, MODERN_DEVICE)
    assert passed is False
    assert reason == "clock_drift_failed_bool"


# ── Same content pattern in the other checks ──

def test_fail_reason_contradiction_rejected():
    """A check that claims pass while its own data records a fail_reason."""
    fp = clean_fingerprint()
    fp["checks"]["thermal_drift"] = {
        "passed": True,
        "data": {"variance": 0.0, "fail_reason": "no_thermal_variance"},
    }
    passed, reason = validate_fingerprint_data(fp, MODERN_DEVICE)
    assert passed is False
    assert reason.startswith("check_self_reported_failure:thermal_drift:")


def test_fail_reasons_list_contradiction_rejected():
    fp = clean_fingerprint()
    fp["checks"]["instruction_jitter"] = {
        "passed": True,
        "data": {"stdev_ns": 0, "fail_reasons": ["no_jitter"]},
    }
    passed, reason = validate_fingerprint_data(fp, MODERN_DEVICE)
    assert passed is False
    assert reason.startswith("check_self_reported_failure:instruction_jitter:")


def test_rom_emulator_detected_with_forged_pass_rejected():
    fp = clean_fingerprint()
    fp["checks"]["rom_fingerprint"] = {
        "passed": True,
        "data": {"emulator_detected": True, "detection_details": [{"platform": "mac_ppc"}]},
    }
    passed, reason = validate_fingerprint_data(fp, MODERN_DEVICE)
    assert passed is False
    assert reason.startswith("known_emulator_rom:")


def test_rom_detection_details_with_forged_flag_rejected():
    fp = clean_fingerprint()
    fp["checks"]["rom_fingerprint"] = {
        "passed": True,
        "data": {"emulator_detected": False, "detection_details": [{"platform": "amiga"}]},
    }
    passed, reason = validate_fingerprint_data(fp, MODERN_DEVICE)
    assert passed is False
    assert reason.startswith("known_emulator_rom:")


def test_rom_clean_data_still_passes():
    fp = clean_fingerprint()
    fp["checks"]["rom_fingerprint"] = {
        "passed": True,
        "data": {"emulator_detected": False, "detection_details": [], "rom_hashes": {}},
    }
    passed, reason = validate_fingerprint_data(fp, MODERN_DEVICE)
    assert passed is True


# ── Phase 4: embedded hard failures no longer hide behind all_passed ──

def test_hard_failure_with_all_passed_true_rejected():
    fp = clean_fingerprint()
    fp["all_passed"] = True  # forged overall verdict
    fp["checks"]["thermal_drift"] = {"passed": False, "data": {"fail_reason": "no_thermal_variance"}}
    passed, reason = validate_fingerprint_data(fp, MODERN_DEVICE)
    assert passed is False
    assert reason.startswith("checks_failed:")
    assert "thermal_drift" in reason


def test_hard_failure_with_all_passed_omitted_rejected():
    fp = clean_fingerprint()
    del fp["all_passed"]
    fp["checks"]["instruction_jitter"] = {"passed": False, "data": {"fail_reason": "no_jitter"}}
    passed, reason = validate_fingerprint_data(fp, MODERN_DEVICE)
    assert passed is False
    assert reason.startswith("checks_failed:")


def test_soft_cache_timing_failure_still_accepted():
    fp = clean_fingerprint()
    fp["all_passed"] = False
    fp["checks"]["cache_timing"] = {"passed": False, "data": {"fail_reason": "no_cache_hierarchy"}}
    passed, reason = validate_fingerprint_data(fp, MODERN_DEVICE)
    assert passed is True
    assert reason.startswith("soft_checks_warn:")


def test_all_passed_false_with_no_failed_checks_rejected():
    fp = clean_fingerprint()
    fp["all_passed"] = False  # says something failed, shows nothing failed
    passed, reason = validate_fingerprint_data(fp, MODERN_DEVICE)
    assert passed is False
    assert reason == "all_passed_false_unattributed"
