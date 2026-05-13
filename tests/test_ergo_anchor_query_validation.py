import importlib.util
import sqlite3
import sys
import types
from pathlib import Path

import pytest
from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
ANCHOR_MODULES = (
    REPO_ROOT / "ergo-anchor" / "rustchain_ergo_anchor.py",
    REPO_ROOT / "node" / "rustchain_ergo_anchor.py",
)


@pytest.fixture(autouse=True)
def stub_rustchain_crypto(monkeypatch):
    crypto = types.ModuleType("rustchain_crypto")
    crypto.blake2b256_hex = lambda data: "00" * 32
    crypto.canonical_json = lambda data: "{}"

    class MerkleTree:
        root_hex = "00" * 32

    crypto.MerkleTree = MerkleTree
    monkeypatch.setitem(sys.modules, "rustchain_crypto", crypto)


def load_anchor_module(path: Path):
    module_name = f"test_{path.parent.name.replace('-', '_')}_rustchain_ergo_anchor"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)
    return module


def seed_anchor_db(db_path: Path, count: int = 120):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE ergo_anchors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rustchain_height INTEGER NOT NULL,
                rustchain_hash TEXT NOT NULL,
                commitment_hash TEXT NOT NULL,
                ergo_tx_id TEXT NOT NULL,
                ergo_height INTEGER,
                confirmations INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                created_at INTEGER NOT NULL
            )
            """
        )
        for height in range(1, count + 1):
            conn.execute(
                """
                INSERT INTO ergo_anchors (
                    rustchain_height, rustchain_hash, commitment_hash,
                    ergo_tx_id, ergo_height, confirmations, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    height,
                    f"hash-{height}",
                    f"commitment-{height}",
                    f"ergo-{height}",
                    height + 1000,
                    6,
                    "confirmed",
                    height,
                ),
            )
        conn.commit()


class AnchorServiceStub:
    def __init__(self, db_path: Path):
        self.db_path = str(db_path)


@pytest.fixture(params=ANCHOR_MODULES, ids=lambda path: path.parent.as_posix())
def client(request, tmp_path):
    seed_anchor_db(tmp_path / "anchors.db")
    app = Flask(__name__)
    module = load_anchor_module(request.param)
    module.create_anchor_api_routes(app, AnchorServiceStub(tmp_path / "anchors.db"))
    return app.test_client()


@pytest.mark.parametrize(
    "query, expected_error",
    (
        ("limit=abc", "limit_must_be_integer"),
        ("limit=0", "limit_must_be_at_least_1"),
        ("limit=-1", "limit_must_be_at_least_1"),
        ("offset=abc", "offset_must_be_integer"),
        ("offset=-1", "offset_must_be_at_least_0"),
    ),
)
def test_anchor_list_rejects_invalid_pagination(client, query, expected_error):
    response = client.get(f"/anchor/list?{query}")

    assert response.status_code == 400
    assert response.get_json() == {"error": expected_error}


def test_anchor_list_caps_limit_and_accepts_non_negative_offset(client):
    response = client.get("/anchor/list?limit=500&offset=5")

    assert response.status_code == 200
    body = response.get_json()
    assert body["count"] == 100
    assert body["anchors"][0]["rustchain_height"] == 115
    assert body["anchors"][-1]["rustchain_height"] == 16
