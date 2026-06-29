"""
Tests for Miner Setup Wizard DOM rendering security hardening (Issue #7191).

Verifies that docs/miner-setup-wizard/index.html:
- Introduces the makePillFragment() DOM helper for node response rendering
- Does not use innerHTML to render remote node /health or /api/miners responses
- Uses textContent/createElement for testOut and minerOut panels

SPDX-License-Identifier: MIT
"""

import re
import subprocess
import pytest
from pathlib import Path


WIZARD_HTML = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "miner-setup-wizard"
    / "index.html"
)


@pytest.fixture(scope="module")
def wizard_source():
    """Read the wizard HTML source once for all tests in this module."""
    return WIZARD_HTML.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. makePillFragment helper present
# ---------------------------------------------------------------------------

class TestMakePillFragmentHelper:
    """The safe DOM helper makePillFragment() must be defined."""

    def test_make_pill_fragment_defined(self, wizard_source):
        """makePillFragment() is defined in the wizard script."""
        assert "function makePillFragment(" in wizard_source, \
            "makePillFragment() DOM helper is missing from the wizard"

    def test_make_pill_fragment_uses_textcontent(self, wizard_source):
        """makePillFragment() sets pill label via textContent."""
        # Extract the function body
        fn_match = re.search(
            r'function makePillFragment\((.*?)\}\s*\n',
            wizard_source,
            re.DOTALL,
        )
        if fn_match:
            fn_body = fn_match.group(0)
            assert ".textContent = " in fn_body, \
                "makePillFragment() must set pill text via textContent"
            assert ".innerHTML" not in fn_body, \
                "makePillFragment() must not use innerHTML"

    def test_make_pill_fragment_uses_createelement(self, wizard_source):
        """makePillFragment() builds DOM elements with createElement."""
        fn_match = re.search(
            r'function makePillFragment\((.*?)\}\s*\n',
            wizard_source,
            re.DOTALL,
        )
        if fn_match:
            fn_body = fn_match.group(0)
            assert "createElement(" in fn_body, \
                "makePillFragment() must use createElement to build elements"


# ---------------------------------------------------------------------------
# 2. testOut (node /health response) — no innerHTML on remote data
# ---------------------------------------------------------------------------

class TestTestOutSafety:
    """testOut div must be populated via DOM API, not innerHTML."""

    def test_testout_no_innerHTML_assignment(self, wizard_source):
        """
        The 'testOut' assignment block must not use innerHTML for the
        remote node /health response body (issue #7191).
        """
        # Locate the testBtn onclick block
        testbtn_match = re.search(
            r"testBtn.*?onclick\s*=\s*async\s*\(\)\s*=>\s*\{(.*?)^\s+\}",
            wizard_source,
            re.DOTALL | re.MULTILINE,
        )
        if testbtn_match:
            block = testbtn_match.group(1)
            innerhtml_with_template = re.compile(r"testOut.*?innerHTML\s*=\s*[r`'\"]", re.DOTALL)
            assert not innerhtml_with_template.search(block), \
                "testOut must not be populated via innerHTML on node response"

    def test_testout_uses_textcontent_or_appendchild(self, wizard_source):
        """testOut must be cleared/filled via textContent or appendChild."""
        assert "testOut.textContent = ''" in wizard_source or \
               "testOut.appendChild(" in wizard_source, \
            "testOut should be cleared with textContent and filled with appendChild"

    def test_testout_uses_makepillfragment(self, wizard_source):
        """testOut should delegate rendering to makePillFragment()."""
        assert "makePillFragment(" in wizard_source, \
            "The wizard should use makePillFragment() for testOut rendering"


# ---------------------------------------------------------------------------
# 3. minerOut (/api/miners response) — no innerHTML on remote data
# ---------------------------------------------------------------------------

class TestMinerOutSafety:
    """minerOut div must be populated via DOM API, not innerHTML."""

    def test_minerout_no_innerHTML_on_api_data(self, wizard_source):
        """
        The 'minerOut' block must not use innerHTML with dynamic API response
        values (issue #7191).
        """
        # Find any remaining innerHTML assignments targeting minerOut
        innerhtml_pattern = re.compile(
            r"minerOut\b.*?\.innerHTML\s*=\s*[`'\"].*?\$\{",
            re.DOTALL,
        )
        matches = innerhtml_pattern.findall(wizard_source)
        assert not matches, \
            "minerOut must not use innerHTML with interpolated API values"

    def test_minerout_cleared_via_textcontent(self, wizard_source):
        """minerOut is cleared via textContent before re-population."""
        assert "minerOut.textContent = ''" in wizard_source, \
            "minerOut should be cleared with minerOut.textContent = ''"

    def test_minerout_not_found_uses_textcontent(self, wizard_source):
        """'Not found yet' message uses textContent, not innerHTML."""
        # The "Not found" branch must use textContent for user-visible text
        assert re.search(r"warnPill\.textContent\s*=\s*['\"]Not found yet['\"]", wizard_source), \
            "'Not found yet' pill text should be set via textContent"


# ---------------------------------------------------------------------------
# 4. h() escaper still present for static template use
# ---------------------------------------------------------------------------

def test_h_escape_function_present(wizard_source):
    """The h() HTML escaper must still be defined for static template contexts."""
    assert "function h(value)" in wizard_source, \
        "h() escaper function should still exist in the wizard"


# ---------------------------------------------------------------------------
# 5. Syntax validity via Node.js inline script check
# ---------------------------------------------------------------------------

def test_wizard_html_script_syntax_valid():
    """
    Extracts the inline <script> block and checks it for JS parse errors.
    Uses node --check on the extracted script content.
    """
    import tempfile, os

    source = WIZARD_HTML.read_text(encoding="utf-8")
    # Extract content between <script> and </script>
    script_match = re.search(r'<script>(.*?)</script>', source, re.DOTALL)
    assert script_match, "No <script> block found in wizard HTML"

    script_content = script_match.group(1)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".js", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(script_content)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            ["node", "--check", tmp_path],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0, (
            f"JS syntax error in wizard script:\n{result.stderr}"
        )
    finally:
        os.unlink(tmp_path)
