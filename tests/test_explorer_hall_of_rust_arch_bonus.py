# SPDX-License-Identifier: MIT
"""
Regression test for the explorer Hall of Rust architecture-bonus case bug.

explorer/hall_of_rust.py::calculate_rust_score() lower-cases the reported
device_arch before matching, but the PowerPC entries in the arch_bonus table
used UPPER-CASE keys ('G3'/'G4'/'G5'). Because ``key in arch`` is a
case-sensitive substring test, 'G4' in 'g4' is False, so a PowerPC machine —
the exact hardware the Hall of Rust exists to celebrate — never received its
architecture bonus. This mirrors the already-merged node sibling fix (#7956);
the explorer copy was missed.

Run:
    python3 -m pytest tests/test_explorer_hall_of_rust_arch_bonus.py -q
"""
import importlib.util
import os

_EXPLORER = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "explorer", "hall_of_rust.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("explorer_hall_of_rust", _EXPLORER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _score(arch):
    # Isolated machine: no manufacture_year, no attestations, no plague model,
    # no thermal events, id default 999 (> 100 => no first-adopter bonus).
    # Only the architecture bonus contributes to the score.
    return _load().calculate_rust_score({"device_arch": arch})


def test_g3_gets_powerpc_bonus():
    assert _score("G3") == 80.0


def test_g4_gets_powerpc_bonus():
    assert _score("G4") == 70.0


def test_g5_gets_powerpc_bonus():
    assert _score("G5") == 60.0


def test_lowercase_g4_also_matches():
    # Some attestation paths report arch already lower-cased; must match too.
    assert _score("g4") == 70.0


def test_modern_still_zero():
    assert _score("modern") == 0.0


def test_486_bonus_unaffected():
    assert _score("486") == 150.0


if __name__ == "__main__":
    for arch, expected in [("G3", 80.0), ("G4", 70.0), ("G5", 60.0),
                           ("g4", 70.0), ("modern", 0.0), ("486", 150.0)]:
        got = _score(arch)
        print(f"arch={arch!r:>8}  expected={expected:>6}  got={got:>6}  "
              f"{'OK' if got == expected else 'FAIL'}")
