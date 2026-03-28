"""
test_green_tracker.py — Unit tests for GreenTracker
Bounty #2218
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from green_tracker import GreenTracker, EWASTE_WEIGHTS_KG, NEW_HARDWARE_CO2_KG


@pytest.fixture
def tracker():
    return GreenTracker(":memory:")


@pytest.fixture
def populated(tracker):
    tracker.register_machine("g5-001", "Power Mac G5", "G5", 2004, "Good", "Berlin")
    tracker.register_machine("g4-001", "Power Mac G4", "G4", 2002, "Fair", "Austin")
    tracker.register_machine("p8-001", "IBM POWER8",   "POWER8", 2014, "Excellent", "London")
    tracker.register_machine("rpi-001", "Raspberry Pi", "RPi", 2018, "Good", "Tokyo")
    tracker.record_mining_session("g5-001", 1, 2.5, 250.0)
    tracker.record_mining_session("g5-001", 2, 3.0, 255.0)
    tracker.record_mining_session("g4-001", 1, 1.8, 180.0)
    tracker.record_mining_session("p8-001", 1, 5.0, 500.0)
    return tracker


class TestRegisterMachine:
    def test_register_returns_dict(self, tracker):
        result = tracker.register_machine("m1", "Test Mac", "G5", 2004, "Good", "NYC")
        assert result["machine_id"] == "m1"
        assert result["name"] == "Test Mac"
        assert result["ewaste_prevented_kg"] == EWASTE_WEIGHTS_KG["G5"]

    def test_register_with_photo_url(self, tracker):
        result = tracker.register_machine(
            "m2", "Photo Mac", "G4", 2002, "Fair", "LA",
            photo_url="https://example.com/mac.jpg"
        )
        assert result["machine_id"] == "m2"

    def test_register_duplicate_replaces(self, tracker):
        tracker.register_machine("dup", "Old Name", "G4", 2002, "Poor", "NYC")
        tracker.register_machine("dup", "New Name", "G5", 2004, "Good", "LA")
        stats = tracker.get_machine_stats("dup")
        assert stats["name"] == "New Name"
        assert stats["arch"] == "G5"


class TestRecordMiningSession:
    def test_session_recorded(self, tracker):
        tracker.register_machine("m1", "Mac", "G4", 2002, "Good", "X")
        result = tracker.record_mining_session("m1", 42, 1.5, 200.0)
        assert result["machine_id"] == "m1"
        assert result["epoch"] == 42
        assert result["rtc_earned"] == 1.5


class TestGetMachineStats:
    def test_stats_totals(self, populated):
        stats = populated.get_machine_stats("g5-001")
        assert stats["total_epochs"] == 2
        assert abs(stats["total_rtc_earned"] - 5.5) < 0.001

    def test_ewaste_field(self, populated):
        stats = populated.get_machine_stats("g5-001")
        assert stats["ewaste_prevented_kg"] == EWASTE_WEIGHTS_KG["G5"]

    def test_co2_saved_non_negative(self, populated):
        stats = populated.get_machine_stats("rpi-001")
        assert stats["co2_saved_kg"] >= 0.0

    def test_unknown_machine_raises(self, tracker):
        with pytest.raises(ValueError, match="not found"):
            tracker.get_machine_stats("nonexistent")


class TestGetGlobalStats:
    def test_global_counts(self, populated):
        g = populated.get_global_stats()
        assert g["total_machines_preserved"] == 4
        assert g["total_mining_sessions"] == 4
        assert g["total_rtc_earned"] > 0
        assert g["total_ewaste_prevented_kg"] > 0
        assert g["total_co2_saved_kg"] >= 0

    def test_empty_db(self, tracker):
        g = tracker.get_global_stats()
        assert g["total_machines_preserved"] == 0
        assert g["total_rtc_earned"] == 0.0


class TestGetLeaderboard:
    def test_leaderboard_order(self, populated):
        lb = populated.get_leaderboard(10)
        rtcs = [e["total_rtc"] for e in lb]
        assert rtcs == sorted(rtcs, reverse=True)

    def test_leaderboard_limit(self, populated):
        lb = populated.get_leaderboard(2)
        assert len(lb) <= 2

    def test_leaderboard_top_is_g5(self, populated):
        lb = populated.get_leaderboard(10)
        assert lb[0]["machine_id"] == "g5-001"


class TestGetByArchitecture:
    def test_filter_g4(self, populated):
        results = populated.get_by_architecture("G4")
        assert len(results) == 1
        assert results[0]["machine_id"] == "g4-001"

    def test_filter_no_match(self, populated):
        results = populated.get_by_architecture("MIPS")
        assert results == []


class TestEstimateEwaste:
    def test_known_archs(self, tracker):
        assert tracker.estimate_ewaste_prevented({"arch": "G4"}) == 8.0
        assert tracker.estimate_ewaste_prevented({"arch": "G5"}) == 12.0
        assert tracker.estimate_ewaste_prevented({"arch": "POWER8"}) == 25.0
        assert tracker.estimate_ewaste_prevented({"arch": "RPi"}) == 0.1

    def test_unknown_arch_uses_default(self, tracker):
        result = tracker.estimate_ewaste_prevented({"arch": "UNKNOWN_ARCH"})
        assert result == EWASTE_WEIGHTS_KG["default"]


class TestExportBadgeData:
    def test_badge_structure(self, populated):
        badge = populated.export_badge_data("g5-001")
        assert badge["badge"] == "Preserved from E-Waste"
        assert "machine" in badge
        assert "impact" in badge
        assert "metadata" in badge
        assert badge["machine"]["id"] == "g5-001"
        assert badge["impact"]["ewaste_prevented_kg"] == EWASTE_WEIGHTS_KG["G5"]
        assert badge["impact"]["total_rtc_earned"] > 0

    def test_badge_description_contains_name(self, populated):
        badge = populated.export_badge_data("g5-001")
        assert "Power Mac G5" in badge["metadata"]["description"]
