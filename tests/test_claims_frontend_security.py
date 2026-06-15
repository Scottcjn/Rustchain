from pathlib import Path


CLAIMS_JS = Path(__file__).resolve().parents[1] / "web" / "claims" / "claims.js"


def source():
    return CLAIMS_JS.read_text(encoding="utf-8")


def test_claims_page_renders_dynamic_ui_with_dom_text_nodes():
    script = source()

    safe_patterns = [
        "function textEl(tag, className, text)",
        "el.textContent = text;",
        "function summaryRow(label, value, options = {})",
        "function checkItem(label, passed)",
        "function resetEpochOptions(label = '-- Select an epoch --')",
        "function renderSubmitSuccess(result)",
        "eligibilityResult.replaceChildren(...nodes);",
        "epochSelect.replaceChildren(...options);",
        "claimSummary.replaceChildren(",
        "tbody.replaceChildren(...history.claims.map(claim => {",
        "box.replaceChildren(",
        "new Option(`Epoch ${epochNumber} - ${formatRtc(epoch.reward_urtc)} RTC`, String(epochNumber))",
        "option.dataset.reward = String(safeInteger(epoch.reward_urtc));",
        "code.style.fontFamily = 'var(--font-mono)';",
    ]

    for pattern in safe_patterns:
        assert pattern in script


def test_claims_page_has_no_dynamic_inner_html_templates():
    script = source()

    assert ".innerHTML" not in script
    assert "insertAdjacentHTML" not in script
    assert "escapeHtml" not in script

    unsafe_patterns = [
        "${eligibility.miner_id}",
        "${eligibility.attestation?.device_arch || 'N/A'}",
        "${eligibility.wallet_address || 'Not registered'}",
        "Reason: ${eligibility.reason || 'Unknown'}",
        'value="${epoch.epoch}"',
        'data-reward="${epoch.reward_urtc}"',
        "${minerId}</span>",
        "${walletAddress}</span>",
        "${claim.claim_id}",
        'class="status-badge ${claim.status}"',
        "${claim.status}</span>",
        "${result.claim_id}</code>",
    ]

    for pattern in unsafe_patterns:
        assert pattern not in script


def test_claims_page_keeps_normalization_helpers_for_numbers_and_classes():
    script = source()

    assert "function safeCssClass(value)" in script
    assert "function safeNumber(value, fallback = 0)" in script
    assert "function safeInteger(value, fallback = 0)" in script
    assert "safeNumber(eligibility.attestation?.antiquity_multiplier, 1).toFixed(2)" in script
    assert "textEl('span', `status-badge ${safeCssClass(claim.status)}`, claim.status)" in script
