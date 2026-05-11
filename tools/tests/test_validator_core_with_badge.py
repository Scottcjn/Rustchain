# SPDX-License-Identifier: MIT

import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

import validator_core_with_badge  # noqa: E402


def test_entropy_score_uses_current_year_for_bios_age(monkeypatch):
    monkeypatch.setattr(validator_core_with_badge, "current_utc_year", lambda: 2026)

    score = validator_core_with_badge.simulate_entropy_score("Pentium III", "1998-12-01")

    assert score == 7.55
