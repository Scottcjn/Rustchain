# SPDX-License-Identifier: MIT

import importlib.util
import sys
import types
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "node" / "rustchain_blockchain_integration.py"


class DummyDatabase:
    def __init__(self, db_path):
        self.db_path = db_path


class DummyBadgeGenerator:
    pass


def load_module():
    db_pkg = types.ModuleType("db")
    schema_mod = types.ModuleType("db.rustchain_database_schema")
    schema_mod.RustChainDatabase = DummyDatabase
    badge_mod = types.ModuleType("rustchain_nft_badges")
    badge_mod.NFTBadgeGenerator = DummyBadgeGenerator

    sys.modules["db"] = db_pkg
    sys.modules["db.rustchain_database_schema"] = schema_mod
    sys.modules["rustchain_nft_badges"] = badge_mod

    spec = importlib.util.spec_from_file_location("blockchain_integration_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {"blocks": []}

    def json(self):
        return self._payload


def test_sync_with_blockchain_uses_bounded_request_timeout(monkeypatch):
    module = load_module()
    calls = []

    def fake_get(url, timeout):
        calls.append((url, timeout))
        return FakeResponse(payload={"blocks": []})

    monkeypatch.setattr(module.requests, "get", fake_get)
    integration = module.BlockchainIntegration(
        node_url="https://node.example",
        db_path=":memory:",
        request_timeout=3,
    )

    result = integration.sync_with_blockchain()

    assert result["errors"] == []
    assert calls == [("https://node.example/api/blocks", 3)]


def test_sync_with_blockchain_returns_controlled_error_for_http_failure(monkeypatch):
    module = load_module()
    monkeypatch.setattr(module.requests, "get", lambda url, timeout: FakeResponse(status_code=503))
    integration = module.BlockchainIntegration(node_url="https://node.example", db_path=":memory:")

    result = integration.sync_with_blockchain()

    assert result["blocks_processed"] == 0
    assert result["errors"] == ["Sync error: node returned HTTP 503"]


@pytest.mark.parametrize("timeout", [0, -1, False, "10"])
def test_blockchain_integration_rejects_invalid_request_timeout(timeout):
    module = load_module()

    with pytest.raises(ValueError, match="request_timeout must be a positive number"):
        module.BlockchainIntegration(
            node_url="https://node.example",
            db_path=":memory:",
            request_timeout=timeout,
        )
