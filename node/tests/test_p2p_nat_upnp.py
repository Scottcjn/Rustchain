# SPDX-License-Identifier: MIT

import os
import sys
import types
from pathlib import Path

from flask import Flask

os.environ.setdefault("RC_P2P_SECRET", "unit-test-secret-0123456789abcdef")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import rustchain_p2p_gossip as gossip
import rustchain_p2p_init as p2p_init


def test_external_url_override_wins(monkeypatch):
    monkeypatch.setenv("RC_P2P_EXTERNAL_URL", "https://home-node.example:8099/")

    assert p2p_init.resolve_advertised_url("192.168.1.20", 8099) == (
        "https://home-node.example:8099"
    )


def test_private_host_uses_upnp_when_available(monkeypatch):
    class FakeUPnP:
        discoverdelay = None

        def discover(self):
            return 1

        def selectigd(self):
            return None

        def externalipaddress(self):
            return "203.0.113.7"

        def addportmapping(self, external_port, proto, local_ip, local_port, desc, remote):
            assert external_port == 8099
            assert proto == "TCP"
            assert local_ip == "192.168.1.20"
            assert local_port == 8099
            return True

    monkeypatch.delenv("RC_P2P_EXTERNAL_URL", raising=False)
    monkeypatch.setitem(sys.modules, "miniupnpc", types.SimpleNamespace(UPnP=FakeUPnP))

    assert p2p_init.resolve_advertised_url("192.168.1.20", 8099) == "http://203.0.113.7:8099"


def test_peer_announce_adds_signed_public_peer(tmp_path):
    db_path = tmp_path / "p2p.db"
    receiver = gossip.GossipLayer("node-a", {}, db_path=str(db_path))
    sender = gossip.GossipLayer("node-b", {}, db_path=str(tmp_path / "sender.db"))

    msg = sender.create_message(
        gossip.MessageType.PEER_ANNOUNCE,
        {"node_id": "node-b", "url": "https://node-b.example:8099"},
    )

    result = receiver.handle_message(msg)

    assert result["status"] == "peer_added"
    assert receiver.peers["node-b"] == "https://node-b.example:8099"


def test_p2p_health_reports_advertised_url(tmp_path):
    node = gossip.RustChainP2PNode(
        "node-a",
        str(tmp_path / "p2p.db"),
        {},
        advertised_url="https://node-a.example:8099",
    )
    app = Flask(__name__)
    gossip.register_p2p_endpoints(app, node)

    response = app.test_client().get("/p2p/health")

    assert response.status_code == 200
    assert response.get_json()["advertised_url"] == "https://node-a.example:8099"
