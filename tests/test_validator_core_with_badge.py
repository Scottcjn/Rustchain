# SPDX-License-Identifier: MIT

from datetime import datetime, timezone

from tools.validator_core_with_badge import simulate_entropy_score


def test_simulate_entropy_score_uses_current_utc_year_by_default():
    cpu_model = "Pentium III"
    bios_date = "1998-12-01"
    current_year = datetime.now(timezone.utc).year
    expected_age_weight = max(0, current_year - 1998)
    expected_score = round((expected_age_weight * 0.25) + (len(cpu_model) * 0.05), 2)

    assert simulate_entropy_score(cpu_model, bios_date) == expected_score


def test_simulate_entropy_score_can_cover_2026_age_weight():
    score = simulate_entropy_score("Pentium III", "1998-12-01", current_year=2026)

    assert score == 7.55
