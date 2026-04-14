"""Regression test for P2P epoch vote spoofing (Rustchain #2256, credit @yuzengbaao #2247)."""
import importlib.util
import os
import sqlite3
import tempfile
from pathlib import Path

os.environ.setdefault("RC_P2P_SECRET", "unit-test-secret-0123456789abcdef")

MODULE_PATH = Path(__file__).resolve().parents[1] / "node" / "rustchain_p2p_gossip.py"
spec = importlib.util.spec_from_file_location("rustchain_p2p_gossip", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _db() -> str:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE miner_attest_recent "
            "(miner TEXT, ts_ok INTEGER, device_family TEXT, "
            "device_arch TEXT, entropy_score INTEGER)"
        )
        conn.execute("CREATE TABLE epoch_state (epoch INTEGER, settled INTEGER)")
    return path


def test_epoch_vote_spoof_does_not_count_as_multiple_voters():
    db_path = _db()
    target = mod.GossipLayer(
        "node1",
        {"node2": "http://n2", "node3": "http://n3", "node4": "http://n4"},
        db_path=db_path,
    )
    attacker = mod.GossipLayer("node2", {}, db_path=db_path)
    target.broadcast = lambda *args, **kwargs: None

    first = attacker.create_message(
        mod.MessageType.EPOCH_VOTE,
        {"epoch": 7, "proposal_hash": "abc123", "vote": "accept", "voter": "node2"},
    )
    spoofed_1 = attacker.create_message(
        mod.MessageType.EPOCH_VOTE,
        {"epoch": 7, "proposal_hash": "abc123", "vote": "accept", "voter": "node3"},
    )
    spoofed_2 = attacker.create_message(
        mod.MessageType.EPOCH_VOTE,
        {"epoch": 7, "proposal_hash": "abc123", "vote": "accept", "voter": "node4"},
    )

    assert target.handle_message(first)["status"] == "ok"
    assert target.handle_message(spoofed_1)["status"] == "duplicate"
    assert target.handle_message(spoofed_2)["status"] == "duplicate"
    assert target._epoch_votes[7] == {"node2": "accept"}
    assert not target.epoch_crdt.contains(7)
