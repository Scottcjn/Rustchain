from pathlib import Path


def test_governance_page_renders_proposal_fields_as_text_nodes():
    page = Path(__file__).resolve().parents[1] / "web" / "governance.html"
    html = page.read_text(encoding="utf-8")

    assert "function safeNumber(value, fallback=0)" in html
    assert "function text(value)" in html
    assert "function renderProposalCard(p)" in html
    assert "title.textContent = `#${safeNumber(p.id)} ${p.title ?? ''}`;" in html
    assert "meta.textContent = `${p.proposer_wallet ?? ''} • ${p.status ?? ''}`;" in html
    assert "text(p.description)" in html
    assert "text(`yes=${safeNumber(p.yes_weight).toFixed(4)} `)" in html
    assert "text(`no=${safeNumber(p.no_weight).toFixed(4)} `)" in html
    assert "text(`abstain=${safeNumber(p.abstain_weight).toFixed(4)}`)" in html
    assert "list.replaceChildren();" in html
    assert "list.appendChild(renderProposalCard(p));" in html

    assert "innerHTML" not in html
    assert "<b>#${p.id} ${p.title}</b>" not in html
    assert "<b>#${safeNumber(p.id)} ${escapeHtml(p.title)}</b>" not in html
    assert "${p.proposer_wallet}" not in html
    assert "${p.status}" not in html
    assert "${p.description}<br>" not in html
    assert "${escapeHtml(p.description)}" not in html
    assert "yes=${(p.yes_weight||0).toFixed(4)}" not in html
    assert "no=${(p.no_weight||0).toFixed(4)}" not in html
