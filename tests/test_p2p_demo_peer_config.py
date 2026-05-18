# SPDX-License-Identifier: MIT

import importlib
import os
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
NODE_DIR = ROOT / "node"
if str(NODE_DIR) not in sys.path:
    sys.path.insert(0, str(NODE_DIR))

os.environ.setdefault("RC_P2P_SECRET", "test-secret-for-p2p-peer-config-0123456789")

p2p = importlib.import_module("rustchain_p2p_gossip")


def test_default_demo_peers_use_https_only():
    peers = p2p._load_demo_peers("node2", raw_peers="")

    assert peers == {"node1": "https://rustchain.org"}
    assert all(not url.startswith("http://") for url in peers.values())


def test_peer_config_rejects_remote_plaintext_http():
    with pytest.raises(ValueError, match="must use HTTPS"):
        p2p._parse_peer_config("node2=http://50.28.86.153:8099")


def test_peer_config_allows_loopback_http_for_local_dev():
    peers = p2p._parse_peer_config(
        "node2=http://localhost:8099,node3=https://peer.example"
    )

    assert peers == {
        "node2": "http://localhost:8099",
        "node3": "https://peer.example",
    }
