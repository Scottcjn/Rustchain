# SPDX-License-Identifier: MIT

import threading
import time

from agent_relationships import DramaArcType
from drama_arc_engine import DramaArcEngine


class SlowRelationshipEngine:
    def __init__(self):
        self.start_count = 0
        self.relationship = {
            "agent_a": "alice",
            "agent_b": "bob",
            "arc_type": DramaArcType.FRIENDLY_RIVALRY.value,
            "arc_start_time": time.time(),
            "state": "rivals",
            "tension_level": 10,
            "trust_level": 50,
        }

    def start_drama_arc(self, agent_a, agent_b, arc_type):
        time.sleep(0.02)
        self.start_count += 1
        return {"success": True, "relationship": dict(self.relationship)}

    def get_relationship(self, agent_a, agent_b):
        return dict(self.relationship)


def test_start_arc_is_idempotent_under_concurrent_calls():
    rel_engine = SlowRelationshipEngine()
    engine = DramaArcEngine(rel_engine)
    callbacks = []
    barrier = threading.Barrier(8)
    results = []

    engine.register_callback(lambda event, payload: callbacks.append((event, payload)))

    def start_same_arc():
        barrier.wait()
        results.append(
            engine.start_arc("alice", "bob", DramaArcType.FRIENDLY_RIVALRY)
        )

    threads = [threading.Thread(target=start_same_arc) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(results) == 8
    assert all(result["success"] for result in results)
    assert rel_engine.start_count == 1
    assert len(engine.get_all_active_arcs()) == 1
    assert sum(1 for result in results if result.get("idempotent")) == 7
    assert [event for event, _payload in callbacks] == ["arc_started"]
