"""RIP-309b: capability-aware three-state fingerprint evaluation.

Checks are passed / failed / unmeasured. 'unmeasured' means the SERVER-derived
device class structurally cannot perform that measurement (a 6502 has no SIMD
unit, a 386/486 has no TSC, a Pico console bridge cannot run cache-timing
sweeps). unmeasured is NEUTRAL: excluded from the active_ratio denominator,
no credit and no penalty.

Both binary alternatives are wrong:
- absent == passed reopens the fail-open spoofing hole;
- absent == failed zeroes the honest Apple II / i386 / console / 486 fleet.

These tests prove both directions:
1. Apple II 6502, flat i386, Pico-bridge console and an honest 486 all
   validate and earn a fair non-zero weight.
2. A modern x86 box gains nothing by claiming to be capability-limited:
   the contradiction veto strips the profile and the derived class is
   downgraded, so its weight never beats its honest classification.

Run: python3 -m pytest tests/test_capability_aware_fingerprint.py -v
"""
import sqlite3

import pytest

# Pre-loaded by tests/conftest.py via importlib (module file name has dots).
integrated_node = pytest.importorskip("integrated_node")

validate_fingerprint_data = integrated_node.validate_fingerprint_data
derive_verified_device = integrated_node.derive_verified_device
evaluate_rotating_fingerprint_checks = integrated_node.evaluate_rotating_fingerprint_checks
_fingerprint_check_state = integrated_node._fingerprint_check_state
_structurally_unmeasurable_checks = integrated_node._structurally_unmeasurable_checks
_capability_contradiction = integrated_node._capability_contradiction
_flat_micro_fingerprint = integrated_node._flat_micro_fingerprint
HARDWARE_WEIGHTS = integrated_node.HARDWARE_WEIGHTS
epoch_weight_to_units = integrated_node.epoch_weight_to_units
ROTATING = integrated_node.RIP309_ROTATING_FINGERPRINT_CHECKS


@pytest.fixture
def conn():
    # No blocks table -> previous-epoch hash falls back to all-zeros ->
    # rotation fails closed and activates ALL SIX checks. Deterministic.
    c = sqlite3.connect(":memory:")
    yield c
    c.close()


def _hw_weight(verified):
    fam = verified["device_family"]
    arch = verified["device_arch"]
    fam_map = HARDWARE_WEIGHTS.get(fam, {})
    return fam_map.get(arch, fam_map.get("default", 1.0))


def _enroll_weight_units(conn, fingerprint, claimed_device):
    """Replicates the auto-enroll weight path for a fingerprint-passing miner."""
    verified = derive_verified_device(claimed_device, fingerprint, True)
    rotation = evaluate_rotating_fingerprint_checks(
        conn, 424, fingerprint, verified_device=verified, claimed_device=claimed_device
    )
    return epoch_weight_to_units(_hw_weight(verified) * rotation["active_ratio"]), verified, rotation


# ── Honest hardware payloads (mirroring the real miner clients) ──────────

# miners/apple2/miner6502.c build_payload(): fingerprint has NO checks map,
# simd_identity is a bare hex STRING, evidence is flat device-native fields.
APPLE2_DEVICE = {"arch": "6502", "cores": 1, "model": "MOS6502", "clock_mhz": 1}
APPLE2_FP = {
    "cycle_count": 10234,
    "ram_kb": 128,
    "aux_ram": True,
    "simd_identity": "a1b2c3d4e5f60718",
}

# miners/i386/miner386.c build_payload(): FLAT top-level payload, no device
# object, no fingerprint object at all.
I386_FLAT_DATA = {
    "miner_id": "my386",
    "arch": "i386",
    "cpu_vendor": "i386-NoCPUID",
    "has_cpuid": 0,
    "cpuid_max_leaf": 0,
    "cpu_flags": 578,
    "ram_kb": 4096,
    "clock_ticks": 183456,
    "hw_fingerprint": "ab" * 32,
    "timestamp": 1234567890,
}

# miners/pico_bridge/pico_bridge_miner.py build_attestation_payload(): only
# ONE of the six rotating names (anti_emulation) is present.
CONSOLE_DEVICE = {
    "family": "console", "arch": "n64_mips", "model": "Nintendo 64",
    "cpu": "NEC VR4300 @ 93.75MHz", "cores": 1, "memory_mb": 4,
    "bridge_type": "pico_serial", "bridge_firmware": "1.0.0",
}
CONSOLE_FP = {
    "all_passed": True,
    "bridge_type": "pico_serial",
    "checks": {
        "ctrl_port_timing": {"passed": True, "data": {"cv": 0.00035, "samples": 500}},
        "rom_execution_timing": {"passed": True, "data": {"hash_time_us": 45000}},
        "bus_jitter": {"passed": True, "data": {"jitter_stdev_ns": 800}},
        "anti_emulation": {"passed": True, "data": {"emulator_indicators": []}},
    },
}

# Honest 486: reports clock_drift FAILED because it has no usable TSC.
DEV_486 = {"arch": "486", "cpu": "GenuineIntel", "machine": "i486", "cores": 1}
FP_486 = {
    "all_passed": False,
    "checks": {
        "clock_drift": {"passed": False,
                        "data": {"fail_reason": "no_tsc", "cv": 0, "samples": 0}},
        "anti_emulation": {"passed": True, "data": {"vm_indicators": []}},
    },
}


# ── Direction 1: iconic vintage miners validate and earn non-zero weight ──

def test_apple2_validates_on_native_evidence():
    ok, reason = validate_fingerprint_data(APPLE2_FP, claimed_device=APPLE2_DEVICE)
    assert ok, reason
    assert reason.startswith("micro_native_evidence")


def test_apple2_not_misclassified_as_arm_and_weighted(conn):
    units, verified, rotation = _enroll_weight_units(conn, APPLE2_FP, APPLE2_DEVICE)
    assert verified == {"device_family": "MOS", "device_arch": "6502"}
    assert rotation["active_ratio"] == 1.0
    assert rotation["measured_total"] == 0
    assert set(rotation["unmeasured_active_checks"]) == set(ROTATING)
    assert units > 0
    assert _hw_weight(verified) == 2.8


def test_i386_flat_payload_reconstructed_and_validates():
    device = {"arch": "i386", "cpu": "i386-NoCPUID", "cores": 1}
    fp = _flat_micro_fingerprint(I386_FLAT_DATA, device)
    assert len(fp) >= 2  # clock_ticks, ram_kb, hw_fingerprint, ...
    ok, reason = validate_fingerprint_data(fp, claimed_device=device)
    assert ok, reason


def test_i386_weight_maps_to_386_tier(conn):
    device = {"arch": "i386", "cpu": "i386-NoCPUID", "cores": 1}
    fp = _flat_micro_fingerprint(I386_FLAT_DATA, device)
    units, verified, rotation = _enroll_weight_units(conn, fp, device)
    assert verified == {"device_family": "x86", "device_arch": "386"}
    assert rotation["active_ratio"] == 1.0
    assert units > 0
    assert _hw_weight(verified) == 2.5


def test_flat_reconstruction_refused_for_non_micro_arch():
    device = {"arch": "modern", "cpu": "AMD Ryzen 9 7950X", "cores": 32}
    assert _flat_micro_fingerprint(I386_FLAT_DATA, device) == {}


def test_console_validates_and_gets_full_ratio(conn):
    ok, reason = validate_fingerprint_data(CONSOLE_FP, claimed_device=CONSOLE_DEVICE)
    assert ok, reason
    units, verified, rotation = _enroll_weight_units(conn, CONSOLE_FP, CONSOLE_DEVICE)
    assert verified == {"device_family": "console", "device_arch": "n64_mips"}
    # anti_emulation is the one measurable rotating check and it passed;
    # the other five are unmeasured (neutral), NOT failed.
    assert rotation["measured_total"] == 1
    assert rotation["passed_active_checks"] == ["anti_emulation"]
    assert set(rotation["unmeasured_active_checks"]) == set(ROTATING) - {"anti_emulation"}
    assert rotation["active_ratio"] == 1.0
    assert units > 0
    assert _hw_weight(verified) == 2.5


def test_console_anti_emulation_failure_still_fatal(conn):
    fp = {
        "all_passed": False,
        "bridge_type": "pico_serial",
        "checks": {
            "ctrl_port_timing": {"passed": True, "data": {"cv": 0.0004, "samples": 500}},
            "anti_emulation": {"passed": False,
                               "data": {"emulator_indicators": ["low_timing_cv"]}},
        },
    }
    ok, reason = validate_fingerprint_data(fp, claimed_device=CONSOLE_DEVICE)
    assert not ok
    # And in rotation terms it is a FAILURE, never neutral:
    verified = {"device_family": "console", "device_arch": "n64_mips"}
    rotation = evaluate_rotating_fingerprint_checks(
        conn, 424, fp, verified_device=verified, claimed_device=CONSOLE_DEVICE)
    assert "anti_emulation" in rotation["failed_active_checks"]
    assert rotation["active_ratio"] == 0.0


def test_honest_486_clock_drift_failure_is_neutral(conn):
    ok, reason = validate_fingerprint_data(FP_486, claimed_device=DEV_486)
    assert ok, reason
    units, verified, rotation = _enroll_weight_units(conn, FP_486, DEV_486)
    assert verified == {"device_family": "x86", "device_arch": "486"}
    assert "clock_drift" in rotation["unmeasured_active_checks"]
    assert "clock_drift" not in rotation["failed_active_checks"]
    assert rotation["measured_total"] == 1  # anti_emulation
    assert rotation["active_ratio"] == 1.0
    assert units > 0
    assert _hw_weight(verified) == 2.0


# ── Direction 2: a modern box gains nothing by claiming limitation ────────

MODERN_FULL_FP = {
    "checks": {
        "clock_drift": {"passed": True, "data": {"cv": 0.09, "samples": 1000}},
        "anti_emulation": {"passed": True, "data": {"vm_indicators": []}},
        "simd_identity": {"passed": True, "data": {"x86_features": ["sse2", "avx2"]}},
    },
}


def test_modern_box_claiming_6502_is_vetoed_and_downgraded(conn):
    spoof_device = {"arch": "6502", "model": "MOS6502", "cores": 1}
    assert _capability_contradiction(spoof_device, MODERN_FULL_FP) == "x86_simd_evidence"
    verified = derive_verified_device(spoof_device, MODERN_FULL_FP, True)
    # Downgraded: 0.8 (honest-modern tier), NOT MOS/6502's 2.8.
    assert verified == {"device_family": "x86_64", "device_arch": "default"}
    rotation = evaluate_rotating_fingerprint_checks(
        conn, 424, MODERN_FULL_FP, verified_device=verified, claimed_device=spoof_device)
    # Full-capability denominator: absent checks count as failures again.
    assert rotation["unmeasured_active_checks"] == []
    assert rotation["measured_total"] == len(rotation["active_checks"])
    assert rotation["active_ratio"] < 1.0
    spoof_weight = _hw_weight(verified) * rotation["active_ratio"]
    assert spoof_weight <= HARDWARE_WEIGHTS["x86_64"]["modern"]


def test_modern_box_claiming_6502_with_machine_field_fails_validation():
    spoof_device = {"arch": "6502", "model": "MOS6502", "machine": "x86_64"}
    ok, reason = validate_fingerprint_data(dict(APPLE2_FP), claimed_device=spoof_device)
    assert not ok
    assert reason == "empty_fingerprint_checks"
    verified = derive_verified_device(spoof_device, dict(APPLE2_FP), False)
    assert verified == {"device_family": "x86_64", "device_arch": "default"}


def test_modern_box_claiming_486_cannot_neutralize_clock_failure():
    spoof_device = {"arch": "486", "cpu": "GenuineIntel", "machine": "x86_64"}
    ok, reason = validate_fingerprint_data(dict(FP_486), claimed_device=spoof_device)
    assert not ok
    assert reason.startswith("clock_drift_failed")


def test_arm_sbc_claiming_6502_keeps_arm_penalty():
    sbc_device = {"arch": "6502", "model": "MOS6502", "machine": "aarch64"}
    verified = derive_verified_device(sbc_device, {}, False)
    assert verified["device_family"] == "ARM"
    assert _hw_weight(verified) == 0.0005


def test_modern_cpu_brand_vetoes_micro_claim():
    spoof_device = {"arch": "386", "cpu": "AMD Ryzen 7 5800X", "cores": 8}
    assert _capability_contradiction(spoof_device, {}) is not None
    verified = derive_verified_device(spoof_device, {}, False)
    assert verified == {"device_family": "x86_64", "device_arch": "default"}


def test_powerpc_simd_evidence_vetoes_micro_claim():
    fp = {"checks": {"simd_identity": {"passed": True, "data": {"altivec": True}}}}
    assert _capability_contradiction({"arch": "6502"}, fp) == "powerpc_simd_evidence"


# ── Regression guards: nothing weakened for capable hardware ─────────────

def test_legacy_callers_keep_strict_absent_equals_failed(conn):
    fp = {"checks": {"anti_emulation": {"passed": True, "data": {"vm_indicators": []}}}}
    rotation = evaluate_rotating_fingerprint_checks(conn, 424, fp)  # no device args
    assert rotation["unmeasured_active_checks"] == []
    assert rotation["measured_total"] == len(rotation["active_checks"])
    assert rotation["active_ratio"] == pytest.approx(1 / len(rotation["active_checks"]))


def test_modern_class_missing_checks_still_penalized(conn):
    verified = {"device_family": "x86_64", "device_arch": "default"}
    fp = {"checks": {"anti_emulation": {"passed": True, "data": {"vm_indicators": []}}}}
    rotation = evaluate_rotating_fingerprint_checks(
        conn, 424, fp, verified_device=verified, claimed_device={"arch": "modern"})
    assert rotation["active_ratio"] == pytest.approx(1 / len(rotation["active_checks"]))


def test_modern_empty_fingerprint_still_rejected():
    ok, reason = validate_fingerprint_data({"checks": {}}, claimed_device={"arch": "modern"})
    assert not ok
    assert reason == "empty_fingerprint_checks"


def test_vintage_powerpc_path_unchanged():
    """G4 relaxation logic untouched: anti_emulation still required."""
    ok, reason = validate_fingerprint_data(
        {"checks": {"cache_timing": {"passed": True, "data": {"x": 1}}}},
        claimed_device={"arch": "g4", "cpu": "PowerPC G4 7455"},
    )
    assert not ok
    assert reason == "missing_required_check:anti_emulation"


def test_check_state_unit_semantics():
    unmeasurable = frozenset(ROTATING)
    # Absent on a capable class: failed. Absent on an incapable class: unmeasured.
    assert _fingerprint_check_state(None, "cache_timing", frozenset()) == "failed"
    assert _fingerprint_check_state(None, "cache_timing", unmeasurable) == "unmeasured"
    # Honest incapacity failure: unmeasured -- except anti_emulation, always hard.
    failed = {"passed": False, "data": {}}
    assert _fingerprint_check_state(failed, "clock_drift", unmeasurable) == "unmeasured"
    assert _fingerprint_check_state(failed, "anti_emulation", unmeasurable) == "failed"
    # A reported pass is a pass either way.
    assert _fingerprint_check_state({"passed": True, "data": {}}, "clock_drift", unmeasurable) == "passed"
    # Bool (C-miner) format.
    assert _fingerprint_check_state(True, "clock_drift", frozenset()) == "passed"
    assert _fingerprint_check_state(False, "clock_drift", frozenset()) == "failed"
    assert _fingerprint_check_state(False, "clock_drift", unmeasurable) == "unmeasured"


def test_unmeasurable_sets_by_class():
    all_six = frozenset(ROTATING)
    assert _structurally_unmeasurable_checks("6502") == all_six
    assert _structurally_unmeasurable_checks("486") == all_six
    assert _structurally_unmeasurable_checks("n64_mips") == all_six - {"anti_emulation"}
    # Bare micro arch attested through a Pico bridge gets the console profile.
    assert _structurally_unmeasurable_checks(
        "6502", {"bridge_type": "pico_serial"}) == all_six - {"anti_emulation"}
    # Full-capability classes get no neutral checks at all.
    assert _structurally_unmeasurable_checks("modern") == frozenset()
    assert _structurally_unmeasurable_checks("G4") == frozenset()
    assert _structurally_unmeasurable_checks("aarch64") == frozenset()
