"""Regression tests for RustChain P2P security hardening Phase 2 (#2256 Phases A-E).

Covers:
- Phase A: sender_id bound into signed content (post-sign flip fails verification)
- Phase B: RR-delegate gate rejects non-leader proposers
- Phase C: votes indexed by (epoch, proposal_hash); mixed-proposal quorum no longer aggregates
- Phase D: _handle_state future-ts rejection + balance namespace scoping
- Phase E: _handle_attestation future-ts + schema validation
"""
import importlib.util
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("RC_P2P_SECRET", "unit-test-secret-0123456789abcdef")

MODULE_PATH = Path(__file__).resolve().parents[1] / "rustchain_p2p_gossip.py"
spec = importlib.util.spec_from_file_location("rustchain_p2p_gossip", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
sys.modules["rustchain_p2p_gossip"] = mod
spec.loader.exec_module(mod)


def _make_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE miner_attest_recent "
            "(miner TEXT PRIMARY KEY, ts_ok INTEGER, device_family TEXT, "
            "device_arch TEXT, entropy_score INTEGER, fingerprint_passed INTEGER)"
        )
        conn.execute("CREATE TABLE epoch_state (epoch INTEGER, settled INTEGER)")
    return path


def _mk_layer(node_id, peers_dict=None, db_path=None):
    db_path = db_path or _make_db()
    layer = mod.GossipLayer(node_id, peers_dict or {}, db_path=db_path)
    layer.broadcast = lambda *args, **kwargs: None  # no-op
    return layer


# Phase A regression
def test_phase_a_sender_id_flip_fails_verification():
    """After Phase A, flipping sender_id post-sign invalidates the signature."""
    layer = _mk_layer("node2", {"node1": "http://n1"})
    msg = layer.create_message(
        mod.MessageType.EPOCH_VOTE,
        {"epoch": 7, "proposal_hash": "abc123", "vote": "accept", "voter": "node2"},
    )
    # Pre-flip: verifies
    assert layer.verify_message(msg)
    # Post-flip: should FAIL now (regression for prior bypass)
    msg.sender_id = "node4"
    assert not layer.verify_message(msg), "Phase A: sender_id flip MUST fail verification"


# Phase A + old spoof regression
def test_phase_a_old_payload_voter_spoof_still_blocked():
    """The original PR #2257 dedup still holds under Phase A."""
    target = _mk_layer("node1", {"node2": "http://n2", "node3": "http://n3", "node4": "http://n4"})
    attacker = _mk_layer("node2", db_path=target.db_path)
    attacker.broadcast = lambda *args, **kwargs: None

    first = attacker.create_message(
        mod.MessageType.EPOCH_VOTE,
        {"epoch": 7, "proposal_hash": "abc123", "vote": "accept", "voter": "node2"},
    )
    spoof = attacker.create_message(
        mod.MessageType.EPOCH_VOTE,
        {"epoch": 7, "proposal_hash": "abc123", "vote": "accept", "voter": "node3"},
    )
    assert target.handle_message(first)["status"] == "ok"
    # Payload voter claim "node3" contradicts authenticated sender "node2" — reject
    result = target.handle_message(spoof)
    assert result["status"] == "error"
    assert result.get("reason") == "voter_identity_mismatch"


def test_p2p_dedup_insert_race_returns_duplicate():
    """A concurrent handler winning the insert after precheck must stop processing."""
    target = _mk_layer("node1", {"node2": "http://n2"})
    sender = _mk_layer("node2", db_path=target.db_path)
    sender.broadcast = lambda *args, **kwargs: None

    msg = sender.create_message(mod.MessageType.PING, {"ping": 1})
    original_verify = target.verify_message

    def racing_verify(message):
        verified = original_verify(message)
        with sqlite3.connect(target.db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO p2p_seen_messages (msg_id, ts) VALUES (?, ?)",
                (message.msg_id, int(time.time())),
            )
        return verified

    target.verify_message = racing_verify

    result = target.handle_message(msg)
    assert result["status"] == "duplicate"
    assert "pong" not in result


# Phase B regression
def test_phase_b_rr_delegate_gate_rejects_non_leader():
    """Phase B: only the scheduled RR-delegate can propose for an epoch."""
    target = _mk_layer("node1", {"node2": "http://n2", "node3": "http://n3", "node4": "http://n4"})
    # nodes sorted = [node1, node2, node3, node4]; leader for epoch=5 is nodes[5 % 4] = node2
    # node3 (not the leader) tries to propose
    attacker = _mk_layer("node3", db_path=target.db_path)
    attacker.broadcast = lambda *args, **kwargs: None

    bad_proposal = attacker.create_message(
        mod.MessageType.EPOCH_PROPOSE,
        {"epoch": 5, "proposer": "node3", "distribution": {}, "merkle_root": "x"},
    )
    result = target.handle_message(bad_proposal)
    assert result["status"] == "reject"
    assert result.get("reason") == "invalid_leader"


# Phase C regression
def test_phase_c_mixed_proposals_dont_aggregate_to_quorum():
    """Phase C: two different proposal_hashes get separate quorum counts."""
    target = _mk_layer("node1", {"node2": "http://n2", "node3": "http://n3", "node4": "http://n4"})
    voters = [_mk_layer(nid, db_path=target.db_path) for nid in ("node2", "node3", "node4")]
    for v in voters:
        v.broadcast = lambda *args, **kwargs: None

    # node2 votes accept on proposal_hash="A"
    # node3 votes accept on proposal_hash="B"
    # node4 votes accept on proposal_hash="A"
    msg_a1 = voters[0].create_message(mod.MessageType.EPOCH_VOTE,
        {"epoch": 9, "proposal_hash": "A", "vote": "accept"})
    msg_b = voters[1].create_message(mod.MessageType.EPOCH_VOTE,
        {"epoch": 9, "proposal_hash": "B", "vote": "accept"})
    msg_a2 = voters[2].create_message(mod.MessageType.EPOCH_VOTE,
        {"epoch": 9, "proposal_hash": "A", "vote": "accept"})

    target.handle_message(msg_a1)
    target.handle_message(msg_b)
    r = target.handle_message(msg_a2)
    # Only 2 of 3 votes were for proposal A — quorum is max(3, 3) = 3. Not reached.
    assert r["status"] != "committed"
    # Verify the two proposals are tracked separately
    assert (9, "A") in target._epoch_votes
    assert (9, "B") in target._epoch_votes
    assert len(target._epoch_votes[(9, "A")]) == 2
    assert len(target._epoch_votes[(9, "B")]) == 1


# Phase E regression
def test_phase_e_future_timestamp_attestation_rejected():
    """Phase E: attestations with ts_ok far in the future are rejected."""
    target = _mk_layer("node1", {"node2": "http://n2"})
    attacker = _mk_layer("node2", db_path=target.db_path)
    attacker.broadcast = lambda *args, **kwargs: None

    future_ts = int(time.time()) + 86400 * 365  # 1 year in the future
    msg = attacker.create_message(
        mod.MessageType.ATTESTATION,
        {"miner": "evil_miner_pin", "ts_ok": future_ts, "device_arch": "modern"},
    )
    result = target.handle_message(msg)
    assert result["status"] == "error"
    assert result.get("reason") == "future_timestamp"


def test_phase_e_attestation_schema_validation():
    """Phase E: missing or invalid miner_id is rejected."""
    target = _mk_layer("node1", {"node2": "http://n2"})
    attacker = _mk_layer("node2", db_path=target.db_path)
    attacker.broadcast = lambda *args, **kwargs: None

    # Missing miner_id
    msg = attacker.create_message(
        mod.MessageType.ATTESTATION,
        {"ts_ok": int(time.time()), "device_arch": "modern"},
    )
    result = target.handle_message(msg)
    assert result["status"] == "error"
    assert result.get("reason") == "invalid_miner_id"
