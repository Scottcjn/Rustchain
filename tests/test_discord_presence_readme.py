from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_discord_presence_readme_uses_current_miners_response_shape():
    text = (ROOT / "discord_presence_README.md").read_text(encoding="utf-8")

    assert "jq -r '.miners[].miner'" in text
    assert "jq '.miners[] | select(.miner==\"YOUR_MINER_ID\")'" in text
    assert "jq '.[].miner'" not in text
    assert "jq '.[] | select(.miner==\"YOUR_MINER_ID\")'" not in text
