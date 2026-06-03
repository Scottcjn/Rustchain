#!/usr/bin/env python3
"""Regression tests for P2P read endpoint authentication."""

import importlib
import os
import sys
from pathlib import Path
from types import SimpleNamespace

from flask import Flask


P2P_SECRET = "unit-test-secret-0123456789abcdef"
os.environ["RC_P2P_SECRET"] = P2P_SECRET

NODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(NODE_DIR))

if "rustchain_p2p_gossip" in sys.modules:
    del sys.modules["rustchain_p2p_gossip"]
gossip = importlib.import_module("rustchain_p2p_gossip")


def _make_client():
    app = Flask(__name__)
    p2p_node = SimpleNamespace(
        node_id="node-a",
        peers={"node-b": "https://node-b.example"},
        running=True,
        gossip=SimpleNamespace(
            attestation_crdt=SimpleNamespace(data={"miner-a": (1, {"device_arch": "x86"})}),
            epoch_crdt=SimpleNamespace(items={}),
        ),
        get_full_state=lambda: {
            "node_id": "node-a",
            "attestations": {"miner-a": {"ts": 1, "value": {"device_arch": "x86"}}},
            "epochs": {},
            "balances": {},
        },
        get_attestation_state=lambda: {
            "node_id": "node-a",
            "attestations": {"miner-a": 1},
        },
    )
    gossip.register_p2p_endpoints(app, p2p_node)
    return app.test_client()


def test_sensitive_p2p_read_endpoints_reject_missing_or_bad_secret():
    client = _make_client()

    for path in ("/p2p/state", "/p2p/attestation_state", "/p2p/peers"):
        assert client.get(path).status_code == 401
        assert client.get(path, headers={"X-P2P-Key": "wrong"}).status_code == 401


def test_sensitive_p2p_read_endpoints_accept_shared_secret():
    client = _make_client()

    for path in ("/p2p/state", "/p2p/attestation_state", "/p2p/peers"):
        response = client.get(path, headers={"X-P2P-Key": P2P_SECRET})
        assert response.status_code == 200


def test_p2p_health_remains_public():
    client = _make_client()

    response = client.get("/p2p/health")

    assert response.status_code == 200
    assert response.get_json()["node_id"] == "node-a"

