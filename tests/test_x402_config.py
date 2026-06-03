import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "node" / "x402_config.py"


def load_x402_config(monkeypatch, key_name="", private_key=""):
    monkeypatch.setenv("CDP_API_KEY_NAME", key_name)
    monkeypatch.setenv("CDP_API_KEY_PRIVATE_KEY", private_key)
    module_name = f"x402_config_under_test_{key_name or 'empty'}_{private_key or 'empty'}"
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_is_free_only_treats_empty_or_zero_prices_as_free(monkeypatch):
    module = load_x402_config(monkeypatch)

    assert module.is_free("0") is True
    assert module.is_free("") is True
    assert module.is_free("100000") is False
    assert module.is_free("0.00") is False


def test_has_cdp_credentials_requires_both_values_at_import(monkeypatch):
    missing_private_key = load_x402_config(monkeypatch, key_name="key-name")
    assert missing_private_key.has_cdp_credentials() is False

    missing_key_name = load_x402_config(monkeypatch, private_key="private-key")
    assert missing_key_name.has_cdp_credentials() is False

    configured = load_x402_config(
        monkeypatch,
        key_name="key-name",
        private_key="private-key",
    )
    assert configured.has_cdp_credentials() is True


def test_create_agentkit_wallet_rejects_missing_credentials(monkeypatch):
    module = load_x402_config(monkeypatch)

    with pytest.raises(RuntimeError, match="CDP credentials not configured"):
        module.create_agentkit_wallet()


def test_create_agentkit_wallet_returns_default_address_and_export(monkeypatch):
    module = load_x402_config(
        monkeypatch,
        key_name="key-name",
        private_key="private-key",
    )
    captured = {}

    class FakeAgentKitConfig:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    class FakeWallet:
        default_address = SimpleNamespace(address_id="0xabc123")

        def export_data(self):
            return {"wallet_id": "wallet-1"}

    class FakeAgentKit:
        def __init__(self, config):
            self.config = config
            self.wallet = FakeWallet()

    fake_coinbase_agentkit = SimpleNamespace(
        AgentKit=FakeAgentKit,
        AgentKitConfig=FakeAgentKitConfig,
    )
    monkeypatch.setitem(sys.modules, "coinbase_agentkit", fake_coinbase_agentkit)

    address, wallet_data = module.create_agentkit_wallet()

    assert address == "0xabc123"
    assert wallet_data == {"wallet_id": "wallet-1"}
    assert captured == {
        "cdp_api_key_name": "key-name",
        "cdp_api_key_private_key": "private-key",
        "network_id": "base-mainnet",
    }
