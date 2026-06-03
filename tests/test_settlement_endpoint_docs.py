from pathlib import Path


def test_settlement_docs_use_rewards_epoch_route():
    readme = Path("docs/api/README.md").read_text(encoding="utf-8")
    examples = Path("docs/api/EXAMPLES.md").read_text(encoding="utf-8")
    openapi = Path("docs/api/openapi.yaml").read_text(encoding="utf-8")

    assert "/api/settlement/{epoch}" not in readme
    assert "/api/settlement/75" not in examples
    assert "/api/settlement/{epoch}:" not in openapi

    assert "/rewards/epoch/{epoch}" in readme
    assert "https://rustchain.org/rewards/epoch/75" in examples
    assert 'f"{self.base_url}/rewards/epoch/{epoch}"' in examples
    assert "this.request(`/rewards/epoch/${epoch}`);" in examples
    assert '"$BASE_URL/rewards/epoch/$epoch"' in examples
    assert "/rewards/epoch/{epoch}:" in openapi
