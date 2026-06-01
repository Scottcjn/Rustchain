from pathlib import Path


DOC = Path(__file__).resolve().parents[1] / "docs" / "RUSTCHAIN_DEVELOPER_TUTORIAL.md"


def test_developer_tutorial_uses_current_transaction_endpoints():
    text = DOC.read_text(encoding="utf-8")

    assert "/wallet/transfer/signed" in text
    assert "/wallet/history?miner_id=" in text
    assert "from_address" in text
    assert "to_address" in text
    assert "amount_rtc" in text
    assert "amount_i64" in text

    stale_endpoints = [
        "https://rustchain.org/api/transaction",
        "/api/transaction",
        "/api/wallet/my-vintage-miner/transactions",
        "/api/wallet/ID/transactions",
        "jq -r '.balance'",
        "balance.get('balance'",
        "if .balance < 10",
    ]
    for endpoint in stale_endpoints:
        assert endpoint not in text
