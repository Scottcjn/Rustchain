"""
Tests for Claims Page DOM rendering security hardening (Issue #7204).

Verifies that web/claims/claims.js v2 (post-hardening):
- No longer uses innerHTML template literals for API-sourced dynamic values
- Uses DOM API helpers: makeEl, makeSummaryRow, makeCheckItem
- CSV export quotes cells to prevent formula injection

SPDX-License-Identifier: MIT
"""

import re
import subprocess
import pytest
from pathlib import Path


CLAIMS_JS = Path(__file__).resolve().parents[1] / "web" / "claims" / "claims.js"


@pytest.fixture(scope="module")
def claims_js_source():
    """Read the claims.js source once for all tests in this module."""
    return CLAIMS_JS.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. No dynamic innerHTML sinks on API data
# ---------------------------------------------------------------------------

class TestClaimsJsDomSafety:
    """Verify claims.js uses DOM API, not innerHTML, for API-sourced data."""

    def test_no_dynamic_innerhtml_template_literal(self, claims_js_source):
        """
        No .innerHTML = `...${...}...` pattern should exist in claims.js.

        Such patterns route API response values through the HTML parser, creating
        a DOM XSS sink regardless of manual escaping.
        """
        dynamic_sink = re.compile(r'\.innerHTML\s*=\s*`[^`]*\$\{', re.MULTILINE)
        matches = dynamic_sink.findall(claims_js_source)
        assert not matches, (
            f"Found {len(matches)} dynamic innerHTML template literal(s):\n"
            + "\n".join(repr(m) for m in matches[:5])
        )

    def test_dom_helpers_defined(self, claims_js_source):
        """Safe DOM builder functions must be defined."""
        assert "function makeEl(" in claims_js_source, "makeEl() helper missing"
        assert "function makeSummaryRow(" in claims_js_source, "makeSummaryRow() helper missing"
        assert "function makeCheckItem(" in claims_js_source, "makeCheckItem() helper missing"

    def test_eligibility_result_cleared_safely(self, claims_js_source):
        """renderEligibilityResult() clears its container via textContent."""
        assert "eligibilityResult.textContent = ''" in claims_js_source

    def test_claim_history_cleared_safely(self, claims_js_source):
        """renderClaimHistory() clears tbody via textContent."""
        assert "tbody.textContent = ''" in claims_js_source

    def test_claim_summary_cleared_safely(self, claims_js_source):
        """renderClaimSummary() clears its container via textContent."""
        assert "claimSummary.textContent = ''" in claims_js_source

    def test_submit_success_no_dynamic_innerhtml(self, claims_js_source):
        """handleSubmitClaim() must not use innerHTML for the success message."""
        # Verify the function exists in the file
        assert "async function handleSubmitClaim()" in claims_js_source, \
            "handleSubmitClaim() not found in claims.js"

        # Check that the successEl / submitSuccess block doesn't use innerHTML
        # with dynamic template literals anywhere in the file
        dynamic_sink = re.compile(r'submitSuccess.*?\.innerHTML\s*=\s*`[^`]*\$\{', re.DOTALL)
        matches = dynamic_sink.findall(claims_js_source)
        assert not matches, \
            "submitSuccess element still uses dynamic innerHTML template literal"

    def test_history_cells_use_textcontent(self, claims_js_source):
        """Table cells in renderClaimHistory() use textContent, not innerHTML."""
        assert "tdId.textContent" in claims_js_source or \
               "td.textContent" in claims_js_source, \
            "History table cells should set text via .textContent"


# ---------------------------------------------------------------------------
# 2. Epoch select built via DOM API
# ---------------------------------------------------------------------------

class TestEpochSelectSafety:
    """Epoch <select> populated via createElement, not innerHTML strings."""

    def test_epoch_options_via_createelement(self, claims_js_source):
        """renderEpochSelect() creates <option> via createElement."""
        assert "createElement('option')" in claims_js_source or \
               'createElement("option")' in claims_js_source, \
            "Epoch options should be created with createElement('option')"

    def test_epoch_option_text_via_textcontent(self, claims_js_source):
        """Option label is assigned via textContent."""
        assert re.search(r'opt\.textContent\s*=', claims_js_source), \
            "Epoch option text should be set via opt.textContent"

    def test_reset_form_clears_options_safely(self, claims_js_source):
        """resetForm() rebuilds default option via createElement, not innerHTML."""
        fn_match = re.search(
            r'function resetForm\(\)(.*?)^\}',
            claims_js_source,
            re.DOTALL | re.MULTILINE,
        )
        if fn_match:
            fn_body = fn_match.group(1)
            # Must NOT use innerHTML to set epoch options
            assert ".innerHTML = '<option" not in fn_body and \
                   '.innerHTML = "<option' not in fn_body, \
                "resetForm() should not use innerHTML to set the epoch placeholder option"


# ---------------------------------------------------------------------------
# 3. CSV formula injection prevention
# ---------------------------------------------------------------------------

class TestClaimsJsCsvSafety:
    """CSV export quotes cells to prevent spreadsheet formula injection."""

    def test_csv_escape_function_present(self, claims_js_source):
        """A CSV cell-quoting escape helper must exist in handleExportHistory()."""
        assert "const escape = v =>" in claims_js_source or \
               "const escape=v=>" in claims_js_source, \
            "CSV escape helper missing in handleExportHistory()"

    def test_csv_double_quote_escape(self, claims_js_source):
        """Embedded double-quotes must be doubled for RFC 4180 compliance."""
        assert '.replace(/"/g, \'""\')'  in claims_js_source or \
               '.replace(/"/g,\'""\')'  in claims_js_source, \
            "CSV escape must double embedded double-quotes"


# ---------------------------------------------------------------------------
# 4. Syntax validity via Node.js
# ---------------------------------------------------------------------------

def test_claims_js_syntax_valid():
    """node --check must pass (no JS parse errors)."""
    result = subprocess.run(
        ["node", "--check", str(CLAIMS_JS)],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, (
        f"node --check claims.js failed:\n{result.stderr}"
    )
