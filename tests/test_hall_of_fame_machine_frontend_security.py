from pathlib import Path


def test_machine_profile_renders_timeline_fields_with_text_content():
    page = Path(__file__).resolve().parents[1] / "web" / "hall-of-fame" / "machine.html"
    html = page.read_text(encoding="utf-8")

    assert "function safeInt(v)" in html
    assert "function safeScore(v)" in html
    assert "function setStatusError(message)" in html
    assert "function renderTimeline(timeline, fallbackScore)" in html
    assert "status.replaceChildren(err);" in html
    assert "tbody.replaceChildren();" in html
    assert "cell.textContent=text;" in html
    assert "appendTimelineCell(row, x.date||'—');" in html
    assert "appendTimelineCell(row, safeInt(x.attestations??x.samples??0));" in html
    assert "appendTimelineCell(row, safeScore(x.rust_score??fallbackScore??'—'));" in html

    assert "document.getElementById('status').innerHTML" not in html
    assert "document.getElementById('timeline').innerHTML" not in html
    assert "t.map(x=>`<tr>" not in html
    assert "${x.date||'—'}</td>" not in html
    assert "${x.attestations??x.samples??0}</td>" not in html
    assert "${x.rust_score??m.rust_score??'—'}</td>" not in html
