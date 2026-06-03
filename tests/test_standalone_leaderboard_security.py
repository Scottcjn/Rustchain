from pathlib import Path


LEADERBOARD_HTML = Path(__file__).resolve().parents[1] / "tools" / "leaderboard.html"


def test_leaderboard_normalizes_current_miners_api_envelope():
    html = LEADERBOARD_HTML.read_text(encoding="utf-8")

    assert "const minersPayload = await minersRes.json();" in html
    assert "function normalizeMinerRows(payload)" in html
    assert "payload.miners || payload.data || payload.items || []" in html
    assert "const miners = normalizeMinerRows(minersPayload);" in html


def test_leaderboard_normalizes_miner_row_ids():
    html = LEADERBOARD_HTML.read_text(encoding="utf-8")

    assert "const miner = row.miner || row.miner_id || row.id;" in html
    assert "return { ...row, miner: String(miner) };" in html
    assert "}).filter(Boolean);" in html


def test_leaderboard_rows_do_not_render_miner_fields_with_inner_html():
    html = LEADERBOARD_HTML.read_text(encoding="utf-8")

    assert "tr.innerHTML = `" not in html
    assert '${m.miner.substring(0, 12)}...' not in html
    assert "${m.device_family} ${m.device_arch}" not in html

    assert "function appendTextCell(row, text)" in html
    assert "minerCell.title = miner;" in html
    assert "badge.textContent = isVintage ? 'Vintage' : 'Modern';" in html


def test_leaderboard_error_row_uses_text_content():
    html = LEADERBOARD_HTML.read_text(encoding="utf-8")

    assert "function renderErrorRow(err)" in html
    assert "cell.textContent = `Error: ${err.message}." in html
    assert "renderErrorRow(err);" in html
    assert 'class="error">Error: ${err.message}' not in html
