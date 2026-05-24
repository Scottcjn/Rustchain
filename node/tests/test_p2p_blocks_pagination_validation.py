# SPDX-License-Identifier: MIT

import importlib.util
import os
import sys
import tempfile
from pathlib import Path


NODE_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = NODE_DIR / "rustchain_v2_integrated_v2.2.1_rip200.py"


def _load_module(module_name: str, db_path: str):
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    mod.init_db()
    return mod


def _auth_headers(mod, body: str = ""):
    signature, timestamp = mod.peer_manager.auth_manager.generate_signature(body)
    return {
        "X-Peer-Signature": signature,
        "X-Peer-Timestamp": timestamp,
    }


def test_p2p_blocks_rejects_negative_start_and_limit():
    prev_db = os.environ.get("RUSTCHAIN_DB_PATH")
    prev_admin = os.environ.get("RC_ADMIN_KEY")
    prev_p2p_key = os.environ.get("RC_P2P_KEY")
    prev_disable = os.environ.get("RUSTCHAIN_DISABLE_P2P_AUTO_START")
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "p2p_blocks_bounds.db")
        os.environ["RUSTCHAIN_DB_PATH"] = db_path
        os.environ["RC_ADMIN_KEY"] = "0123456789abcdef0123456789abcdef"
        os.environ["RC_P2P_KEY"] = "test-p2p-shared-key"
        os.environ["RUSTCHAIN_DISABLE_P2P_AUTO_START"] = "1"

        mod = _load_module("rustchain_p2p_blocks_bounds", db_path)
        client = mod.app.test_client()

        negative_start = client.get(
            "/p2p/blocks?start=-1&limit=10",
            headers=_auth_headers(mod),
        )
        assert negative_start.status_code == 400
        assert negative_start.get_json() == {"ok": False, "error": "start_must_be_non_negative"}

        non_positive_limit = client.get(
            "/p2p/blocks?start=0&limit=0",
            headers=_auth_headers(mod),
        )
        assert non_positive_limit.status_code == 400
        assert non_positive_limit.get_json() == {"ok": False, "error": "limit_must_be_positive"}

        if hasattr(mod, "block_sync") and hasattr(mod.block_sync, "stop"):
            mod.block_sync.stop()

    if prev_db is None:
        os.environ.pop("RUSTCHAIN_DB_PATH", None)
    else:
        os.environ["RUSTCHAIN_DB_PATH"] = prev_db
    if prev_admin is None:
        os.environ.pop("RC_ADMIN_KEY", None)
    else:
        os.environ["RC_ADMIN_KEY"] = prev_admin
    if prev_p2p_key is None:
        os.environ.pop("RC_P2P_KEY", None)
    else:
        os.environ["RC_P2P_KEY"] = prev_p2p_key
    if prev_disable is None:
        os.environ.pop("RUSTCHAIN_DISABLE_P2P_AUTO_START", None)
    else:
        os.environ["RUSTCHAIN_DISABLE_P2P_AUTO_START"] = prev_disable


def test_p2p_blocks_caps_limit_to_1000():
    prev_db = os.environ.get("RUSTCHAIN_DB_PATH")
    prev_admin = os.environ.get("RC_ADMIN_KEY")
    prev_p2p_key = os.environ.get("RC_P2P_KEY")
    prev_disable = os.environ.get("RUSTCHAIN_DISABLE_P2P_AUTO_START")
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "p2p_blocks_cap.db")
        os.environ["RUSTCHAIN_DB_PATH"] = db_path
        os.environ["RC_ADMIN_KEY"] = "0123456789abcdef0123456789abcdef"
        os.environ["RC_P2P_KEY"] = "test-p2p-shared-key"
        os.environ["RUSTCHAIN_DISABLE_P2P_AUTO_START"] = "1"

        mod = _load_module("rustchain_p2p_blocks_limit_cap", db_path)
        client = mod.app.test_client()

        captured = {}

        def _fake_get_blocks(start_height, limit):
            captured["start"] = start_height
            captured["limit"] = limit
            return []

        mod.block_sync.get_blocks_for_sync = _fake_get_blocks
        response = client.get(
            "/p2p/blocks?start=5&limit=5000",
            headers=_auth_headers(mod),
        )
        assert response.status_code == 200
        assert response.get_json() == {"ok": True, "blocks": []}
        assert captured == {"start": 5, "limit": 1000}

        if hasattr(mod, "block_sync") and hasattr(mod.block_sync, "stop"):
            mod.block_sync.stop()

    if prev_db is None:
        os.environ.pop("RUSTCHAIN_DB_PATH", None)
    else:
        os.environ["RUSTCHAIN_DB_PATH"] = prev_db
    if prev_admin is None:
        os.environ.pop("RC_ADMIN_KEY", None)
    else:
        os.environ["RC_ADMIN_KEY"] = prev_admin
    if prev_p2p_key is None:
        os.environ.pop("RC_P2P_KEY", None)
    else:
        os.environ["RC_P2P_KEY"] = prev_p2p_key
    if prev_disable is None:
        os.environ.pop("RUSTCHAIN_DISABLE_P2P_AUTO_START", None)
    else:
        os.environ["RUSTCHAIN_DISABLE_P2P_AUTO_START"] = prev_disable
