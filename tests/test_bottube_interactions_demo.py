from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import bottube_interactions_demo as demo


class FakeInteractionTracker:
    instances: list["FakeInteractionTracker"] = []

    def __init__(self) -> None:
        self.interactions: list[dict] = []
        FakeInteractionTracker.instances.append(self)

    def record_interaction(
        self,
        *,
        from_agent: str,
        to_agent: str,
        type: str,
        video_id: str,
        metadata: dict,
    ) -> None:
        self.interactions.append(
            {
                "from_agent": from_agent,
                "to_agent": to_agent,
                "type": type,
                "video_id": video_id,
                "metadata": metadata,
            }
        )

    def get_network_stats(self) -> dict:
        return {
            "total_agents": 10,
            "total_interactions": len(self.interactions),
            "most_connected": [
                {"agent": "AlphaBot", "unique_peers": 9},
                {"agent": "BetaNode", "unique_peers": 8},
            ],
            "most_active_pairs": [
                {"agents": ("AlphaBot", "BetaNode"), "count": 11},
            ],
        }

    def get_alliances(self, top_n: int) -> list[dict]:
        return [
            {
                "agents": ("AlphaBot", "GammaRig"),
                "collab_count": 4,
                "reply_count": 6,
                "strength": 0.75,
            }
        ][:top_n]

    def get_rivalries(self, top_n: int) -> list[dict]:
        return [
            {
                "agents": ("DeltaMiner", "KappaNet"),
                "challenge_count": 3,
                "strength": 0.5,
            }
        ][:top_n]

    def get_agent_graph(self, agent: str) -> dict:
        return {
            "agent": agent,
            "total_connections": 2,
            "total_interactions": 7,
            "connections": {
                "BetaNode": {"count": 5, "strength": 0.9, "types": ["reply", "collab"]},
                "GammaRig": {"count": 2, "strength": 0.4, "types": ["like"]},
            },
        }

    def export_graph_data(self) -> dict:
        return {"meta": {"total_nodes": 10, "total_links": 21}}


def test_interactions_demo_records_seeded_interactions_and_prints_analysis(monkeypatch, capsys) -> None:
    FakeInteractionTracker.instances = []
    monkeypatch.setattr(demo, "InteractionTracker", FakeInteractionTracker)

    demo.run_demo()

    assert len(FakeInteractionTracker.instances) == 1
    tracker = FakeInteractionTracker.instances[0]
    assert len(tracker.interactions) == 200
    for interaction in tracker.interactions:
        assert interaction["from_agent"] in demo.AGENTS
        assert interaction["to_agent"] in demo.AGENTS
        assert interaction["from_agent"] != interaction["to_agent"]
        assert interaction["type"] in demo.TYPES
        assert interaction["video_id"] in demo.VIDEO_IDS
        assert interaction["metadata"] == {"session": "demo"}

    output = capsys.readouterr().out
    assert "BoTTube Agent Interaction Tracker" in output
    assert "Simulating 200 random agent interactions" in output
    assert "Total agents     : 10" in output
    assert "Total interactions: 200" in output
    assert "Most Connected Agents" in output
    assert "Most Active Pairs" in output
    assert "Top Alliances" in output
    assert "Top Rivalries" in output
    assert "Agent Graph: AlphaBot" in output
    assert "Nodes: 10" in output
    assert "Links: 21" in output
    assert "Demo complete." in output
