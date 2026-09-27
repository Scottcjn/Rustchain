"""Regression tests for server-side vouching of claimed reward tiers.

Encodes the defect found 2026-07-31: derive_verified_device() ended by
returning the miner's own device_family/device_arch verbatim for any family it
did not specifically handle, and there was no allowlist of arch values
anywhere. Both reward tables key off what it returns, so a plain bare-metal
x86 box that put two extra strings in its attestation payload collected a
vintage tier for free:

    {"family": "ARM",     "arch": "arm2"}      -> 4.0x
    {"family": "console", "arch": "nes_6502"}  -> 2.8x

against an honest modern x86_64 at 0.8x. The epoch pot is fixed at 1.5 RTC and
split by weight, so every fraudulent multiplier came straight out of the
honest miners' share.

The second half of the same defect: the console clock_drift relaxation in
validate_fingerprint_data() keyed off the *claimed* arch string, so the same
payload with no clock_drift measurement at all was rejected as "modern" and
accepted as "nes_6502".

The hard constraint on any fix here is that the fleet contains hardware which
genuinely cannot produce the usual evidence. An unvouchable claim must be
capped at the modern rate, never zeroed. Losing the bonus is correct; losing
the ability to mine is not.
"""

import importlib.util
import os
import sys
import tempfile

import pytest

NODE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "node")
NODE_FILE = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")


@pytest.fixture(scope="module")
def node():
    os.environ.setdefault("RC_ADMIN_KEY", "0" * 32)
    os.environ.setdefault("RC_P2P_SECRET", "c" * 40)
    _db_fd, _db_path = tempfile.mkstemp(suffix=".db")
    os.close(_db_fd)
    os.environ.setdefault("DB_PATH", _db_path)
    if NODE_DIR not in sys.path:
        sys.path.insert(0, NODE_DIR)
    spec = importlib.util.spec_from_file_location("rcnode_vouch", NODE_FILE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["rcnode_vouch"] = mod
    spec.loader.exec_module(mod)
    return mod


def weight_of(node, verified):
    """Enrolment-path weight, mirroring the lookup in enroll_epoch()."""
    bucket = node.HARDWARE_WEIGHTS.get(verified["device_family"], {})
    return bucket.get(verified["device_arch"], bucket.get("default", 1.0))


def antiquity_of(arch):
    """Settlement-path multiplier, mirroring calculate_epoch_rewards_time_aged()."""
    from rip_200_round_robin_1cpu1vote import get_time_aged_multiplier
    return get_time_aged_multiplier(arch, 0.0)


MODERN_FP = {
    "all_passed": True,
    "checks": {
        "anti_emulation": {"passed": True, "data": {"vm_indicators": []}},
        "clock_drift": {"passed": True, "data": {"cv": 0.09, "samples": 500}},
        "simd_identity": {"passed": True, "data": {"has_sse": True, "has_sse2": True, "has_avx": True}},
    },
}

# A real Pico bridge attestation (RIP-304). miners/pico_bridge/pico_bridge_miner.py
# stamps bridge_type on both the device and the fingerprint and always emits
# ctrl_port_timing.
PICO_FP = {
    "bridge_type": "pico_serial",
    "all_passed": True,
    "checks": {
        "ctrl_port_timing": {"passed": True, "data": {"cv": 0.005, "samples": 500}},
        "rom_execution_timing": {"passed": True, "data": {"hash_time_us": 847000}},
        "bus_jitter": {"passed": True, "data": {"jitter_stdev_ns": 1250}},
        "anti_emulation": {"passed": True, "data": {"vm_indicators": []}},
    },
}

# A genuine 486: no SIMD, and clock_drift FAILS because there is no usable TSC.
FP_486 = {
    "all_passed": False,
    "checks": {
        "anti_emulation": {"passed": True, "data": {"vm_indicators": []}},
        "cache_timing": {"passed": True, "data": {"latencies": {"4KB": {"random_ns": 180.0}}}},
        "simd_identity": {"passed": True, "data": {"has_sse": False}},
    },
}

MODERN_X86_BOX = {"cpu": "Intel(R) Core(TM) i9-13900K", "machine": "x86_64"}


# --- the hole itself -------------------------------------------------------

@pytest.mark.parametrize("family,arch", [
    ("ARM", "arm2"),
    ("ARM", "arm3"),
    ("ARM", "strongarm"),
    ("console", "nes_6502"),
    ("console", "ps1_mips"),
    ("console", "snes_65c816"),
])
def test_claimed_vintage_tier_on_a_modern_box_is_capped(node, family, arch):
    """A bare-metal x86 box cannot type its way into a vintage tier."""
    device = dict(MODERN_X86_BOX, family=family, arch=arch)
    verified = node.derive_verified_device(device, MODERN_FP, True)

    assert weight_of(node, verified) <= 0.8, (
        f"{family}/{arch} still pays {weight_of(node, verified)} on the enrolment path"
    )
    assert antiquity_of(verified["device_arch"]) <= 0.8, (
        f"{family}/{arch} still pays {antiquity_of(verified['device_arch'])} at settlement"
    )


def test_capped_claim_is_not_zeroed(node):
    """Losing the bonus is correct. Losing the ability to earn is not."""
    device = dict(MODERN_X86_BOX, family="console", arch="nes_6502")
    verified = node.derive_verified_device(device, MODERN_FP, True)

    assert weight_of(node, verified) > 0, "an unvouched miner must still earn"
    assert weight_of(node, verified) == 0.8, "cap is the modern rate, not a penalty"


def test_console_arch_no_longer_skips_clock_drift(node):
    """The relaxation must not be reachable by typing a console arch string."""
    no_clock = {"all_passed": True, "checks": {
        "anti_emulation": {"passed": True, "data": {"vm_indicators": []}},
    }}

    ok_modern, reason_modern = node.validate_fingerprint_data(
        no_clock, claimed_device={"family": "x86_64", "arch": "modern"},
    )
    ok_console, reason_console = node.validate_fingerprint_data(
        no_clock, claimed_device={"family": "console", "arch": "nes_6502"},
    )

    assert ok_modern is False and reason_modern == "missing_required_check:clock_drift"
    assert ok_console is False, "claiming a console arch skipped a required check"
    assert reason_console == reason_modern, "same payload, same verdict"


# --- honest hardware must not regress --------------------------------------

def test_honest_console_via_pico_bridge_keeps_its_tier(node):
    device = {"family": "console", "arch": "nes_6502", "model": "NES",
              "cpu": "Ricoh 2A03", "bridge_type": "pico_serial"}
    verified = node.derive_verified_device(device, PICO_FP, True)

    assert verified == {"device_family": "console", "device_arch": "nes_6502"}
    assert weight_of(node, verified) == 2.8


def test_honest_apple_ii_reports_a_bare_cpu_and_keeps_its_tier(node):
    """An Apple II reports "6502", not a console model name.

    HARDWARE_WEIGHTS["console"] has no "6502" key, so it lands on the console
    default tier. Any vouching check built from the weight-table keys alone
    would cap this machine, which is worse than the bug it fixes.
    """
    device = {"family": "console", "arch": "6502", "model": "Apple II",
              "cpu": "MOS 6502", "bridge_type": "pico_serial"}
    verified = node.derive_verified_device(device, PICO_FP, True)

    assert verified == {"device_family": "console", "device_arch": "6502"}
    assert weight_of(node, verified) == 2.5
    assert antiquity_of("6502") > 0.8


def test_honest_tscless_486_is_untouched(node):
    """A real 486 legitimately fails clock_drift. It keeps its tier.

    x86 is deliberately left on its existing path here (_detect_x86_vintage
    plus the _derive_enroll_weight_device clamp from #8022) so this change
    stays complementary to PR #8087 rather than colliding with it.
    """
    device = {"family": "x86", "arch": "486", "cpu": "Intel 486DX2-66", "machine": "i486"}
    verified = node.derive_verified_device(device, FP_486, False)

    assert verified == {"device_family": "x86", "device_arch": "486"}
    assert weight_of(node, verified) == 2.0


def test_honest_vintage_arm_with_arm_evidence_keeps_its_tier(node):
    """Real vintage ARM resolves in the ARM-evidence branch, not at the tail."""
    device = {"family": "ARM", "arch": "strongarm",
              "cpu": "DEC StrongARM SA-110", "machine": "arm"}
    verified = node.derive_verified_device(device, MODERN_FP, True)

    assert verified == {"device_family": "ARM", "device_arch": "strongarm"}
    assert weight_of(node, verified) == 2.8


def test_honest_g4_and_apple_silicon_unaffected(node):
    g4 = node.derive_verified_device(
        {"family": "PowerPC", "arch": "g4", "cpu": "PowerPC 7455 AltiVec", "machine": "ppc"},
        MODERN_FP, True)
    assert g4 == {"device_family": "PowerPC", "device_arch": "G4"}

    m2 = node.derive_verified_device(
        {"family": "ARM", "arch": "m2", "cpu": "Apple M2", "machine": "arm64",
         "platform_system": "Darwin"}, MODERN_FP, True)
    assert m2["device_family"] == "Apple Silicon"


def test_honest_modern_x86_unchanged(node):
    device = dict(MODERN_X86_BOX, family="x86_64", arch="modern")
    verified = node.derive_verified_device(device, MODERN_FP, True)

    assert verified == {"device_family": "x86_64", "device_arch": "modern"}
    assert weight_of(node, verified) == 0.8


def test_missing_device_object_does_not_crash(node):
    """An i386 client may send no device object at all."""
    verified = node.derive_verified_device({}, FP_486, False)

    assert isinstance(verified, dict)
    assert "device_family" in verified and "device_arch" in verified


# --- the vouching helper itself --------------------------------------------

def test_claim_pays_above_neutral_consults_both_reward_tables(node):
    """x86 486 is 2.0 in HARDWARE_WEIGHTS and 2.9 in ANTIQUITY_MULTIPLIERS.

    Consulting only one table would miss half the money, so the helper has to
    read both.
    """
    assert node._claim_pays_above_neutral("ARM", "arm2") is True
    assert node._claim_pays_above_neutral("console", "nes_6502") is True
    assert node._claim_pays_above_neutral("x86_64", "modern") is False


def test_console_bridge_evidence_requires_the_pico_shape(node):
    assert node._console_bridge_evidence({"bridge_type": "pico_serial"}, {}) is True
    assert node._console_bridge_evidence({}, PICO_FP) is True
    assert node._console_bridge_evidence({}, MODERN_FP) is False
    assert node._console_bridge_evidence({}, {}) is False
