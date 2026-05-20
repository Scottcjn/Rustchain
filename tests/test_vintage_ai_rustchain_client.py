"""Tests for the vintage AI video RustChain client."""

import importlib.util
from pathlib import Path


def load_client_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "vintage_ai_video_pipeline" / "rustchain_client.py"
    spec = importlib.util.spec_from_file_location("vintage_rustchain_client", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_get_miners_accepts_envelope_payloads(monkeypatch):
    module = load_client_module()
    client = module.RustChainClient(base_url="https://node.example")

    monkeypatch.setattr(
        client,
        "_get",
        lambda endpoint: {
            "items": [
                {"miner": "alice", "hardware_type": "PowerPC G4"},
                {"miner": "bob", "hardware_type": "x86-64"},
            ],
            "pagination": {"total": 2},
        },
    )

    assert client.get_miners() == [
        {"miner": "alice", "hardware_type": "PowerPC G4"},
        {"miner": "bob", "hardware_type": "x86-64"},
    ]


def test_get_miners_returns_empty_list_for_unexpected_payload(monkeypatch):
    module = load_client_module()
    client = module.RustChainClient(base_url="https://node.example")

    monkeypatch.setattr(client, "_get", lambda endpoint: {"pagination": {"total": 0}})

    assert client.get_miners() == []
