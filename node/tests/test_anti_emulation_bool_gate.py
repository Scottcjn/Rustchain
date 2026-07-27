"""The bare-boolean anti_emulation bypass, and the fleet it must not break.

A Proxmox VM attested on production with fingerprint_passed=1 and earned 0.8x
by submitting {"anti_emulation": true, ...} with no evidence object. The bool
branch only rejected an explicit False, so `true` fell through.

anti_emulation is the VM gate, not a measurement channel. Capable hardware must
affirmatively pass it with evidence. The bare-boolean form exists only for the
C miners that cannot serialise a nested object.
"""
import re
import pytest

SRC = open("node/rustchain_v2_integrated_v2.2.1_rip200.py").read()
SEG_START = SRC.index("elif isinstance(anti_emu_check, bool):")
SEG = SRC[SEG_START:SEG_START + 2000]


def test_capable_device_rejects_bare_true():
    """The exact production exploit payload must no longer pass."""
    assert "anti_emulation_bool_not_accepted_for_capable_device" in SEG


def test_explicit_false_still_rejected():
    assert "anti_emulation_failed_bool" in SEG


@pytest.mark.parametrize("token", ["6502", "z80", "386", "486", "console", "retro"])
def test_constrained_classes_still_allowed(token):
    """Apple II, i386 and the console bridges cannot send a nested object."""
    assert token in SEG, f"{token} must stay on the bare-boolean allowlist"


def test_allowlist_is_class_based_not_key_based():
    """Capability must come from the server-derived class.

    'No data' cannot distinguish 'this hardware cannot measure it' from 'this
    client did not bother'. Only the device class can.
    """
    assert "device_family" in SEG and "device_arch" in SEG
