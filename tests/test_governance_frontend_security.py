from pathlib import Path


def test_governance_page_renders_proposal_fields_with_text_nodes():
    page = Path(__file__).resolve().parents[1] / "web" / "governance.html"
    html = page.read_text(encoding="utf-8")

    assert "function escapeHtml(value)" in html
    assert "function safeNumber(value, fallback=0)" in html
    assert "function textEl(tag, className, text)" in html
    assert "el.textContent = String(text ?? '');" in html
    assert "function renderProposalCard(p)" in html
    assert "div.appendChild(textEl('b', '', `#${safeNumber(p.id)} ${p.title ?? ''}`));" in html
    assert "div.appendChild(textEl('span', 'muted', `${p.proposer_wallet ?? ''} - ${p.status ?? ''}`));" in html
    assert "div.appendChild(document.createTextNode(String(p.description ?? '')));" in html
    assert "list.appendChild(renderProposalCard(p));" in html

    assert "div.innerHTML = `<b>#${safeNumber(p.id)} ${escapeHtml(p.title)}</b><br>" not in html
    assert "${escapeHtml(p.proposer_wallet)}" not in html
    assert "${escapeHtml(p.status)}" not in html
    assert "${escapeHtml(p.description)}" not in html

    assert "<b>#${p.id} ${p.title}</b>" not in html
    assert "${p.proposer_wallet}" not in html
    assert "${p.status}" not in html
    assert "${p.description}<br>" not in html
    assert "yes=${(p.yes_weight||0).toFixed(4)}" not in html
    assert "no=${(p.no_weight||0).toFixed(4)}" not in html
