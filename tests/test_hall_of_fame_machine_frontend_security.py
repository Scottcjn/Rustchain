from pathlib import Path


def test_machine_profile_escapes_timeline_fields_before_inner_html():
    page = Path(__file__).resolve().parents[1] / "web" / "hall-of-fame" / "machine.html"
    html = page.read_text(encoding="utf-8")

    assert "function esc(s)" in html
    assert "function safeInt(v)" in html
    assert "function safeScore(v)" in html
    assert "${esc(x.date||'—')}" in html
    assert "${safeInt(x.attestations??x.samples??0)}" in html
    assert "${safeScore(x.rust_score??m.rust_score??'—')}" in html

    assert "${x.date||'—'}</td>" not in html
    assert "${x.attestations??x.samples??0}</td>" not in html
    assert "${x.rust_score??m.rust_score??'—'}</td>" not in html
