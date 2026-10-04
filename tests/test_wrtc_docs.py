"""
RTC "one way in, no way out" documentation guard.

RTC is earned for contributions (or bought as credits on BoTTube) and spent
on services in the ecosystem. The wRTC bridge is disabled and there is no
off-ramp. Official, user-facing documentation must therefore stay silent on
exchanges, DEXs, liquidity pools, swaps, and third-party price trackers.

This suite replaces the earlier wRTC quickstart tests, which required the
docs to link to Raydium and DexScreener.

Run with: python -m pytest tests/test_wrtc_docs.py -v
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
EARN_AND_SPEND_URL = (
    "https://github.com/Scottcjn/rustchain-bounties/blob/main/docs/EARN_AND_SPEND.md"
)
BRIDGE_DISABLED = "The wRTC bridge is disabled."

# User-facing documents that must not point readers at trading venues or
# market-data trackers. Historical records (RIPs, bounty implementation
# write-ups, audit reports) are intentionally not listed here.
GUARDED_DOCS = [
    "README.md",
    "README_DE.md",
    "README_ES.md",
    "README_HI.md",
    "README_JA.md",
    "README_RU.md",
    "README_ZH.md",
    "README_ZH-TW.md",
    "README.vi.md",
    "README.zh-CN.md",
    "CONTRIBUTING.md",
    "docs/wrtc.md",
    "docs/WRTC_ONBOARDING_TUTORIAL.md",
    "docs/token-economics.md",
    "docs/zh-CN/TOKEN_ECONOMICS.md",
    "docs/QUICKSTART.md",
    "docs/zh-CN/QUICKSTART.md",
    "docs/FAQ.md",
    "docs/FAQ_TROUBLESHOOTING.md",
    "docs/sprint/faq-troubleshooting.md",
    "docs/protocol-overview.md",
    "docs/zh-CN/PROTOCOL_OVERVIEW.md",
    "docs/RUSTCHAIN_PROTOCOL.md",
    "docs/RUSTCHAIN_DEVELOPER_TUTORIAL.md",
    "docs/US_REGULATORY_POSITION.md",
    "docs/WHITEPAPER.md",
    "docs/zh-CN/README.md",
    "docs/es/README.md",
    "docs/api-reference.md",
    "docs/API_REFERENCE.md",
    "docs/zh-CN/API_REFERENCE.md",
    "docs/api/README.md",
    "docs/api/openapi.yaml",
    "docs/tokenomics.html",
    "docs/mining.html",
    "website/static/tokenomics.html",
    "website/static/mining.html",
    "web/wallets.html",
]

FORBIDDEN_PATTERNS = [
    r"raydium",
    r"dexscreener",
    r"birdeye",
    r"geckoterminal",
    r"aerodrome",
    r"liquidity pool",
    r"exchange listing",
    r"/wallet/swap-info",
    r"price discovery",
]


@pytest.mark.parametrize("relpath", GUARDED_DOCS)
def test_guarded_doc_exists(relpath):
    assert (REPO_ROOT / relpath).is_file(), f"guarded doc missing: {relpath}"


@pytest.mark.parametrize("relpath", GUARDED_DOCS)
def test_guarded_doc_has_no_trading_references(relpath):
    content = (REPO_ROOT / relpath).read_text(encoding="utf-8").lower()
    hits = [p for p in FORBIDDEN_PATTERNS if re.search(p, content)]
    assert not hits, f"{relpath} references trading/market venues: {hits}"


def test_wrtc_doc_is_a_disabled_notice():
    content = (REPO_ROOT / "docs" / "wrtc.md").read_text(encoding="utf-8")
    assert content.startswith("# ")
    assert BRIDGE_DISABLED in content
    assert "no off-ramp" in content
    assert EARN_AND_SPEND_URL in content


def test_onboarding_tutorial_is_a_disabled_notice():
    content = (REPO_ROOT / "docs" / "WRTC_ONBOARDING_TUTORIAL.md").read_text(
        encoding="utf-8"
    )
    assert BRIDGE_DISABLED in content
    assert EARN_AND_SPEND_URL in content


def test_readme_states_bridge_disabled_and_links_earn_and_spend():
    content = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert BRIDGE_DISABLED in content
    assert EARN_AND_SPEND_URL in content
    assert "internal accounting unit" in content


@pytest.mark.parametrize(
    "relpath", ["tools/wrtc-price-bot/README.md", "wrtc_price_bot/README.md"]
)
def test_price_bots_are_marked_deprecated(relpath):
    content = (REPO_ROOT / relpath).read_text(encoding="utf-8")
    assert "Deprecated" in content
    assert BRIDGE_DISABLED in content
