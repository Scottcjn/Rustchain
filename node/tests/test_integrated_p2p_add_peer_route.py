# SPDX-License-Identifier: MIT

import importlib.util
import os
import sys
from pathlib import Path
from functools import wraps
from unittest.mock import Mock

NODE_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = NODE_DIR / "rustchain_v2_integrated_v2.2.1_rip200.py"


def load_module(monkeypatch):
    def passthrough_auth(func):
        @wraps(func)
        def decorated(*args, **kwargs):
            return func(*args, **kwargs)
        return decorated

    monkeypatch.setenv("RUSTCHAIN_DISABLE_P2P_AUTO_START", "1")
    monkeypatch.setenv("RC_ADMIN_KEY", "0123456789abcdef0123456789abcdef")
    if str(NODE_DIR) not in sys.path:
        sys.path.insert(0, str(NODE_DIR))
    monkeypatch.setattr("rustchain_p2p_sync_secure.create_p2p_auth_middleware", lambda _auth: passthrough_auth)
    spec = importlib.util.spec_from_file_location("rustchain_integrated_p2p_add_peer_test", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def auth_headers():
    return {"X-Peer-Token": "0123456789abcdef0123456789abcdef"}


def test_p2p_add_peer_rejects_non_object_json(monkeypatch):
    mod = load_module(monkeypatch)

    response = mod.app.test_client().post(
        "/p2p/add_peer",
        json=["peer_url", "http://peer.example:8088"],
        headers=auth_headers(),
    )

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "JSON object required"}


def test_p2p_add_peer_unpacks_tuple_failure(monkeypatch):
    mod = load_module(monkeypatch)
    mod.peer_manager.add_peer = Mock(return_value=(False, "max peers reached"))

    response = mod.app.test_client().post(
        "/p2p/add_peer",
        json={"peer_url": "http://peer.example:8088"},
        headers=auth_headers(),
    )

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "max peers reached"}
