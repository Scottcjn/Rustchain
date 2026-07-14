# SPDX-License-Identifier: MIT
"""
POC / regression test for the Hall of Rust architecture-bonus case bug.

calculate_rust_score() lower-cases the reported device_arch before matching,
but the PowerPC entries in the arch_bonus table use UPPER-CASE keys
('G3'/'G4'/'G5'). Because ``key in arch`` is a case-sensitive substring test,
'G4' in 'g4' is False, so a PowerPC machine — the exact hardware the Hall of
Rust exists to celebrate — never receives its architecture bonus.

Run:
    python3 -m pytest node/test_hall_of_rust_arch_bonus_poc.py -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from hall_of_rust import calculate_rust_score


def _isolated(arch):
    # Only the arch bonus contributes: no mfg year, no attestations, no plague
    # model, no thermal events, id default 999 (> 100 => no first-adopter bonus).
    return calculate_rust_score({"device_arch": arch}, current_year=2026)


def test_g4_gets_powerpc_bonus():
    assert _isolated("G4") == 70.0


def test_g3_gets_powerpc_bonus():
    assert _isolated("G3") == 80.0


def test_g5_gets_powerpc_bonus():
    assert _isolated("G5") == 60.0


def test_lowercase_g4_also_matches():
    # arch is reported lower-cased in some paths; must match too.
    assert _isolated("g4") == 70.0


def test_modern_still_zero():
    assert _isolated("modern") == 0.0


if __name__ == "__main__":
    for arch, expected in [("G4", 70.0), ("G3", 80.0), ("G5", 60.0),
                           ("g4", 70.0), ("modern", 0.0)]:
        got = _isolated(arch)
        print(f"arch={arch!r:>8}  expected={expected:>6}  got={got:>6}  "
              f"{'OK' if got == expected else 'FAIL'}")
