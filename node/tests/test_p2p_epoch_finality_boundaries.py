# SPDX-License-Identifier: MIT

import os
import sys
from pathlib import Path

os.environ.setdefault("RC_P2P_SECRET", "a" * 64)
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "node"))

from rustchain_p2p_gossip import GossipLayer, MessageType


def _layer(node_id, peers, db_path):
    return GossipLayer(
        node_id=node_id,
        peers=peers,
        db_path=str(db_path),
    )


def test_signed_state_sync_cannot_inject_epoch_finality(tmp_path, monkeypatch):
    monkeypatch.setenv("RC_P2P_SECRET", "a" * 64)
    victim = _layer(
        "victim",
        {"peer1": "https://peer1.example"},
        tmp_path / "victim.db",
    )
    peer = _layer(
        "peer1",
        {"victim": "https://victim.example"},
        tmp_path / "peer.db",
    )

    msg = peer.create_message(
        MessageType.STATE,
        {
            "state": {
                "attestations": {},
                "epochs": {
                    "epochs": [999],
                    "metadata": {999: {"finalized": True, "proposal_hash": "fake"}},
                },
                "balances": {},
            }
        },
        ttl=0,
    )

    assert victim.verify_message(msg)
    assert victim._handle_state(msg)["status"] == "ok"
    assert not victim.epoch_crdt.contains(999)
    assert 999 not in victim.epoch_crdt.metadata


def test_epoch_commit_rejects_sender_reported_quorum_without_local_votes(tmp_path, monkeypatch):
    monkeypatch.setenv("RC_P2P_SECRET", "a" * 64)
    victim = _layer(
        "victim",
        {
            "peer1": "https://peer1.example",
            "peer2": "https://peer2.example",
            "peer3": "https://peer3.example",
        },
        tmp_path / "victim.db",
    )
    peer1 = _layer(
        "peer1",
        {
            "victim": "https://victim.example",
            "peer2": "https://peer2.example",
            "peer3": "https://peer3.example",
        },
        tmp_path / "peer1.db",
    )

    msg = peer1.create_message(
        MessageType.EPOCH_COMMIT,
        {
            "epoch": 31337,
            "proposal_hash": "forged-by-one-peer",
            "accept_count": 3,
            "voters": ["peer1", "peer2", "peer3"],
        },
        ttl=0,
    )

    result = victim.handle_message(msg)

    assert result["status"] == "error"
    assert result["reason"] == "unverified_voters"
    assert not victim.epoch_crdt.contains(31337)


def test_epoch_commit_accepts_quorum_backed_by_local_votes(tmp_path, monkeypatch):
    monkeypatch.setenv("RC_P2P_SECRET", "a" * 64)
    victim = _layer(
        "victim",
        {
            "peer1": "https://peer1.example",
            "peer2": "https://peer2.example",
            "peer3": "https://peer3.example",
        },
        tmp_path / "victim.db",
    )
    peer1 = _layer(
        "peer1",
        {
            "victim": "https://victim.example",
            "peer2": "https://peer2.example",
            "peer3": "https://peer3.example",
        },
        tmp_path / "peer1.db",
    )
    victim._epoch_votes[(7, "proposal-a")] = {
        "peer1": "accept",
        "peer2": "accept",
        "peer3": "accept",
    }

    msg = peer1.create_message(
        MessageType.EPOCH_COMMIT,
        {
            "epoch": 7,
            "proposal_hash": "proposal-a",
            "accept_count": 3,
            "voters": ["peer1", "peer2", "peer3"],
        },
        ttl=0,
    )

    result = victim.handle_message(msg)

    assert result["status"] == "committed"
    assert victim.epoch_crdt.contains(7)
    assert victim.epoch_crdt.metadata[7]["voters"] == ["peer1", "peer2", "peer3"]
