# SPDX-License-Identifier: MIT

import importlib
from pathlib import Path
from types import SimpleNamespace


CPU_INFO = {
    "arch": "arm64",
    "arch_type": "apple_silicon",
    "cpu_count": 8,
    "antiquity_multiplier": 1.0,
    "optimal_threads": 8,
}


def load_cli_module(monkeypatch, tmp_path):
    package_root = Path(__file__).resolve().parents[1] / "rustchainnode"
    monkeypatch.syspath_prepend(str(package_root))

    module = importlib.import_module("rustchainnode.cli")
    module = importlib.reload(module)
    monkeypatch.setattr(module, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(module, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(module, "PID_FILE", tmp_path / "node.pid")
    monkeypatch.setattr(module, "detect_cpu_info", lambda: CPU_INFO)
    return module


def record_probe_urls(monkeypatch, module):
    calls = []

    def fake_health(node_url=module.NODE_URL):
        calls.append(("health", node_url))
        return {"ok": True, "version": "test"}

    def fake_epoch(node_url=module.NODE_URL):
        calls.append(("epoch", node_url))
        return {"epoch": 1, "slot": 2}

    monkeypatch.setattr(module, "_check_health", fake_health)
    monkeypatch.setattr(module, "_check_epoch", fake_epoch)
    return calls


def test_init_persists_testnet_node_url(monkeypatch, tmp_path, capsys):
    module = load_cli_module(monkeypatch, tmp_path)
    monkeypatch.setattr(
        module,
        "get_optimal_config",
        lambda wallet, port: {
            "wallet": wallet,
            "port": port,
            "node_url": module.NODE_URL,
        },
    )
    calls = record_probe_urls(monkeypatch, module)

    module.cmd_init(SimpleNamespace(wallet="wallet-1", port=9000, testnet=True))
    capsys.readouterr()

    cfg = module._load_config()
    assert cfg["testnet"] is True
    assert cfg["node_url"] == module.TESTNET_NODE_URL
    assert calls == [("health", module.TESTNET_NODE_URL)]


def test_start_uses_persisted_testnet_config(monkeypatch, tmp_path, capsys):
    module = load_cli_module(monkeypatch, tmp_path)
    module._save_config(
        {
            "wallet": "wallet-1",
            "port": 8099,
            "testnet": True,
            "node_url": module.NODE_URL,
        }
    )
    calls = record_probe_urls(monkeypatch, module)

    module.cmd_start(SimpleNamespace(wallet=None, port=None, testnet=False))
    capsys.readouterr()

    assert calls == [
        ("health", module.TESTNET_NODE_URL),
        ("epoch", module.TESTNET_NODE_URL),
    ]


def test_status_and_dashboard_use_persisted_testnet_config(monkeypatch, tmp_path, capsys):
    module = load_cli_module(monkeypatch, tmp_path)
    module._save_config(
        {
            "wallet": "wallet-1",
            "port": 8099,
            "testnet": True,
            "node_url": module.NODE_URL,
        }
    )

    status_calls = record_probe_urls(monkeypatch, module)
    module.cmd_status(SimpleNamespace())
    capsys.readouterr()
    assert status_calls == [
        ("health", module.TESTNET_NODE_URL),
        ("epoch", module.TESTNET_NODE_URL),
    ]

    dashboard_calls = record_probe_urls(monkeypatch, module)
    module.cmd_dashboard(SimpleNamespace())
    capsys.readouterr()
    assert dashboard_calls == [
        ("health", module.TESTNET_NODE_URL),
        ("epoch", module.TESTNET_NODE_URL),
    ]


def test_status_keeps_custom_production_node_url(monkeypatch, tmp_path, capsys):
    module = load_cli_module(monkeypatch, tmp_path)
    module._save_config(
        {
            "wallet": "wallet-1",
            "port": 8099,
            "testnet": False,
            "node_url": "https://node.example",
        }
    )
    calls = record_probe_urls(monkeypatch, module)

    module.cmd_status(SimpleNamespace())
    capsys.readouterr()

    assert calls == [
        ("health", "https://node.example"),
        ("epoch", "https://node.example"),
    ]
