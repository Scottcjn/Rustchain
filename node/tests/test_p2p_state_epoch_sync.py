# SPDX-License-Identifier: MIT

import os
import sys
from pathlib import Path

os.environ.setdefault("RC_P2P_SECRET", "a" * 64)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import rustchain_p2p_gossip as p2p
from rustchain_p2p_gossip import GossipLayer, MessageType


def _cluster_node(tmp_path, node_id):
    all_nodes = {
        "victim": "https://victim.example",
        "peer1": "https://peer1.example",
        "peer2": "https://peer2.example",
        "peer3": "https://peer3.example",
    }
    return GossipLayer(
        node_id=node_id,
        peers={peer_id: url for peer_id, url in all_nodes.items() if peer_id != node_id},
        db_path=str(tmp_path / f"{node_id}.db"),
    )


def _accept_vote(node, epoch=7, proposal_hash="proposal-a"):
    return node.create_message(
        MessageType.EPOCH_VOTE,
        {
            "epoch": epoch,
            "proposal_hash": proposal_hash,
            "vote": "accept",
            "voter": node.node_id,
        },
        ttl=0,
    )


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


def test_epoch_vote_omits_partial_certificate_after_vote_reload(tmp_path, monkeypatch):
    monkeypatch.setenv("RC_P2P_SECRET", "a" * 64)
    node = _cluster_node(tmp_path, "victim")
    peer3 = _cluster_node(tmp_path, "peer3")
    key = (7, "proposal-a")
    node._epoch_votes[key] = {
        "peer1": "accept",
        "peer2": "accept",
    }
    broadcasted = []
    monkeypatch.setattr(node, "broadcast", lambda msg: broadcasted.append(msg))

    result = node.handle_message(_accept_vote(peer3))

    assert result["status"] == "committed"
    assert len(broadcasted) == 1
    assert "vote_certificate" not in broadcasted[0].payload
    assert broadcasted[0].payload["voters"] == ["peer1", "peer2", "peer3"]


def test_epoch_commit_partial_certificate_falls_back_to_local_votes(tmp_path, monkeypatch):
    monkeypatch.setenv("RC_P2P_SECRET", "a" * 64)
    victim = _cluster_node(tmp_path, "victim")
    peer1 = _cluster_node(tmp_path, "peer1")
    peer3 = _cluster_node(tmp_path, "peer3")
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
            "vote_certificate": [_accept_vote(peer3).to_dict()],
        },
        ttl=0,
    )

    result = victim.handle_message(msg)

    assert result["status"] == "committed"
    assert victim.epoch_crdt.contains(7)
    assert victim.epoch_crdt.metadata[7]["voters"] == ["peer1", "peer2", "peer3"]
    assert "certificate" not in victim.epoch_crdt.metadata[7]


def test_epoch_commit_accepts_quorum_backed_by_vote_certificate(tmp_path, monkeypatch):
    monkeypatch.setenv("RC_P2P_SECRET", "a" * 64)
    victim = _cluster_node(tmp_path, "victim")
    peer1 = _cluster_node(tmp_path, "peer1")
    peer2 = _cluster_node(tmp_path, "peer2")
    peer3 = _cluster_node(tmp_path, "peer3")

    vote_certificate = [
        _accept_vote(peer1).to_dict(),
        _accept_vote(peer2).to_dict(),
        _accept_vote(peer3).to_dict(),
    ]
    msg = peer1.create_message(
        MessageType.EPOCH_COMMIT,
        {
            "epoch": 7,
            "proposal_hash": "proposal-a",
            "accept_count": 3,
            "voters": ["peer1", "peer2", "peer3"],
            "vote_certificate": vote_certificate,
        },
        ttl=0,
    )

    result = victim.handle_message(msg)

    assert result["status"] == "committed"
    assert victim.epoch_crdt.contains(7)
    assert victim.epoch_crdt.metadata[7]["proposal_hash"] == "proposal-a"
    assert victim.epoch_crdt.metadata[7]["voters"] == ["peer1", "peer2", "peer3"]
    assert victim.epoch_crdt.metadata[7]["certificate"] is True


def test_epoch_commit_certificate_allows_stale_votes_for_offline_catchup(tmp_path, monkeypatch):
    monkeypatch.setenv("RC_P2P_SECRET", "a" * 64)
    now = p2p.time.time()
    victim = _cluster_node(tmp_path, "victim")
    peer1 = _cluster_node(tmp_path, "peer1")
    peer2 = _cluster_node(tmp_path, "peer2")
    peer3 = _cluster_node(tmp_path, "peer3")

    vote_certificate = [
        _accept_vote(peer1).to_dict(),
        _accept_vote(peer2).to_dict(),
        _accept_vote(peer3).to_dict(),
    ]
    monkeypatch.setattr(p2p.time, "time", lambda: now + p2p.MESSAGE_EXPIRY + 30)
    msg = peer1.create_message(
        MessageType.EPOCH_COMMIT,
        {
            "epoch": 7,
            "proposal_hash": "proposal-a",
            "accept_count": 3,
            "voters": ["peer1", "peer2", "peer3"],
            "vote_certificate": vote_certificate,
        },
        ttl=0,
    )

    result = victim.handle_message(msg)

    assert result["status"] == "committed"
    assert victim.epoch_crdt.contains(7)


def test_epoch_commit_rejects_tampered_vote_certificate(tmp_path, monkeypatch):
    monkeypatch.setenv("RC_P2P_SECRET", "a" * 64)
    victim = _cluster_node(tmp_path, "victim")
    peer1 = _cluster_node(tmp_path, "peer1")
    peer2 = _cluster_node(tmp_path, "peer2")
    peer3 = _cluster_node(tmp_path, "peer3")

    vote_certificate = [
        _accept_vote(peer1).to_dict(),
        _accept_vote(peer2).to_dict(),
        _accept_vote(peer3).to_dict(),
    ]
    vote_certificate[1]["payload"]["proposal_hash"] = "proposal-b"
    msg = peer1.create_message(
        MessageType.EPOCH_COMMIT,
        {
            "epoch": 7,
            "proposal_hash": "proposal-a",
            "accept_count": 3,
            "voters": ["peer1", "peer2", "peer3"],
            "vote_certificate": vote_certificate,
        },
        ttl=0,
    )

    result = victim.handle_message(msg)

    assert result["status"] == "error"
    assert result["reason"] == "invalid_vote_certificate_signature"
    assert not victim.epoch_crdt.contains(7)


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
