# SPDX-License-Identifier: MIT

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "node"))

import pytest

from rustchain_p2p_gossip import GOSSIP_TTL, GossipMessage, MessageType


def _message(payload):
    return {
        "msg_type": MessageType.PING.value,
        "msg_id": "msg-oversized-payload-demo",
        "sender_id": "node-a",
        "timestamp": int(time.time()),
        "ttl": GOSSIP_TTL,
        "signature": "invalid",
        "payload": payload,
    }


def test_gossip_from_dict_rejects_oversized_payload_before_signature_work():
    payload = {f"k{i:05d}": "x" * 1024 for i in range(5000)}

    with pytest.raises(ValueError, match="too many keys|serialized size"):
        GossipMessage.from_dict(_message(payload))



def test_gossip_from_dict_rejects_oversized_list_payload():
    payload = {"items": ["x" * 4096 for _ in range(256)]}

    with pytest.raises(ValueError, match="serialized size"):
        GossipMessage.from_dict(_message(payload))

def test_gossip_from_dict_accepts_small_payload():
    msg = GossipMessage.from_dict(_message({"ping": "pong"}))

    assert msg.payload == {"ping": "pong"}
