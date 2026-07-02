"""
Tests for claims page DOM-rendering security (issue #7204).

The implementation was upgraded from innerHTML + escapeHtml() helper to a
full DOM-API approach (createElement / textContent / appendChild). These
tests assert the *security property* — no innerHTML sink on dynamic API data
— rather than the specific helper function that was in the old implementation.
"""

import re
from pathlib import Path


CLAIMS_JS = Path(__file__).resolve().parents[1] / "web" / "claims" / "claims.js"


def _source():
    """Return the current claims.js source text."""
    return CLAIMS_JS.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. No dynamic innerHTML sinks on API-sourced data
# ---------------------------------------------------------------------------


def test_claims_page_no_dynamic_innerHTML_template_literals():
    """
    Asserts that no innerHTML template-literal sinks exist in claims.js.

    A pattern like:
        someEl.innerHTML = `...${apiField}...`
    routes API response values through the HTML parser regardless of escaping,
    creating a DOM XSS sink. The rewrite eliminates this entirely by using
    createElement/textContent/appendChild instead.
    """
    source = _source()
    dynamic_sink = re.compile(r"\.innerHTML\s*=\s*`[^`]*\$\{", re.MULTILINE)
    matches = dynamic_sink.findall(source)
    assert not matches, (
        f"Found {len(matches)} dynamic innerHTML template literal(s) in claims.js. "
        "All dynamic data from API responses must be rendered via the DOM API "
        "(createElement / textContent / appendChild)."
    )


def test_claims_page_no_concat_innerHTML_on_api_data():
    """
    Asserts there are no string-concatenation innerHTML sinks for API data.

    e.g.  el.innerHTML += "..." + apiValue  is forbidden.
    """
    source = _source()
    # Look for innerHTML += or innerHTML = "..." + variable patterns
    concat_sink = re.compile(r"\.innerHTML\s*\+?=\s*[\"'][^\"']*[\"']\s*\+", re.MULTILINE)
    matches = concat_sink.findall(source)
    assert not matches, (
        f"Found {len(matches)} string-concatenation innerHTML sink(s) in claims.js."
    )


# ---------------------------------------------------------------------------
# 2. DOM-API rendering helpers are present
# ---------------------------------------------------------------------------


def test_claims_page_dom_helper_makeEl_defined():
    """The makeEl() DOM builder helper must be defined."""
    assert "function makeEl(" in _source(), \
        "makeEl() DOM helper is missing from claims.js"


def test_claims_page_dom_helper_makeSummaryRow_defined():
    """The makeSummaryRow() DOM builder helper must be defined."""
    assert "function makeSummaryRow(" in _source(), \
        "makeSummaryRow() DOM helper is missing from claims.js"


def test_claims_page_dom_helper_makeCheckItem_defined():
    """The makeCheckItem() DOM builder helper must be defined."""
    assert "function makeCheckItem(" in _source(), \
        "makeCheckItem() DOM helper is missing from claims.js"


# ---------------------------------------------------------------------------
# 3. Specific render functions use DOM API (no innerHTML on containers)
# ---------------------------------------------------------------------------


def test_claims_page_eligibility_cleared_via_textcontent():
    """renderEligibilityResult() clears its container via textContent, not innerHTML."""
    assert "eligibilityResult.textContent = ''" in _source(), \
        "renderEligibilityResult() must clear container via textContent"


def test_claims_page_claim_summary_cleared_via_textcontent():
    """renderClaimSummary() clears its container via textContent, not innerHTML."""
    assert "claimSummary.textContent = ''" in _source(), \
        "renderClaimSummary() must clear container via textContent"


def test_claims_page_history_tbody_cleared_via_textcontent():
    """renderClaimHistory() clears the table body via textContent, not innerHTML."""
    assert "tbody.textContent = ''" in _source(), \
        "renderClaimHistory() must clear tbody via textContent"


# ---------------------------------------------------------------------------
# 4. Epoch <select> populated via DOM API
# ---------------------------------------------------------------------------


def test_claims_page_epoch_option_via_createElement():
    """
    Epoch <option> elements must be created via createElement, not via an
    innerHTML string that embeds epoch numbers from the API response.
    """
    source = _source()
    assert "createElement('option')" in source or 'createElement("option")' in source, \
        "Epoch options must be created with createElement('option')"


def test_claims_page_epoch_option_text_via_textcontent():
    """Epoch option text must be assigned via textContent."""
    assert re.search(r"opt\.textContent\s*=", _source()), \
        "Epoch option text should be set via opt.textContent"


# ---------------------------------------------------------------------------
# 5. No unescaped API fields directly in unsafe sinks
# ---------------------------------------------------------------------------


def test_claims_page_no_bare_api_fields_in_innerHTML():
    """
    Asserts the specific unsafe bare-interpolation patterns from the original
    implementation are no longer used **inside innerHTML template literals**.

    Template literals used with textContent are safe and allowed.
    Only innerHTML sinks that embed raw API values are forbidden.

    Previously unsafe (removed in the DOM-API rewrite):
        someEl.innerHTML = `...${eligibility.miner_id}...`
        someEl.innerHTML = `...${claim.claim_id}...`
    """
    source = _source()

    # Regex: find innerHTML = `...pattern...` contexts
    # We look for .innerHTML = ` ... ` blocks containing the raw field names
    inner_html_blocks = re.findall(r"\.innerHTML\s*=\s*`[^`]*`", source, re.DOTALL)

    unsafe_fields_in_html = [
        "eligibility.miner_id",
        "eligibility.attestation",
        "eligibility.wallet_address",
        "eligibility.reason",
        "epoch.epoch",
        "epoch.reward_urtc",
        "claim.claim_id",
        "claim.status",
        "result.claim_id",
    ]

    for block in inner_html_blocks:
        for field in unsafe_fields_in_html:
            assert field not in block, (
                f"API field {field!r} found directly inside an innerHTML template literal — "
                "use createElement/textContent instead."
            )


# ---------------------------------------------------------------------------
# 6. CSV export quotes cells (formula injection prevention)
# ---------------------------------------------------------------------------


def test_claims_page_csv_cells_quoted():
    """handleExportHistory() must quote CSV cells to prevent formula injection."""
    source = _source()
    assert "const escape = v =>" in source or "const escape=v=>" in source, \
        "CSV export must have a cell-quoting escape function"


def test_claims_page_csv_double_quotes_escaped():
    """Embedded double-quotes in CSV must be doubled for RFC 4180 compliance."""
    assert '.replace(/"/g, \'""\')' in _source() or ".replace(/\"/g,'\"\"')" in _source(), \
        "CSV escape must double embedded double-quotes"
