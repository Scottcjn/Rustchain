from pathlib import Path


def test_claims_page_renders_api_and_user_fields_without_inner_html():
    claims_js = Path(__file__).resolve().parents[1] / "web" / "claims" / "claims.js"
    script = claims_js.read_text(encoding="utf-8")

    assert "function createElement(tagName, options = {}, children = [])" in script
    assert "function createOption(label, value = '', dataset = {})" in script
    assert "function createSummaryRow(label, value, options = {})" in script
    assert "function createCheckItem(label, passed)" in script
    assert "function renderSubmitSuccess(result)" in script

    assert "eligibilityResult.replaceChildren(status, ...detailNodes, checks);" in script
    assert "epochSelect.replaceChildren(" in script
    assert "claimSummary.replaceChildren(" in script
    assert "tbody.replaceChildren(...history.claims.map(claim => {" in script
    assert "submitSuccess.replaceChildren(" in script

    unsafe_patterns = [
        "innerHTML",
        "${eligibility.miner_id}",
        "${eligibility.attestation?.device_arch || 'N/A'}",
        "${eligibility.wallet_address || 'Not registered'}",
        "Reason: ${eligibility.reason || 'Unknown'}",
        "${formatCheckName(check)}",
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
