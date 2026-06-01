# SPDX-License-Identifier: MIT

import os
import sys
from pathlib import Path

os.environ.setdefault("RC_P2P_SECRET", "a" * 64)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "node"))

from rustchain_p2p_gossip import GossipLayer, MessageType


def test_signed_state_sync_cannot_inject_epoch_finality(tmp_path, monkeypatch):
    monkeypatch.setenv("RC_P2P_SECRET", "a" * 64)
    victim = GossipLayer(
        node_id="victim",
        peers={"peer1": "https://peer1.example"},
        db_path=str(tmp_path / "victim.db"),
    )
    peer = GossipLayer(
        node_id="peer1",
        peers={"victim": "https://victim.example"},
        db_path=str(tmp_path / "peer.db"),
    )

    payload = {
        "state": {
            "attestations": {},
            "epochs": {
                "epochs": [999],
                "metadata": {999: {"finalized": True, "proposal_hash": "fake"}},
            },
            "balances": {},
        }
    }
    msg = peer.create_message(MessageType.STATE, payload, ttl=0)
    assert victim.verify_message(msg)

    result = victim._handle_state(msg)

    assert result["status"] == "ok"
    assert not victim.epoch_crdt.contains(999)
    assert 999 not in victim.epoch_crdt.metadata


def test_epoch_commit_rejects_sender_reported_quorum_without_local_votes(tmp_path, monkeypatch):
    monkeypatch.setenv("RC_P2P_SECRET", "a" * 64)
    victim = GossipLayer(
        node_id="victim",
        peers={
            "peer1": "https://peer1.example",
            "peer2": "https://peer2.example",
            "peer3": "https://peer3.example",
        },
        db_path=str(tmp_path / "victim.db"),
    )
    peer1 = GossipLayer(
        node_id="peer1",
        peers={
            "victim": "https://victim.example",
            "peer2": "https://peer2.example",
            "peer3": "https://peer3.example",
        },
        db_path=str(tmp_path / "peer1.db"),
    )

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

    assert result["status"] == "error"
    assert result["reason"] == "unverified_voters"
    assert not victim.epoch_crdt.contains(7)


def test_hmac_epoch_votes_cannot_impersonate_multiple_voters(tmp_path, monkeypatch):
    monkeypatch.setenv("RC_P2P_SECRET", "a" * 64)
    victim = GossipLayer(
        node_id="victim",
        peers={
            "peer1": "https://peer1.example",
            "peer2": "https://peer2.example",
            "peer3": "https://peer3.example",
        },
        db_path=str(tmp_path / "victim.db"),
    )
    proposal_hash = "proposal-hmac-impersonation"

    results = []
    for peer_id in ("peer1", "peer2", "peer3"):
        sender = GossipLayer(
            node_id=peer_id,
            peers={
                "victim": "https://victim.example",
                "peer1": "https://peer1.example",
                "peer2": "https://peer2.example",
                "peer3": "https://peer3.example",
            },
            db_path=str(tmp_path / f"{peer_id}.db"),
        )
        msg = sender.create_message(
            MessageType.EPOCH_VOTE,
            {
                "epoch": 9,
                "proposal_hash": proposal_hash,
                "vote": "accept",
                "voter": peer_id,
            },
            ttl=0,
        )
        assert victim.verify_message(msg)
        results.append(victim.handle_message(msg))

    assert [result["reason"] for result in results] == [
        "epoch_vote_requires_ed25519",
        "epoch_vote_requires_ed25519",
        "epoch_vote_requires_ed25519",
    ]
    assert not victim.epoch_crdt.contains(9)
    assert victim._epoch_votes.get((9, proposal_hash), {}) == {}


def test_epoch_commit_accepts_quorum_backed_by_local_votes(tmp_path, monkeypatch):
    monkeypatch.setenv("RC_P2P_SECRET", "a" * 64)
    victim = GossipLayer(
        node_id="victim",
        peers={
            "peer1": "https://peer1.example",
            "peer2": "https://peer2.example",
            "peer3": "https://peer3.example",
        },
        db_path=str(tmp_path / "victim.db"),
    )
    peer1 = GossipLayer(
        node_id="peer1",
        peers={
            "victim": "https://victim.example",
            "peer2": "https://peer2.example",
            "peer3": "https://peer3.example",
        },
        db_path=str(tmp_path / "peer1.db"),
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
    assert victim.epoch_crdt.metadata[7]["proposal_hash"] == "proposal-a"
    assert victim.epoch_crdt.metadata[7]["voters"] == ["peer1", "peer2", "peer3"]


def test_epoch_commit_rejects_without_quorum(tmp_path, monkeypatch):
    monkeypatch.setenv("RC_P2P_SECRET", "a" * 64)
    victim = GossipLayer(
        node_id="victim",
        peers={"peer1": "https://peer1.example", "peer2": "https://peer2.example"},
        db_path=str(tmp_path / "victim.db"),
    )
    peer1 = GossipLayer(
        node_id="peer1",
        peers={"victim": "https://victim.example", "peer2": "https://peer2.example"},
        db_path=str(tmp_path / "peer1.db"),
    )

    msg = peer1.create_message(
        MessageType.EPOCH_COMMIT,
        {
            "epoch": 8,
            "proposal_hash": "proposal-b",
            "accept_count": 2,
            "voters": ["peer1", "peer2"],
        },
        ttl=0,
    )

    result = victim.handle_message(msg)

    assert result["status"] == "error"
    assert result["reason"] == "insufficient_quorum"
    assert not victim.epoch_crdt.contains(8)
