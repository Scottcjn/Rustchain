from pathlib import Path


def test_claims_page_escapes_api_and_user_fields_before_inner_html():
    claims_js = Path(__file__).resolve().parents[1] / "web" / "claims" / "claims.js"
    script = claims_js.read_text(encoding="utf-8")

    assert "function escapeHtml(value)" in script
    assert "function safeCssClass(value)" in script
    assert "function safeNumber(value, fallback = 0)" in script
    assert "function safeInteger(value, fallback = 0)" in script

    safe_patterns = [
        "${escapeHtml(eligibility.miner_id)}",
        "${escapeHtml(eligibility.attestation?.device_arch || 'N/A')}",
        "${escapeHtml(eligibility.wallet_address || 'Not registered')}",
        "Reason: ${escapeHtml(eligibility.reason || 'Unknown')}",
        "${escapeHtml(formatCheckName(check))}",
        'value="${safeInteger(epoch.epoch)}"',
        'data-reward="${safeInteger(epoch.reward_urtc)}"',
        "${escapeHtml(minerId)}",
        "${escapeHtml(walletAddress)}",
        "${escapeHtml(claim.claim_id)}",
        'class="status-badge ${safeCssClass(claim.status)}"',
        "${escapeHtml(claim.status)}",
        "${escapeHtml(result.claim_id)}",
    ]

    for pattern in safe_patterns:
        assert pattern in script

    unsafe_patterns = [
        "${eligibility.miner_id}",
        "${eligibility.attestation?.device_arch || 'N/A'}",
        "${eligibility.wallet_address || 'Not registered'}",
        "Reason: ${eligibility.reason || 'Unknown'}",
        "${check.replace(/_/g, ' ').replace(/\\b\\w/g, l => l.toUpperCase())}",
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
