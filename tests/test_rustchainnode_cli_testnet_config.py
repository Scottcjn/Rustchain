import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace


def load_cli_module():
    package_root = Path(__file__).resolve().parents[1] / "rustchainnode"
    sys.path.insert(0, str(package_root))
    sys.modules.pop("rustchainnode.cli", None)
    return importlib.import_module("rustchainnode.cli")


def test_start_uses_persisted_testnet_config(monkeypatch, tmp_path):
    module = load_cli_module()
    monkeypatch.setattr(module, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(module, "CONFIG_DIR", tmp_path)
    module.CONFIG_FILE.write_text(json.dumps({"wallet": "wallet-1", "port": 8099, "testnet": True}))

    health_urls = []
    epoch_urls = []
    monkeypatch.setattr(module, "detect_cpu_info", lambda: {
        "arch": "x86_64",
        "cpu_count": 4,
        "antiquity_multiplier": 1.0,
    })
    monkeypatch.setattr(module, "_check_health", lambda node_url: health_urls.append(node_url) or {"ok": True})
    monkeypatch.setattr(module, "_check_epoch", lambda node_url: epoch_urls.append(node_url) or {"epoch": 1})

    module.cmd_start(SimpleNamespace(wallet=None, port=None, testnet=False))

    assert health_urls == [module.TESTNET_NODE_URL]
    assert epoch_urls == [module.TESTNET_NODE_URL]


def test_status_and_dashboard_use_persisted_testnet_config(monkeypatch, tmp_path):
    module = load_cli_module()
    monkeypatch.setattr(module, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(module, "CONFIG_DIR", tmp_path)
    module.CONFIG_FILE.write_text(json.dumps({"wallet": "wallet-1", "port": 8099, "testnet": True}))

    health_urls = []
    epoch_urls = []
    monkeypatch.setattr(module, "detect_cpu_info", lambda: {
        "arch": "x86_64",
        "arch_type": "modern",
        "cpu_count": 4,
        "antiquity_multiplier": 1.0,
    })
    monkeypatch.setattr(module, "_check_health", lambda node_url: health_urls.append(node_url) or {"ok": True})
    monkeypatch.setattr(module, "_check_epoch", lambda node_url: epoch_urls.append(node_url) or {"epoch": 1})

    module.cmd_status(SimpleNamespace())
    module.cmd_dashboard(SimpleNamespace())

    assert health_urls == [module.TESTNET_NODE_URL, module.TESTNET_NODE_URL]
    assert epoch_urls == [module.TESTNET_NODE_URL, module.TESTNET_NODE_URL]
