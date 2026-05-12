from flask import Flask

from node.rustchain_p2p_sync import add_p2p_endpoints


class StubPeerManager:
    db_path = ":memory:"

    def __init__(self):
        self.peers = []

    def add_peer(self, peer_url):
        self.peers.append(peer_url)
        return True

    def get_active_peers(self):
        return list(self.peers)


def build_client():
    app = Flask(__name__)
    peer_manager = StubPeerManager()
    add_p2p_endpoints(app, peer_manager, block_sync=None, tx_gossip=None)
    return app.test_client(), peer_manager


def test_p2p_announce_accepts_valid_peer_url():
    client, peer_manager = build_client()

    response = client.post("/p2p/announce", json={"peer_url": "http://peer.example:8088"})

    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "peers": 1}
    assert peer_manager.peers == ["http://peer.example:8088"]


def test_p2p_announce_rejects_non_object_json():
    client, _ = build_client()

    response = client.post("/p2p/announce", json=["peer_url", "http://peer.example:8088"])

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "JSON object required"}


def test_p2p_announce_rejects_missing_peer_url():
    client, _ = build_client()

    response = client.post("/p2p/announce", json={})

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "peer_url required"}
