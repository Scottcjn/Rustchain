# SPDX-License-Identifier: MIT
"""
Regression (audit A5): the node must construct AirdropV2 on its real DB file.

AirdropV2(db_path=":memory:") is the constructor default. The node used to call
AirdropV2() with no arguments, so every gunicorn worker held its own private
in-memory claims table that vanished on restart - the one-claim-per-GitHub/
wallet rule (RIP-305) was never actually persisted or shared.
"""

import importlib.util
import os
import sqlite3
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
NODE_DIR = PROJECT_ROOT / "node"
MODULE_PATH = NODE_DIR / "rustchain_v2_integrated_v2.2.1_rip200.py"

if str(NODE_DIR) not in sys.path:
    sys.path.insert(0, str(NODE_DIR))

from airdrop_v2 import AirdropV2  # noqa: E402


def _load_node(db_path: Path):
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from tests import mock_crypto

    sys.modules["rustchain_crypto"] = mock_crypto
    os.environ["DB_PATH"] = str(db_path)
    os.environ["RUSTCHAIN_DB_PATH"] = str(db_path)
    os.environ.setdefault("RC_ADMIN_KEY", "0" * 32)
    spec = importlib.util.spec_from_file_location("integrated_node_airdrop_db_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_node_constructs_airdrop_on_its_db_file(tmp_path):
    db_path = tmp_path / "node_airdrop.sqlite3"
    node = _load_node(db_path)
    if not getattr(node, "HAVE_AIRDROP", False):
        pytest.skip("airdrop_v2 not importable in this environment")

    airdrop = node.airdrop_instance
    assert airdrop.db_path == node.DB_PATH == str(db_path)
    assert airdrop.db_path != ":memory:"

    # The schema landed in the shared file, not in a private in-memory DB.
    with sqlite3.connect(db_path) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"airdrop_claims", "airdrop_allocation"} <= tables


def test_claims_persist_across_instances_on_same_path(tmp_path):
    """Two workers (two AirdropV2 instances) on the same file see the same claim."""
    db_path = str(tmp_path / "shared_airdrop.sqlite3")
    worker_a = AirdropV2(db_path=db_path)
    conn = worker_a._get_conn()
    conn.execute(
        "INSERT INTO airdrop_claims (claim_id, github_username, wallet_address, chain, tier, amount_uwrtc, timestamp, status)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, 'completed')",
        ("claim-a", "octocat", "octocat-wallet", "solana", "bronze", 1_000_000, int(time.time())),
    )
    conn.commit()
    worker_a._close_conn(conn)

    worker_b = AirdropV2(db_path=db_path)  # simulates a second gunicorn worker / restart
    assert worker_b._has_claimed("octocat", "octocat-wallet", "solana") is True
    assert worker_b._has_claimed("someone-else", "other-wallet", "solana") is False

    # Control: the in-memory default really is per-instance (what the node used to get).
    mem_a = AirdropV2()
    assert mem_a.db_path == ":memory:"
    assert mem_a._has_claimed("octocat", "octocat-wallet", "solana") is False
