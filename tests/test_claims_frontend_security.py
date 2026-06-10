from pathlib import Path


def test_claims_page_uses_dom_text_apis_instead_of_html_templates():
    claims_js = Path(__file__).resolve().parents[1] / "web" / "claims" / "claims.js"
    script = claims_js.read_text(encoding="utf-8")

    forbidden_sinks = [
        "innerHTML",
        "insertAdjacentHTML",
        "outerHTML",
        "function escapeHtml",
    ]

    for sink in forbidden_sinks:
        assert sink not in script

    required_dom_patterns = [
        "function createNode(tagName, options = {})",
        "node.textContent = String(options.text ?? '')",
        "parent.appendChild(document.createTextNode(String(value ?? '')))",
        "eligibilityResult.replaceChildren();",
        "epochSelect.replaceChildren(new Option(label, ''));",
        "claimSummary.replaceChildren();",
        "tbody.replaceChildren();",
        "submitSuccess.replaceChildren();",
        "new Option(`Epoch ${epochNumber} - ${formatRtc(rewardUrtc)} RTC`, String(epochNumber))",
        "option.dataset.reward = String(rewardUrtc)",
        "appendNode(submitSuccess, 'code', { text: result.claim_id })",
        "className: `status-badge ${safeCssClass(claim.status)}`",
    ]

    for pattern in required_dom_patterns:
        assert pattern in script
