from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_developer_tutorial_uses_current_miners_response_shape():
    text = (ROOT / "docs" / "RUSTCHAIN_DEVELOPER_TUTORIAL.md").read_text(encoding="utf-8")

    assert "jq '.miners[] | select(.miner | contains(\"YOUR_WALLET_NAME\"))'" in text
    assert "'.miners[] | select(.miner == \"my-vintage-miner\")'" in text
    assert "jq '.miners | length'" in text
    assert ".miners[] | select(.miner == \\\"$WALLET\\\") | .miner" in text
    assert "jq '.miners[] | select(.miner == \"YOUR_WALLET\")'" in text
    assert '.json().get("miners", [])' in text

    assert "jq '.[] | select(.miner_id" not in text
    assert "jq 'length'" not in text
    assert 'len(requests.get(f"{NODE}/api/miners", verify=False).json())' not in text
