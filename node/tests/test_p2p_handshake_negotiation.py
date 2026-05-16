#!/usr/bin/env python3
"""Regression tests for P2P handshake parameter negotiation."""

import importlib
import os
import sqlite3
import sys
from pathlib import Path


P2P_SECRET = "unit-test-secret-0123456789abcdef"
os.environ["RC_P2P_SECRET"] = P2P_SECRET

NODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(NODE_DIR))

if "rustchain_p2p_gossip" in sys.modules:
    del sys.modules["rustchain_p2p_gossip"]
gossip = importlib.import_module("rustchain_p2p_gossip")


def _init_minimal_p2p_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS p2p_seen_messages (
                msg_id TEXT PRIMARY KEY,
                ts INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS p2p_epoch_votes (
                epoch INTEGER NOT NULL,
                proposal_hash TEXT NOT NULL,
                voter TEXT NOT NULL,
                vote TEXT NOT NULL,
                ts INTEGER NOT NULL,
                PRIMARY KEY (epoch, proposal_hash, voter)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS miner_attest_recent (
                miner TEXT PRIMARY KEY,
                ts_ok INTEGER,
                device_family TEXT,
                device_arch TEXT,
                entropy_score REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS epoch_state (
                epoch INTEGER PRIMARY KEY,
                settled INTEGER
            )
            """
        )


def test_negotiate_handshake_params_chooses_compatible_values():
    local = {
        "protocol_version": 2,
        "k_bucket_size": 20,
        "ping_interval": 30,
        "timeout": 10,
    }
    remote = {
        "protocol_version": 1,
        "k_bucket_size": 16,
        "ping_interval": 60,
        "timeout": 45,
    }

    assert gossip.negotiate_handshake_params(local, remote) == {
        "protocol_version": 1,
        "k_bucket_size": 16,
        "ping_interval": 30,
        "timeout": 45,
    }
    assert gossip.handshake_mismatches(local, remote) == {
        "protocol_version": {"local": 2, "remote": 1},
        "k_bucket_size": {"local": 20, "remote": 16},
        "ping_interval": {"local": 30, "remote": 60},
        "timeout": {"local": 10, "remote": 45},
    }


def test_ping_response_includes_local_and_agreed_handshake(tmp_path):
    local_db = tmp_path / "local.db"
    remote_db = tmp_path / "remote.db"
    _init_minimal_p2p_db(local_db)
    _init_minimal_p2p_db(remote_db)

    local = gossip.GossipLayer(
        "local",
        {"remote": "http://remote.example"},
        str(local_db),
    )
    remote = gossip.GossipLayer(
        "remote",
        {"local": "http://local.example"},
        str(remote_db),
    )

    ping = remote.create_message(gossip.MessageType.PING, {
        "node_id": "remote",
        "handshake": {
            "protocol_version": 1,
            "k_bucket_size": 12,
            "ping_interval": 90,
            "timeout": 45,
        },
    })

    response = local.handle_message(ping)

    assert response["status"] == "ok"
    pong_payload = response["pong"]["payload"]
    assert pong_payload["handshake"] == gossip.local_handshake_params()
    assert pong_payload["agreed_handshake"] == {
        "protocol_version": 1,
        "k_bucket_size": 12,
        "ping_interval": gossip.local_handshake_params()["ping_interval"],
        "timeout": 45,
    }
    assert pong_payload["handshake_mismatches"]["k_bucket_size"] == {
        "local": gossip.local_handshake_params()["k_bucket_size"],
        "remote": 12,
    }
