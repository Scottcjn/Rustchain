from pathlib import Path


LEADERBOARD_HTML = Path(__file__).resolve().parents[1] / "tools" / "leaderboard.html"


def test_leaderboard_normalizes_current_miners_api_envelope():
    html = LEADERBOARD_HTML.read_text(encoding="utf-8")

    assert "const minersPayload = await minersRes.json();" in html
    assert "minersPayload.miners || minersPayload.data || []" in html


def test_leaderboard_rows_do_not_render_miner_fields_with_inner_html():
    html = LEADERBOARD_HTML.read_text(encoding="utf-8")

    assert "tr.innerHTML = `" not in html
    assert '${m.miner.substring(0, 12)}...' not in html
    assert "${m.device_family} ${m.device_arch}" not in html

    assert "function appendTextCell(row, text)" in html
    assert "minerCell.title = miner;" in html
    assert "badge.textContent = isVintage ? 'Vintage' : 'Modern';" in html
