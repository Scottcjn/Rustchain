from pathlib import Path


def test_governance_page_escapes_proposal_fields_before_inner_html():
    page = Path(__file__).resolve().parents[1] / "web" / "governance.html"
    html = page.read_text(encoding="utf-8")

    assert "function escapeHtml(value)" in html
    assert "function safeNumber(value, fallback=0)" in html
    assert "<b>#${safeNumber(p.id)} ${escapeHtml(p.title)}</b>" in html
    assert "${escapeHtml(p.proposer_wallet)}" in html
    assert "${escapeHtml(p.status)}" in html
    assert "${escapeHtml(p.description)}" in html
    assert "yes=${safeNumber(p.yes_weight).toFixed(4)}" in html
    assert "no=${safeNumber(p.no_weight).toFixed(4)}" in html

    assert "<b>#${p.id} ${p.title}</b>" not in html
    assert "${p.proposer_wallet}" not in html
    assert "${p.status}" not in html
    assert "${p.description}<br>" not in html
    assert "yes=${(p.yes_weight||0).toFixed(4)}" not in html
    assert "no=${(p.no_weight||0).toFixed(4)}" not in html
