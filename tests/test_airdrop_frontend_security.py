# SPDX-License-Identifier: MIT
from pathlib import Path


HTML = Path(__file__).resolve().parents[1] / "airdrop" / "index.html"


def source():
    return HTML.read_text(encoding="utf-8")


def test_airdrop_page_defines_escape_and_normalization_helpers():
    html = source()

    assert "function escapeHtml(value)" in html
    assert "function safeNumber(value, fallback = 0)" in html
    assert "function safeInteger(value, fallback = 0)" in html
    assert "function shortWallet(value, start = 8, end = 6)" in html
    assert "if (end === 0) return `${text.slice(0, start)}...`;" in html


def test_airdrop_github_and_wallet_status_escape_dynamic_fields():
    html = source()

    assert "Connected as <strong>${escapeHtml(mockUser.login)}</strong>" in html
    assert "Stars: ${safeInteger(mockUser.stars)} repos" in html
    assert "PRs: ${safeInteger(mockUser.prs)} merged" in html
    assert "Account age: ${safeInteger(mockUser.age_days)} days" in html
    assert "${escapeHtml(shortWallet(address, 6, 4))} · ${balanceETH.toFixed(4)} ETH" in html
    assert "${escapeHtml(shortWallet(pubkey, 8, 6))} · ${balanceSOL.toFixed(4)} SOL" in html

    assert "Connected as <strong>${mockUser.login}</strong>" not in html
    assert "${address.slice(0,6)}...${address.slice(-4)}" not in html
    assert "${pubkey.slice(0,8)}...${pubkey.slice(-6)}" not in html


def test_airdrop_eligibility_rows_escape_labels_and_coerce_numbers():
    html = source()

    assert "const ghStars = safeInteger(gh.stars);" in html
    assert "const ghPrs = safeInteger(gh.prs);" in html
    assert "const ghAgeDays = safeInteger(gh.age_days);" in html
    assert "${ghStars} Scottcjn repos starred" in html
    assert "${ghPrs} merged PRs" in html
    assert "GitHub account age: ${ghAgeDays} days" in html
    assert "${escapeHtml(c.label)}</div>" in html

    assert "${gh.stars || 0} Scottcjn repos starred" not in html
    assert "${gh.prs || 0} merged PRs" not in html
    assert "GitHub account age: ${gh.age_days} days" not in html
    assert "${c.label}</div>" not in html


def test_airdrop_rtc_wallet_and_claim_summary_escape_fields():
    html = source()

    assert "<strong>Name:</strong> ${escapeHtml(nameInput)}<br>" in html
    assert '<strong>Address:</strong> <code style="font-size:11px;">${escapeHtml(addr)}</code>' in html
    assert "<strong>Claim ID:</strong> ${escapeHtml(generateClaimId())}<br>" in html
    assert "<strong>GitHub:</strong> ${escapeHtml(payload.github || '')}<br>" in html
    assert "<strong>Wallet:</strong> ${escapeHtml(shortWallet(payload.wallet_address, 10, 0))}<br>" in html
    assert "<strong>Allocation:</strong> ${safeInteger(payload.allocation)} wRTC<br>" in html
    assert "<strong>Tier:</strong> ${escapeHtml(payload.tier || '')}<br><br>" in html

    assert "<strong>Name:</strong> ${nameInput}<br>" not in html
    assert '<strong>Address:</strong> <code style="font-size:11px;">${addr}</code>' not in html
    assert "<strong>GitHub:</strong> ${payload.github}<br>" not in html
    assert "<strong>Allocation:</strong> ${payload.allocation} wRTC<br>" not in html
    assert "<strong>Tier:</strong> ${payload.tier}<br><br>" not in html
