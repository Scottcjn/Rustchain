from pathlib import Path


def test_governance_page_uses_text_content_for_proposal_rendering():
    page = Path(__file__).resolve().parents[1] / "web" / "governance.html"
    html = page.read_text(encoding="utf-8")

    # The proposal list must build cards with textContent / DOM APIs, not the
    # historical `escapeHtml + innerHTML` template that is a fragile XSS sink
    # (Issue #7200). The textContent invariant is the safe shape.
    assert "function safeNumber(value, fallback=0)" in html

    # New invariant: the proposal card builder creates elements with
    # createElement and assigns them textContent. The escapeHtml+innerHTML
    # template for the proposal list is forbidden.
    assert "idEl.textContent = `#${safeNumber(p.id)} ${String(p.title ?? '')}`" in html
    assert "mutedEl.className = 'muted'" in html
    assert "mutedEl.textContent = `${String(p.proposer_wallet ?? '')} • ${String(p.status ?? '')}`" in html
    assert "descEl.textContent = String(p.description ?? '')" in html
    assert "div.appendChild(idEl)" in html
    assert "div.appendChild(mutedEl)" in html

    # The legacy fragile patterns must NOT appear in the proposal list builder.
    forbidden_patterns = [
        "<b>#${safeNumber(p.id)} ${escapeHtml(p.title)}</b>",
        "${escapeHtml(p.proposer_wallet)}",
        "${escapeHtml(p.status)}",
        "${escapeHtml(p.description)}",
        "<b>#${p.id} ${p.title}</b>",
        "${p.proposer_wallet}",
        "${p.status}",
        "${p.description}<br>",
    ]
    for pattern in forbidden_patterns:
        assert pattern not in html, f"legacy fragile pattern must be removed: {pattern}"
