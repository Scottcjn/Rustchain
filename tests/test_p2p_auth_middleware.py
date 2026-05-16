# SPDX-License-Identifier: MIT

import sys
from pathlib import Path

import pytest
from flask import Flask, jsonify

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "node"))

import rustchain_p2p_sync_secure as p2p_secure


class StaticKeyAuthManager(p2p_secure.P2PAuthManager):
    def _start_key_rotation(self):
        """Disable the background rotation thread in unit tests."""


def _build_client(monkeypatch):
    monkeypatch.setenv("RC_P2P_KEY", "unit-test-p2p-key")

    app = Flask(__name__)
    auth_manager = StaticKeyAuthManager(rotation_interval=10**9)
    require_peer_auth = p2p_secure.create_p2p_auth_middleware(auth_manager)

    @app.route("/p2p/blocks", methods=["GET"])
    @require_peer_auth
    def blocks():
        return jsonify({"ok": True})

    @app.route("/p2p/ping", methods=["POST"])
    @require_peer_auth
    def ping():
        return jsonify({"ok": True})

    return app.test_client(), auth_manager


def _signed_headers(auth_manager, body: str):
    signature, timestamp = auth_manager.generate_signature(body)
    return {
        "X-Peer-Signature": signature,
        "X-Peer-Timestamp": timestamp,
    }


def test_localhost_blocks_missing_peer_auth_headers(monkeypatch):
    client, _ = _build_client(monkeypatch)

    response = client.get(
        "/p2p/blocks",
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == "Missing authentication headers"


def test_p2p_blocks_accepts_signed_empty_get_body(monkeypatch):
    client, auth_manager = _build_client(monkeypatch)

    response = client.get(
        "/p2p/blocks",
        headers=_signed_headers(auth_manager, ""),
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )

    assert response.status_code == 200
    assert response.get_json()["ok"] is True


def test_p2p_ping_rejects_signature_for_wrong_body(monkeypatch):
    client, auth_manager = _build_client(monkeypatch)
    body = '{"ping":"real"}'

    response = client.post(
        "/p2p/ping",
        data=body,
        content_type="application/json",
        headers=_signed_headers(auth_manager, '{"ping":"tampered"}'),
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == "Invalid signature"
