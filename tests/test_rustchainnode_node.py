import importlib.util
import json
import urllib.request
from pathlib import Path


def load_node_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "rustchainnode"
        / "rustchainnode"
        / "node.py"
    )
    spec = importlib.util.spec_from_file_location("rustchainnode_node", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def test_init_uses_testnet_local_node_url(tmp_path):
    module = load_node_module()

    node = module.RustChainNode(
        wallet="wallet-1",
        port=9000,
        config_dir=tmp_path,
        testnet=True,
        node_url="https://node.example",
    )

    assert node.wallet == "wallet-1"
    assert node.port == 9000
    assert node.config_dir == tmp_path
    assert node.node_url == "http://localhost:8099"
    assert node.is_running() is False


def test_start_and_stop_update_running_state(tmp_path):
    module = load_node_module()
    node = module.RustChainNode(wallet="wallet-1", config_dir=tmp_path)

    node.start()
    node.start()
    assert node.is_running() is True

    node.stop()
    assert node.is_running() is False


def test_config_reads_config_json_when_present(tmp_path):
    module = load_node_module()
    config = {"wallet": "wallet-1", "port": 9001}
    (tmp_path / "config.json").write_text(json.dumps(config))
    node = module.RustChainNode(wallet="wallet-1", config_dir=tmp_path)

    assert node.config() == config


def test_config_returns_empty_dict_when_missing(tmp_path):
    module = load_node_module()
    node = module.RustChainNode(wallet="wallet-1", config_dir=tmp_path)

    assert node.config() == {}


def test_health_and_epoch_return_json_from_node_url(monkeypatch, tmp_path):
    module = load_node_module()
    calls = []

    def fake_urlopen(url, timeout):
        calls.append((url, timeout))
        payloads = {
            "https://node.example/health": {"ok": True},
            "https://node.example/epoch": {"epoch": 12},
        }
        return FakeResponse(payloads[url])

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    node = module.RustChainNode(
        wallet="wallet-1",
        config_dir=tmp_path,
        node_url="https://node.example",
    )

    assert node.health() == {"ok": True}
    assert node.epoch() == {"epoch": 12}
    assert calls == [
        ("https://node.example/health", 5),
        ("https://node.example/epoch", 5),
    ]


def test_health_reports_urlopen_errors(monkeypatch, tmp_path):
    module = load_node_module()

    def raise_error(url, timeout):
        raise OSError("offline")

    monkeypatch.setattr(urllib.request, "urlopen", raise_error)
    node = module.RustChainNode(wallet="wallet-1", config_dir=tmp_path)

    assert node.health() == {"ok": False, "error": "offline"}
