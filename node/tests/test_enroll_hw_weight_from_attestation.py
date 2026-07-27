"""Regression tests for the /epoch/enroll reward-weight source.

Encodes the defect found 2026-07-25: enroll_epoch computed reward weight from
device.family / device.arch in the raw request body, so any caller could
self-grant a multiplier. HARDWARE_WEIGHTS["ARM"]["arm2"] is 4.0 against an
honest modern x86_64 at 0.8, and because epoch_enroll is INSERT OR IGNORE the
forged row also won against the honest auto-enroll that followed.
"""
import re
import sqlite3
import sys
from pathlib import Path

import pytest

NODE = Path(__file__).resolve().parents[1] / "rustchain_v2_integrated_v2.2.1_rip200.py"
SRC = NODE.read_text()


def _load():
    """Load HARDWARE_WEIGHTS and the resolver without importing the 11k-line app."""
    ns = {"sqlite3": sqlite3}
    from contextlib import closing
    ns["closing"] = closing
    hw = re.search(r"^HARDWARE_WEIGHTS = \{.*?^\}", SRC, re.S | re.M)
    assert hw, "HARDWARE_WEIGHTS block not found"
    exec(hw.group(0), ns)
    fn = re.search(r"^def resolve_enroll_hw_weight\(.*?(?=^\S)", SRC, re.S | re.M)
    assert fn, "resolve_enroll_hw_weight not found"
    exec(fn.group(0), ns)
    return ns


NS = _load()
resolve = NS["resolve_enroll_hw_weight"]
HW = NS["HARDWARE_WEIGHTS"]


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "t.db"
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE miner_attest_recent (miner TEXT PRIMARY KEY, device_family TEXT, device_arch TEXT)")
    c.commit(); c.close()
    return str(p)


def _attest(db, miner, family, arch):
    c = sqlite3.connect(db)
    c.execute("INSERT OR REPLACE INTO miner_attest_recent VALUES (?,?,?)", (miner, family, arch))
    c.commit(); c.close()


def test_arm2_selfgrant_is_ignored(db):
    """The exploit: attest as modern, then enroll claiming ARM/arm2 for 4.0."""
    _attest(db, "attacker", "x86_64", "modern")
    weight, family, arch, src = resolve(db, "attacker")
    assert weight == HW["x86_64"]["modern"] == 0.8
    assert (family, arch) == ("x86_64", "modern")
    assert src == "attested"
    assert weight < HW["ARM"]["arm2"], "must not reach the self-claimed ARM tier"


def test_body_cannot_reach_any_vintage_tier(db):
    """No body-supplied arch can raise a modern miner above its attested tier."""
    _attest(db, "m", "x86_64", "modern")
    for family, arch in (("PowerPC", "G4"), ("ARM", "arm2"), ("x86", "386"), ("x86", "pentium_mmx")):
        assert HW[family][arch] > 0.8, "test would be vacuous"
    assert resolve(db, "m")[0] == 0.8


def test_honest_vintage_keeps_its_multiplier(db):
    """The fleet this chain exists for must be untouched."""
    for miner, family, arch, expected in (
        ("g4", "PowerPC", "G4", HW["PowerPC"]["G4"]),
        ("g5", "PowerPC", "G5", HW["PowerPC"]["G5"]),
        ("t40", "x86", "pentium_m_banias", HW["x86"]["pentium_m_banias"]),
        ("qube", "x86", "retro", HW["x86"]["retro"]),
    ):
        _attest(db, miner, family, arch)
        assert resolve(db, miner)[0] == expected, f"{miner} lost its tier"


def test_macos_x86_64_vintage_arch_uses_x86_bucket(db):
    """The macOS miner reports family x86_64 with vintage archs like core2.

    x86_64 carries only modern/default, so a naive nested default would pay a
    Core 2 Mac 0.8 instead of the intended 1.3. This is the under-pay failure
    mode that a careless tightening would introduce.
    """
    _attest(db, "mac", "x86_64", "core2")
    weight, _, _, _ = resolve(db, "mac")
    assert weight == HW["x86"]["core2"] == 1.3
    assert weight != HW["x86_64"]["default"]


def test_missing_attestation_is_neutral_not_a_bonus(db):
    """No attestation row must not grant a vintage tier."""
    weight, family, arch, src = resolve(db, "ghost")
    assert src == "no_attestation"
    assert weight <= 1.0
    assert weight < HW["PowerPC"]["G4"]


def test_miner_id_fallback_resolves(db):
    """Enrolment may present miner_id when miner_pk has no attestation row."""
    _attest(db, "named-g5", "PowerPC", "G5")
    assert resolve(db, "unknown-pk", "named-g5")[0] == HW["PowerPC"]["G5"]


def test_unreadable_db_fails_soft_without_bonus(tmp_path):
    """A broken database must neither grant a tier nor deny enrolment."""
    weight, _, _, _ = resolve(str(tmp_path / "missing.db"), "m")
    assert weight <= 1.0
