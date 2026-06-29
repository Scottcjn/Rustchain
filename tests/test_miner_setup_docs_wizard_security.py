"""
Tests for miner setup wizard DOM-rendering security (issue #7191).

The implementation was upgraded from innerHTML + h() escaper to a DOM-API
approach using the makePillFragment() helper (createElement / textContent /
DocumentFragment). These tests assert the *security property* — no innerHTML
sink on remote node response data — rather than specific string patterns
from the old implementation.
"""

import re
from pathlib import Path


WIZARD_HTML = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "miner-setup-wizard"
    / "index.html"
)


def _source():
    """Return the current wizard HTML source text."""
    return WIZARD_HTML.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. makePillFragment() DOM helper is present
# ---------------------------------------------------------------------------


def test_make_pill_fragment_helper_defined():
    """
    makePillFragment() must be defined in the wizard script.

    This helper builds pill + pre + note entirely via the DOM API, replacing
    the old innerHTML template-literal pattern.
    """
    assert "function makePillFragment(" in _source(), \
        "makePillFragment() DOM helper is missing from the wizard"


def test_make_pill_fragment_uses_textcontent():
    """makePillFragment() sets pill label via textContent, not innerHTML."""
    source = _source()
    fn_match = re.search(r"function makePillFragment\(.*?\}\s*\n", source, re.DOTALL)
    if fn_match:
        fn_body = fn_match.group(0)
        assert ".textContent = " in fn_body, \
            "makePillFragment() must assign pill text via .textContent"
        assert ".innerHTML" not in fn_body, \
            "makePillFragment() must not use innerHTML"


def test_make_pill_fragment_uses_createElement():
    """makePillFragment() builds elements via createElement."""
    source = _source()
    fn_match = re.search(r"function makePillFragment\(.*?\}\s*\n", source, re.DOTALL)
    if fn_match:
        assert "createElement(" in fn_match.group(0), \
            "makePillFragment() must use createElement"


# ---------------------------------------------------------------------------
# 2. testOut (node /health response) — no innerHTML on remote data
# ---------------------------------------------------------------------------


def test_testout_no_innerHTML_template_on_node_response():
    """
    The testOut element must not be populated via an innerHTML template
    literal that embeds the raw node /health response text.

    Old pattern (unsafe):
        testOut.innerHTML = `<span>...</span><pre>${h(r.text)}</pre>`
    New pattern (safe):
        testOut.textContent = '';
        testOut.appendChild(makePillFragment(...));
    """
    source = _source()
    # Old assertions — the innerHTML template strings for testOut must be gone
    assert "<pre>${h(r.text)}</pre>" not in source, (
        "testOut must not use innerHTML with h(r.text) — use makePillFragment() instead"
    )


def test_testout_cleared_via_textcontent():
    """testOut is cleared via textContent before re-population."""
    assert "testOut.textContent = ''" in _source(), \
        "testOut should be cleared via testOut.textContent = ''"


def test_testout_uses_makepillfragment():
    """testOut rendering delegates to the safe makePillFragment() helper."""
    source = _source()
    assert "makePillFragment(" in source, \
        "testOut rendering must use makePillFragment()"


# ---------------------------------------------------------------------------
# 3. minerOut (/api/miners response) — no innerHTML on remote data
# ---------------------------------------------------------------------------


def test_minerout_no_innerHTML_template_on_api_response():
    """
    The minerOut element must not be populated via an innerHTML template
    literal that embeds raw API response data.

    Old patterns (unsafe):
        minerOut.innerHTML = `<span>Found</span><pre>${h(JSON.stringify(hit,null,2))}</pre>`
        minerOut.innerHTML = `<span>Check failed</span><pre>${h(String(e))}</pre>`
    """
    source = _source()
    assert "<pre>${h(JSON.stringify(hit,null,2))}</pre>" not in source, (
        "minerOut must not use innerHTML with JSON.stringify(hit) — use makePillFragment()"
    )
    assert "<pre>${h(String(e))}</pre>" not in source, (
        "minerOut must not use innerHTML with String(e) — use makePillFragment()"
    )


def test_minerout_cleared_via_textcontent():
    """minerOut is cleared via textContent before re-population."""
    assert "minerOut.textContent = ''" in _source(), \
        "minerOut should be cleared via minerOut.textContent = ''"


# ---------------------------------------------------------------------------
# 4. h() escaper still present for static template use
# ---------------------------------------------------------------------------


def test_h_escape_function_still_present():
    """
    The h() HTML escaper must still exist for the static template contexts
    (commandBlock, platform detection display, wallet name inputs) that still
    use innerHTML with fully static or local-state-only strings.
    """
    assert "function h(value)" in _source(), \
        "h() escaper must still be defined for static template contexts"


# ---------------------------------------------------------------------------
# 5. commandBlock still properly escapes the copy attribute
# ---------------------------------------------------------------------------


def test_generated_command_blocks_escape_display_and_copy_attribute():
    """
    commandBlock() must escape the command string with h() when embedding
    it into the innerHTML template, and must use data-copy= for the copy
    attribute rather than an inline onclick with unescaped data.

    This test is unchanged from the original because commandBlock() renders
    developer-controlled command strings (no remote data), and the pattern
    is still correct.
    """
    source = _source()

    assert "return `<pre>${cmd}</pre>" not in source, \
        "commandBlock must escape cmd via h(cmd), not raw ${cmd}"
    assert 'onclick="copyText(${JSON.stringify(cmd)})"' not in source, \
        "commandBlock must use data-copy attribute, not inline onclick with raw data"

    assert "return `<pre>${h(cmd)}</pre>" in source, \
        "commandBlock must use h(cmd) for display"
    assert 'data-copy="${h(cmd)}" onclick="copyText(this.dataset.copy)"' in source, \
        "commandBlock must use data-copy= pattern for copy button"
