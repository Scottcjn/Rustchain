"""Regression test for the RustChain airdrop claim UI DOM hardening (#7214).

The airdrop page previously used `innerHTML` template-string rendering for several
status messages. Each of those interpolated at least one attacker-influenceable
string (mock user login, wallet address, eligibility values, generated RTC wallet
name, claim-summary fields). Any value containing markup would be parsed and
executed in the page.

This test enforces that the live source code in `airdrop/index.html` no longer
contains the unsafe innerHTML assignments and uses DOM-construction helpers
(`renderStatus`, `buildCheckRow`, `createElement`, `textContent`) instead.

See: https://github.com/Scottcjn/Rustchain/issues/7214
"""

from pathlib import Path


PAGE = Path(__file__).resolve().parents[1] / "airdrop" / "index.html"


def _read_page() -> str:
    return PAGE.read_text(encoding="utf-8")


def test_airdrop_html_exists():
    assert PAGE.is_file(), f"airdrop page missing at {PAGE}"


def test_airdrop_does_not_assign_innerhtml_to_status_or_rendered_containers():
    """No `.innerHTML = ` template-string assignments inside the airdrop script.

    Comments mentioning innerHTML are allowed (e.g. "without using innerHTML").
    The banned form is an actual assignment of a template literal to innerHTML.
    """
    html = _read_page()
    # Disallowed patterns:
    banned_substrings = [
        "statusBox.innerHTML = `",
        "out.innerHTML = `",
        ".innerHTML = `",
        ".innerHTML =\"",
    ]
    for banned in banned_substrings:
        assert banned not in html, (
            f"airdrop/index.html still uses banned innerHTML assignment: {banned!r}. "
            "Replace with renderStatus() / buildCheckRow() helpers (#7214)."
        )


def test_airdrop_uses_renderstatus_helper():
    html = _read_page()
    assert "function renderStatus(container, segments)" in html, (
        "Expected `renderStatus(container, segments)` helper in airdrop/index.html. "
        "The helper builds status boxes from typed segments via createElement + textContent."
    )


def test_airdrop_uses_buildcheckrow_helper():
    html = _read_page()
    assert "function buildCheckRow(icon, text)" in html, (
        "Expected `buildCheckRow(icon, text)` helper in airdrop/index.html. "
        "The helper builds each eligibility / anti-sybil row as DOM nodes."
    )


def test_renderstatus_uses_textcontent_and_createelement():
    """The renderStatus helper must not write to innerHTML and must build DOM nodes."""
    html = _read_page()
    # Find the renderStatus function body
    start = html.find("function renderStatus(container, segments)")
    assert start != -1, "renderStatus helper not found"
    # Look ahead for the closing brace of the function. Helper ends right before
    # the next top-level helper or `function unlockStep`.
    end_candidates = [
        html.find("function unlockStep", start),
        html.find("function buildCheckRow", start),
    ]
    end_candidates = [c for c in end_candidates if c != -1]
    assert end_candidates, "Could not find end of renderStatus body"
    body = html[start:min(end_candidates)]

    assert ".innerHTML" not in body, (
        "renderStatus must not assign innerHTML; use createElement + textContent."
    )
    assert "createElement" in body, "renderStatus must use createElement"
    assert "textContent" in body, "renderStatus must use textContent to assign text"
    assert "appendChild" in body, "renderStatus must use appendChild to attach nodes"


def test_buildcheckrow_uses_textcontent_and_createelement():
    html = _read_page()
    start = html.find("function buildCheckRow(icon, text)")
    assert start != -1, "buildCheckRow helper not found"
    end = html.find("function unlockStep", start)
    assert end != -1, "Could not find end of buildCheckRow body"
    body = html[start:end]

    assert ".innerHTML" not in body, (
        "buildCheckRow must not assign innerHTML; use createElement + textContent."
    )
    assert "createElement" in body, "buildCheckRow must use createElement"
    assert "textContent" in body, "buildCheckRow must use textContent"


def test_airdrop_renders_check_rows_via_helper_calls():
    """The check-rows and sybil-rows containers must be populated through the helper.

    Pre-fix code used `innerHTML = ...` template literals to inject rows.
    Post-fix code must call `buildCheckRow(...)` for each row.
    """
    html = _read_page()
    assert "checkRowsEl.appendChild(buildCheckRow(" in html, (
        "Expected checkRowsEl.appendChild(buildCheckRow(...)) calls in airdrop/index.html."
    )
    assert "sybilRowsEl.appendChild(buildCheckRow(" in html, (
        "Expected sybilRowsEl.appendChild(buildCheckRow(...)) calls in airdrop/index.html."
    )


def test_airdrop_no_inline_template_strings_for_claim_summary():
    """The claim-summary block must be built via renderStatus, not a template literal."""
    html = _read_page()
    # The original dangerous block had this exact prefix:
    assert "✅ Claim submitted successfully!<br><br>" not in html, (
        "airdrop/index.html still embeds the claim-summary template literal with <br><br>. "
        "Use renderStatus(statusBox, [...]) instead (#7214)."
    )
    # The rendered "Claim submitted" status must go through renderStatus
    assert "renderStatus(statusBox, [" in html, (
        "renderStatus() must be invoked for the claim-submitted success box (#7214)."
    )