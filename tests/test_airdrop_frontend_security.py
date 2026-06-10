from pathlib import Path


PAGE = Path(__file__).resolve().parents[1] / "airdrop" / "index.html"


def source() -> str:
    return PAGE.read_text(encoding="utf-8")


def test_airdrop_claim_page_uses_escape_helpers() -> None:
    html = source()

    assert "function escapeHtml(value)" in html
    assert "function safeNumber(value, fallback = 0)" in html
    assert "function shortWallet(value, head = 6, tail = 4)" in html


def test_airdrop_dynamic_claim_fields_are_escaped_before_inner_html() -> None:
    html = source()

    safe_patterns = [
        "${escapeHtml(mockUser.login)}",
        "${escapeHtml(safeNumber(mockUser.stars))}",
        "${escapeHtml(safeNumber(mockUser.prs))}",
        "${escapeHtml(safeNumber(mockUser.age_days))}",
        "${escapeHtml(shortWallet(address))}",
        "${escapeHtml(shortWallet(pubkey, 8, 6))}",
        "${escapeHtml(stars)} Scottcjn repos starred",
        "${escapeHtml(prs)} merged PRs",
        "${escapeHtml(githubAge)} days",
        "${escapeHtml(c.label)}",
        "<strong>Name:</strong> ${escapeHtml(nameInput)}",
        '<strong>Address:</strong> <code style="font-size:11px;">${escapeHtml(addr)}</code>',
        "<strong>Claim ID:</strong> ${escapeHtml(generateClaimId())}",
        "<strong>GitHub:</strong> ${escapeHtml(payload.github)}",
        "<strong>Wallet:</strong> ${escapeHtml(shortWallet(payload.wallet_address, 10, 0))}",
        "<strong>Allocation:</strong> ${escapeHtml(safeNumber(payload.allocation))} wRTC",
        "<strong>Tier:</strong> ${escapeHtml(payload.tier)}",
    ]

    for pattern in safe_patterns:
        assert pattern in html


def test_airdrop_old_raw_interpolations_are_absent() -> None:
    html = source()

    unsafe_patterns = [
        "${mockUser.login}",
        "${mockUser.stars} repos",
        "${mockUser.prs} merged",
        "${mockUser.age_days} days",
        "${address.slice(0,6)}...${address.slice(-4)}",
        "${pubkey.slice(0,8)}...${pubkey.slice(-6)}",
        "${gh.stars || 0} Scottcjn repos starred",
        "${gh.prs || 0} merged PRs",
        "GitHub account age: ${gh.age_days} days",
        "${c.label}</div>",
        "<strong>Name:</strong> ${nameInput}",
        '<strong>Address:</strong> <code style="font-size:11px;">${addr}</code>',
        "<strong>Claim ID:</strong> ${generateClaimId()}",
        "<strong>GitHub:</strong> ${payload.github}",
        "<strong>Wallet:</strong> ${payload.wallet_address?.slice(0,10)}...",
        "<strong>Allocation:</strong> ${payload.allocation} wRTC",
        "<strong>Tier:</strong> ${payload.tier}",
    ]

    for pattern in unsafe_patterns:
        assert pattern not in html
