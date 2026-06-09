from pathlib import Path


def test_machine_profile_renders_timeline_fields_without_inner_html():
    page = Path(__file__).resolve().parents[1] / "web" / "hall-of-fame" / "machine.html"
    html = page.read_text(encoding="utf-8")

    assert "function safeInt(v)" in html
    assert "function safeScore(v)" in html
    assert "function renderStatus(message)" in html
    assert "function renderTimeline(rows, fallbackScore)" in html
    assert "timeline.replaceChildren(...rows.map(x=>el('tr',{},[" in html
    assert "el('td',{text:x.date||'—'})" in html
    assert "el('td',{text:safeInt(x.attestations??x.samples??0)})" in html
    assert "el('td',{text:safeScore(x.rust_score??fallbackScore??'—')})" in html

    assert "document.getElementById('timeline').innerHTML" not in html
    assert "${x.date||'—'}</td>" not in html
    assert "${x.attestations??x.samples??0}</td>" not in html
    assert "${x.rust_score??m.rust_score??'—'}</td>" not in html
