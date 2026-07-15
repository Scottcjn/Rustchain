# SPDX-License-Identifier: MIT
"""sync_from_peers must sign the pre-image the auth middleware actually verifies.

The signer built its own message (`get_blocks:{peer_url}`) while
create_p2p_auth_middleware verifies over `request.get_data()`, so the two HMACs
were computed over different pre-images and every sync request 401'd -- with no
else-branch and no reputation penalty, so silently.

This drives the REAL sync_from_peers against the REAL middleware over a shared
key; only requests.get is redirected into a Flask test client.
"""
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

import pytest
from flask import Flask, jsonify


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "node" / "rustchain_p2p_sync_secure.py"

os.environ["RC_P2P_KEY"] = "shared-network-key"
spec = importlib.util.spec_from_file_location("rustchain_p2p_sync_secure", MODULE_PATH)
p2p = importlib.util.module_from_spec(spec)
sys.modules["rustchain_p2p_sync_secure"] = p2p
spec.loader.exec_module(p2p)

PEER_URL = "http://peer.example:8099"


class _Resp:
    """The bit of requests.Response that sync_from_peers touches."""

    def __init__(self, flask_response):
        self.status_code = flask_response.status_code
        self.ok = flask_response.status_code < 400
        self._json = flask_response.get_json()

    def json(self):
        return self._json


@pytest.fixture
def rig(monkeypatch):
    """Real peer manager + real auth middleware, wired peer-to-peer over HTTP."""
    db_path = os.path.join(tempfile.mkdtemp(), "peers.db")
    manager = p2p.SecurePeerManager(db_path=db_path, local_host="127.0.0.1", local_port=8099)
    sync = p2p.SecureBlockSync(manager, db_path=db_path)

    with __import__("sqlite3").connect(db_path) as conn:
        conn.execute(
            "INSERT INTO peers (peer_url, is_active, is_banned) VALUES (?, 1, 0)", (PEER_URL,)
        )

    # The remote node: same module, same shared key, the middleware as the monolith wires it
    # (node/rustchain_v2_integrated_v2.2.1_rip200.py:10693-10694).
    remote_auth = p2p.P2PAuthManager()
    require_peer_auth = p2p.create_p2p_auth_middleware(remote_auth)
    app = Flask(__name__)
    served = [{"block_index": 1, "previous_hash": "0" * 64, "timestamp": 0,
               "miner": "node1", "transactions": [], "hash": "a" * 64}]

    @app.route("/p2p/blocks", methods=["GET"])
    @require_peer_auth
    def p2p_blocks():
        return jsonify({"blocks": served})

    client = app.test_client()
    seen = []

    def fake_get(url, headers=None, timeout=None):
        resp = client.get("/p2p/blocks", headers=headers or {})
        seen.append(resp.status_code)
        return _Resp(resp)

    monkeypatch.setattr(p2p.requests, "get", fake_get)

    applied = []
    monkeypatch.setattr(p2p.SecureBlockSync, "_apply_block",
                        lambda self, block: applied.append(block))
    monkeypatch.setattr(p2p.BlockValidator, "validate_block", lambda self, block: (True, None))
    return sync, seen, applied


def test_peer_accepts_our_sync_request(rig):
    """A correctly-keyed peer must authenticate us, not 401 us."""
    sync, seen, _ = rig

    sync.sync_from_peers()

    assert seen == [200], f"peer rejected our own signature: HTTP {seen}"


def test_blocks_from_peer_are_actually_ingested(rig):
    """The 401 fails closed and silent -- `if response.ok` just never runs."""
    sync, _, applied = rig

    sync.sync_from_peers()

    assert len(applied) == 1, "no block ingested; the secure sync path is inert"
    assert applied[0]["block_index"] == 1
