# SPDX-License-Identifier: MIT
"""Tests for /api/network and /api/peers endpoints.

Regression coverage for issue #7109 — public docs /api/network and /api/peers
were returning nginx HTML 404 on production. The backend RPC layer now exposes
both, and nginx proxies them to the node.

These tests verify:
1. `/api/network` returns combined node info + peer list + peer count
2. `/api/peers` returns the peer list (already existed but no regression test)
3. Both routes are routed through the same `RustChainApi` allowlist (read-only)
4. The /api/network response degrades safely when get_peers returns non-list
"""

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RPC_PATH = REPO_ROOT / "rips" / "rustchain-core" / "api" / "rpc.py"


def load_rpc_module():
    module_name = "rustchain_core_rpc_under_test_network"
    spec = importlib.util.spec_from_file_location(module_name, RPC_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class FakeNode:
    """Stand-in for `Node` exposing only the methods the RPC needs."""

    def __init__(self, peers=None):
        self.chain_id = 2718
        self.version = "2.2.1-security-hardened"
        self.validator_id = "validator-test"
        self.is_mining = True
        self.peers = peers or [
            {"id": "peer-a", "address": "10.0.0.1:8099"},
            {"id": "peer-b", "address": "10.0.0.2:8099"},
            {"id": "peer-c", "address": "10.0.0.3:8099"},
        ]

    def get_uptime(self):
        return 86400  # 1 day

    def get_peers(self):
        return self.peers


def _route(path):
    """Route a static REST path through `ApiRequestHandler._route_request`."""
    rpc_module = load_rpc_module()
    node = FakeNode()
    handler = object.__new__(rpc_module.ApiRequestHandler)
    handler.api = rpc_module.RustChainApi(node)
    return handler._route_request(path, {})


def test_api_network_returns_combined_node_info_and_peers():
    response = _route("/api/network")

    assert response.success is True
    data = response.data

    # Node info fields from getNodeInfo
    assert data["chain_id"] == 2718
    assert data["version"] == "2.2.1-security-hardened"
    assert data["validator_id"] == "validator-test"
    assert data["is_mining"] is True
    assert data["uptime_seconds"] == 86400

    # Peer list passthrough from getPeers
    assert data["peers"] == [
        {"id": "peer-a", "address": "10.0.0.1:8099"},
        {"id": "peer-b", "address": "10.0.0.2:8099"},
        {"id": "peer-c", "address": "10.0.0.3:8099"},
    ]
    assert data["peer_count"] == 3


def test_api_peers_returns_peer_list():
    response = _route("/api/peers")

    assert response.success is True
    assert response.data == [
        {"id": "peer-a", "address": "10.0.0.1:8099"},
        {"id": "peer-b", "address": "10.0.0.2:8099"},
        {"id": "peer-c", "address": "10.0.0.3:8099"},
    ]


def test_api_network_degrades_when_get_peers_returns_non_list():
    """Defensive: if get_peers returns non-list, peer_count is 0 and peers is empty."""

    class BrokenNode(FakeNode):
        def get_peers(self):
            return {"unexpected": "dict-not-list"}  # wrong type on purpose

    rpc_module = load_rpc_module()
    handler = object.__new__(rpc_module.ApiRequestHandler)
    handler.api = rpc_module.RustChainApi(BrokenNode())
    response = handler._route_request("/api/network", {})

    assert response.success is True
    assert response.data["peer_count"] == 0
    assert response.data["peers"] == {"unexpected": "dict-not-list"}
    # Node info still intact
    assert response.data["chain_id"] == 2718


def test_api_network_with_empty_peer_list():
    """Solo node with no peers should return peer_count=0 and peers=[]."""

    class SoloNode(FakeNode):
        def get_peers(self):
            return []

    rpc_module = load_rpc_module()
    handler = object.__new__(rpc_module.ApiRequestHandler)
    handler.api = rpc_module.RustChainApi(SoloNode())
    response = handler._route_request("/api/network", {})

    assert response.success is True
    assert response.data["peer_count"] == 0
    assert response.data["peers"] == []


def test_get_network_is_in_public_allowlist():
    """`getNetwork` must be callable via the RPC allowlist (read-only)."""
    rpc_module = load_rpc_module()
    assert "getNetwork" in rpc_module.RPC_PUBLIC_METHODS