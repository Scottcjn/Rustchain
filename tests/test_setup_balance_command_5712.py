from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETUP_SH = ROOT / "setup.sh"


def test_setup_summary_points_to_wallet_balance_endpoint():
    script = SETUP_SH.read_text(encoding="utf-8")

    assert "curl -sk '$NODE_URL/wallet/$WALLET_NAME' | python3 -m json.tool" not in script
    assert "curl -sk '$NODE_URL/wallet/balance?miner_id=$WALLET_NAME' | python3 -m json.tool" in script
