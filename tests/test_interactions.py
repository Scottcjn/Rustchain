"""
Tests for BoTTube Interaction Tracker (tools/bottube_interactions.py)
"""

import pytest
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from bottube_interactions import InteractionTracker, VALID_TYPES, TYPE_WEIGHTS


@pytest.fixture
def tracker():
    return InteractionTracker()  # in-memory SQLite


# ── record_interaction ────────────────────────────────────────────────────────

class TestRecordInteraction:
    def test_basic_record(self, tracker):
        row_id = tracker.record_interaction("AgentA", "AgentB", "reply", "vid_001")
        assert row_id == 1

    def test_all_valid_types(self, tracker):
        for i, t in enumerate(VALID_TYPES):
            rid = tracker.record_interaction(f"A{i}", f"B{i}", t)
            assert rid > 0

    def test_invalid_type_raises(self, tracker):
        with pytest.raises(ValueError, match="Invalid type"):
            tracker.record_interaction("A", "B", "unknown_type")

    def test_self_interaction_raises(self, tracker):
        with pytest.raises(ValueError, match="must be different"):
            tracker.record_interaction("AgentA", "AgentA", "reply")

    def test_metadata_stored(self, tracker):
        tracker.record_interaction("A", "B", "collab", metadata={"key": "value"})
        history = tracker.get_interaction_history(from_agent="A")
        assert history[0]["metadata"] == {"key": "value"}

    def test_video_id_stored(self, tracker):
        tracker.record_interaction("A", "B", "react", video_id="vid_999")
        history = tracker.get_interaction_history(from_agent="A")
        assert history[0]["video_id"] == "vid_999"


# ── get_agent_graph ───────────────────────────────────────────────────────────

class TestGetAgentGraph:
    def test_empty_graph(self, tracker):
        result = tracker.get_agent_graph("NonExistent")
        assert result["total_connections"] == 0
        assert result["total_interactions"] == 0

    def test_outbound_connections(self, tracker):
        tracker.record_interaction("A", "B", "reply")
        tracker.record_interaction("A", "C", "collab")
        graph = tracker.get_agent_graph("A")
        assert graph["total_connections"] == 2
        assert "B" in graph["connections"]
        assert "C" in graph["connections"]

    def test_inbound_connections(self, tracker):
        tracker.record_interaction("X", "A", "mention")
        graph = tracker.get_agent_graph("A")
        assert "X" in graph["connections"]

    def test_bidirectional_counted_once(self, tracker):
        tracker.record_interaction("A", "B", "reply")
        tracker.record_interaction("B", "A", "reply")
        graph = tracker.get_agent_graph("A")
        # B should appear once, with count=2
        assert graph["connections"]["B"]["count"] == 2

    def test_strength_positive(self, tracker):
        tracker.record_interaction("A", "B", "collab")
        graph = tracker.get_agent_graph("A")
        assert graph["connections"]["B"]["strength"] > 0


# ── get_network_stats ─────────────────────────────────────────────────────────

class TestGetNetworkStats:
    def test_empty_stats(self, tracker):
        stats = tracker.get_network_stats()
        assert stats["total_agents"] == 0
        assert stats["total_interactions"] == 0

    def test_counts_agents(self, tracker):
        tracker.record_interaction("A", "B", "reply")
        tracker.record_interaction("C", "D", "collab")
        stats = tracker.get_network_stats()
        assert stats["total_agents"] == 4
        assert stats["total_interactions"] == 2

    def test_most_connected_present(self, tracker):
        for i in range(5):
            tracker.record_interaction("Hub", f"Spoke{i}", "reply")
        stats = tracker.get_network_stats()
        agents = [e["agent"] for e in stats["most_connected"]]
        assert "Hub" in agents

    def test_most_active_pairs_present(self, tracker):
        for _ in range(5):
            tracker.record_interaction("A", "B", "reply")
        stats = tracker.get_network_stats()
        pairs = [e["agents"] for e in stats["most_active_pairs"]]
        assert ("A", "B") in pairs or ("B", "A") in pairs


# ── get_interaction_history ───────────────────────────────────────────────────

class TestGetInteractionHistory:
    def test_filter_by_from(self, tracker):
        tracker.record_interaction("Alice", "Bob", "reply")
        tracker.record_interaction("Carol", "Bob", "mention")
        hist = tracker.get_interaction_history(from_agent="Alice")
        assert len(hist) == 1
        assert hist[0]["from_agent"] == "Alice"

    def test_filter_by_type(self, tracker):
        tracker.record_interaction("A", "B", "reply")
        tracker.record_interaction("A", "B", "collab")
        hist = tracker.get_interaction_history(type="collab")
        assert all(h["type"] == "collab" for h in hist)

    def test_limit_respected(self, tracker):
        for _ in range(20):
            tracker.record_interaction("A", "B", "react")
        hist = tracker.get_interaction_history(limit=5)
        assert len(hist) == 5

    def test_invalid_type_raises(self, tracker):
        with pytest.raises(ValueError):
            tracker.get_interaction_history(type="bogus")


# ── get_rivalries / get_alliances ─────────────────────────────────────────────

class TestRivalriesAndAlliances:
    def test_rivalries_empty(self, tracker):
        tracker.record_interaction("A", "B", "reply")
        assert tracker.get_rivalries() == []

    def test_rivalries_detected(self, tracker):
        for _ in range(3):
            tracker.record_interaction("A", "B", "challenge")
        rivalries = tracker.get_rivalries()
        assert len(rivalries) == 1
        assert rivalries[0]["challenge_count"] == 3

    def test_alliances_detected(self, tracker):
        for _ in range(4):
            tracker.record_interaction("X", "Y", "collab")
        alliances = tracker.get_alliances()
        assert len(alliances) >= 1
        assert alliances[0]["collab_count"] == 4


# ── export_graph_data ─────────────────────────────────────────────────────────

class TestExportGraphData:
    def test_structure(self, tracker):
        tracker.record_interaction("A", "B", "reply")
        data = tracker.export_graph_data()
        assert "nodes" in data
        assert "links" in data
        assert "meta" in data

    def test_node_count(self, tracker):
        tracker.record_interaction("A", "B", "reply")
        tracker.record_interaction("C", "D", "collab")
        data = tracker.export_graph_data()
        assert data["meta"]["total_nodes"] == 4

    def test_link_weight_positive(self, tracker):
        tracker.record_interaction("A", "B", "collab")
        data = tracker.export_graph_data()
        assert data["links"][0]["weight"] > 0

    def test_empty_export(self, tracker):
        data = tracker.export_graph_data()
        assert data["nodes"] == []
        assert data["links"] == []
