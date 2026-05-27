from pathlib import Path


def test_settlement_reference_docs_use_rewards_epoch_endpoint():
    repo_root = Path(__file__).resolve().parents[1]
    files = [
        repo_root / "docs" / "api-reference.md",
        repo_root / "docs" / "epoch-settlement.md",
    ]

    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "/api/settlement/{epoch}" not in text
        assert "/api/settlement/75" not in text
        assert "/rewards/epoch/{epoch}" in text
        assert "/rewards/epoch/75" in text
