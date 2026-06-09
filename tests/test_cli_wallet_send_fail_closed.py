from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI_MAIN = ROOT / "tools" / "cli-wallet" / "src" / "main.rs"
CLI_README = ROOT / "tools" / "cli-wallet" / "README.md"


def test_cli_wallet_send_does_not_mock_successful_transactions():
    source = CLI_MAIN.read_text(encoding="utf-8")

    assert 'println!("Note: Mock transaction' not in source
    assert "hex::encode(&signed_transaction.signature[0..8])" not in source
    assert "Transaction endpoint returned HTTP" in source
    assert "Transaction submission failed" in source
    assert "if !status.is_success()" in source


def test_cli_wallet_readme_does_not_claim_mock_send_success():
    readme = CLI_README.read_text(encoding="utf-8")

    assert "Simulated successful transactions" not in readme
    assert "Transaction submission fails closed" in readme
