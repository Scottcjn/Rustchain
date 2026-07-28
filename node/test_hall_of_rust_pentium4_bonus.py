# SPDX-License-Identifier: MIT
"""
POC / regression test for the Hall of Rust Pentium 4 architecture-bonus bug.

arch_bonus lists both 'pentium' (100) and 'pentium4' (50). The match loop does a
substring test (``key in arch``) and stops at the first hit. Because 'pentium'
is a substring of 'pentium4' and appeared first in dict-iteration order, a
Pentium 4 machine matched 'pentium' and received 100 instead of its intended 50
-- the 'pentium4' entry was unreachable dead code, and every Pentium 4 sat 50
points too high on the ``ORDER BY rust_score DESC`` leaderboard.

Fix: match the longest (most specific) key first.

Run:
    python3 -m pytest node/test_hall_of_rust_pentium4_bonus.py -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from hall_of_rust import calculate_rust_score


def _isolated(arch):
    # Only the arch bonus contributes: no mfg year, no attestations, no plague
    # model, no thermal events, id default 999 (> 100 => no first-adopter bonus).
    return calculate_rust_score({"device_arch": arch}, current_year=2026)


def test_pentium4_gets_its_own_lower_bonus():
    # FAILS on main: 'pentium' matches first and returns 100.0.
    assert _isolated("pentium4") == 50.0


def test_pentium4_variants_still_specific():
    # Reported strings that embed 'pentium 4' / 'Pentium4' must resolve to 50.
    assert _isolated("Pentium4 Northwood") == 50.0
    assert _isolated("intel pentium4") == 50.0


def test_plain_pentium_unchanged():
    assert _isolated("pentium") == 100.0
    assert _isolated("Pentium III") == 100.0


def test_powerpc_bonus_unaffected():
    # The longest-first ordering must not regress the PowerPC fix (#7956).
    assert _isolated("g4") == 70.0
    assert _isolated("486") == 150.0


if __name__ == "__main__":
    cases = [("pentium4", 50.0), ("Pentium4 Northwood", 50.0),
             ("pentium", 100.0), ("g4", 70.0), ("486", 150.0)]
    for arch, expected in cases:
        got = _isolated(arch)
        print(f"arch={arch!r:>20}  expected={expected:>6}  got={got:>6}  "
              f"{'OK' if got == expected else 'FAIL'}")
