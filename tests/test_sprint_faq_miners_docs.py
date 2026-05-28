from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_sprint_faq_uses_live_miners_endpoint_for_multiplier():
    text = (ROOT / "docs" / "sprint" / "faq-troubleshooting.md").read_text(encoding="utf-8")

    assert "https://rustchain.org/api/miners" in text
    assert 'jq \'.miners[] | select(.miner == "YOUR_WALLET") | .antiquity_multiplier\'' in text
    assert "https://rustchain.org/api/miner-info" not in text
    assert "jq .multiplier" not in text
