import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "docs" / "postman" / "README.md"
COLLECTION = ROOT / "docs" / "postman" / "RustChain_API.postman_collection.json"


def test_postman_balance_docs_use_wallet_balance_endpoint():
    readme = README.read_text(encoding="utf-8")
    collection = json.loads(COLLECTION.read_text(encoding="utf-8"))
    collection_text = json.dumps(collection, sort_keys=True)

    assert "/wallet/balance?miner_id=X" in readme
    assert "{{base_url}}/wallet/balance?miner_id={{miner_id}}" in collection_text
    assert '"path": ["wallet", "balance"]' in COLLECTION.read_text(encoding="utf-8")
    assert "amount_rtc" in collection_text

    stale_patterns = [
        "`/balance?miner_id=X`",
        "{{base_url}}/balance?miner_id={{miner_id}}",
        '"path": ["balance"]',
        '"balance": 150.5',
    ]
    combined = readme + "\n" + COLLECTION.read_text(encoding="utf-8")
    for pattern in stale_patterns:
        assert pattern not in combined
