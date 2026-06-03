import importlib.util
import sys
import types
from pathlib import Path


def load_verifier():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "integrations"
        / "solana-spl"
        / "verify.py"
    )
    sys.modules.pop("spl_deployment", None)
    sys.modules["solders"] = types.ModuleType("solders")
    pubkey_module = types.ModuleType("solders.pubkey")

    class FakePubkey:
        @classmethod
        def from_string(cls, value):
            return f"pubkey:{value}"

    pubkey_module.Pubkey = FakePubkey
    sys.modules["solders.pubkey"] = pubkey_module

    spec = importlib.util.spec_from_file_location("solana_spl_verify", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_get_rpc_url_returns_known_networks_and_devnet_fallback():
    module = load_verifier()

    assert module.get_rpc_url("devnet") == "https://api.devnet.solana.com"
    assert module.get_rpc_url("testnet") == "https://api.testnet.solana.com"
    assert module.get_rpc_url("mainnet") == "https://api.mainnet-beta.solana.com"
    assert module.get_rpc_url("localnet") == "http://localhost:8899"
    assert module.get_rpc_url("unknown") == "https://api.devnet.solana.com"


def test_print_report_outputs_nested_check_results(capsys):
    module = load_verifier()
    verification = {
        "status": "success",
        "mint_address": "mint-123",
        "network": "devnet",
        "checks": {
            "mint": {"initialized": True, "frozen": False},
            "supply": 1000,
        },
        "expected_config_hash": "hash-abc",
    }

    module.print_report(verification, verbose=True)

    output = capsys.readouterr().out
    assert "Status: success" in output
    assert "Mint Address: mint-123" in output
    assert "Network: devnet" in output
    assert "initialized: True" in output
    assert "frozen: False" in output
    assert "supply: 1000" in output
    assert "Expected config hash: hash-abc" in output


def test_verify_deployment_sets_mint_and_adds_timestamp(monkeypatch, tmp_path):
    module = load_verifier()
    calls = {}

    class FakeDeployment:
        def __init__(self, rpc_url):
            calls["rpc_url"] = rpc_url
            self.mint_address = None

        def verify_deployment(self):
            calls["mint_address"] = self.mint_address
            return {"status": "success", "checks": {}}

    monkeypatch.setattr(module, "SPLTokenDeployment", FakeDeployment)
    monkeypatch.setattr(module, "load_config_from_file", lambda path: {"config": path})
    monkeypatch.setattr(module, "hash_config", lambda config: f"hash:{config['config']}")
    config_path = tmp_path / "config.json"
    config_path.write_text("{}")

    verification = module.verify_deployment(
        "mint-abc",
        "https://rpc.example",
        str(config_path),
    )

    assert calls == {
        "rpc_url": "https://rpc.example",
        "mint_address": "pubkey:mint-abc",
    }
    assert verification["status"] == "success"
    assert verification["expected_config_hash"] == f"hash:{config_path}"
    assert "verification_timestamp" in verification


def test_parse_args_uses_defaults(monkeypatch):
    module = load_verifier()
    monkeypatch.setattr(sys, "argv", ["verify.py", "--mint-address", "mint-abc"])

    args = module.parse_args()

    assert args.mint_address == "mint-abc"
    assert args.network == "devnet"
    assert args.config is None
    assert args.output == "verification-report.json"
    assert args.verbose is False
