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
