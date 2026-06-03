# SPDX-License-Identifier: MIT

import importlib.util
import os
import sys
from pathlib import Path

from flask import Flask, jsonify


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "node" / "rustchain_p2p_sync_secure.py"

os.environ["RC_P2P_KEY"] = "test-p2p-key"
spec = importlib.util.spec_from_file_location("rustchain_p2p_sync_secure", MODULE_PATH)
p2p = importlib.util.module_from_spec(spec)
sys.modules["rustchain_p2p_sync_secure"] = p2p
spec.loader.exec_module(p2p)


def make_client():
    app = Flask(__name__)
    auth_manager = p2p.P2PAuthManager(rotation_interval=24 * 60 * 60)
    require_peer_auth = p2p.create_p2p_auth_middleware(auth_manager)

    @app.route("/p2p/blocks", methods=["POST"])
    @require_peer_auth
    def p2p_blocks():
        return jsonify({"ok": True})

    return app.test_client(), auth_manager


def test_trusted_ip_without_signature_is_rejected():
    client, _ = make_client()

    response = client.post(
        "/p2p/blocks",
        data="{}",
        environ_overrides={"REMOTE_ADDR": "127.0.0.1"},
    )

    assert response.status_code == 401
    assert response.get_json() == {"error": "Missing authentication headers"}


def test_former_trusted_peer_ip_still_requires_valid_signature():
    client, auth_manager = make_client()
    body = '{"height":1}'
    signature, timestamp = auth_manager.generate_signature(body)

    response = client.post(
        "/p2p/blocks",
        data=body,
        headers={
            "X-Peer-Signature": signature,
            "X-Peer-Timestamp": timestamp,
        },
        environ_overrides={"REMOTE_ADDR": "50.28.86.131"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"ok": True}


def test_former_trusted_peer_ip_with_bad_signature_is_rejected():
    client, auth_manager = make_client()
    _, timestamp = auth_manager.generate_signature("{}")

    response = client.post(
        "/p2p/blocks",
        data="{}",
        headers={
            "X-Peer-Signature": "bad-signature",
            "X-Peer-Timestamp": timestamp,
        },
        environ_overrides={"REMOTE_ADDR": "50.28.86.153"},
    )

    assert response.status_code == 401
    assert response.get_json() == {"error": "Invalid signature"}
