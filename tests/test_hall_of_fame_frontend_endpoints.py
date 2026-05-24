# SPDX-License-Identifier: MIT
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_hall_of_fame_index_uses_compat_leaderboard_endpoint():
    html = (ROOT / "web" / "hall-of-fame" / "index.html").read_text(
        encoding="utf-8"
    )

    assert "const API_LEADERBOARD = '/api/hall_of_fame/leaderboard';" in html
    assert "const API_STATS       = '/api/hall_of_fame/stats';" in html


def test_hall_of_fame_machine_uses_compat_machine_endpoint_and_shape():
    html = (ROOT / "web" / "hall-of-fame" / "machine.html").read_text(
        encoding="utf-8"
    )

    assert "fetch('/api/hall_of_fame/machine?id='+encodeURIComponent(id))" in html
    assert "const m=data.machine||data||{};" in html
