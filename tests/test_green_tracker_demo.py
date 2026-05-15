from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import green_tracker_demo as demo


class FakeGreenTracker:
    instances: list["FakeGreenTracker"] = []

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.registered: list[tuple] = []
        self.sessions: list[tuple] = []
        FakeGreenTracker.instances.append(self)

    def register_machine(
        self,
        machine_id: str,
        name: str,
        arch: str,
        year: int,
        condition: str,
        location: str,
    ) -> dict:
        self.registered.append((machine_id, name, arch, year, condition, location))
        return {"machine_id": machine_id, "name": name, "ewaste_prevented_kg": len(self.registered)}

    def record_mining_session(self, machine_id: str, epoch: int, rtc: float, watts: float) -> dict:
        self.sessions.append((machine_id, epoch, rtc, watts))
        return {"machine_id": machine_id, "epoch": epoch, "rtc_earned": rtc}

    def get_machine_stats(self, machine_id: str) -> dict:
        return {
            "machine_id": machine_id,
            "total_epochs": 3,
            "total_rtc_earned": 7.85,
            "ewaste_prevented_kg": 12.0,
        }

    def get_global_stats(self) -> dict:
        return {
            "total_machines_preserved": len(self.registered),
            "total_mining_sessions": len(self.sessions),
            "total_rtc_earned": 27.3,
        }

    def get_leaderboard(self, limit: int) -> list[dict]:
        return [
            {"name": "IBM POWER8 Server", "arch": "POWER8", "total_rtc": 10.1, "total_epochs": 2},
            {"name": "Power Mac G5", "arch": "G5", "total_rtc": 7.85, "total_epochs": 3},
        ][:limit]

    def get_by_architecture(self, arch: str) -> list[dict]:
        return [{"name": "Power Mac G4 MDD", "location": "Austin, TX", "arch": arch}]

    def export_badge_data(self, machine_id: str) -> dict:
        return {"machine_id": machine_id, "badge": "green", "ewaste_prevented_kg": 12.0}


def test_green_tracker_demo_runs_full_flow_with_in_memory_tracker(monkeypatch, capsys) -> None:
    FakeGreenTracker.instances = []
    monkeypatch.setattr(demo, "GreenTracker", FakeGreenTracker)

    demo.main()

    assert len(FakeGreenTracker.instances) == 1
    tracker = FakeGreenTracker.instances[0]
    assert tracker.db_path == ":memory:"
    assert len(tracker.registered) == 6
    assert tracker.registered[0] == (
        "mac-g5-001",
        "Power Mac G5",
        "G5",
        2004,
        "Good",
        "Berlin, DE",
    )
    assert tracker.registered[-1] == (
        "alpha-006",
        "DEC AlphaStation",
        "Alpha",
        1999,
        "Poor",
        "Sydney, AU",
    )
    assert len(tracker.sessions) == 10
    assert tracker.sessions[0] == ("mac-g5-001", 1001, 2.50, 250.0)
    assert tracker.sessions[-1] == ("alpha-006", 1001, 2.10, 300.0)

    output = capsys.readouterr().out
    assert "=== RustChain Green Tracker Demo ===" in output
    assert "Registering machines preserved from e-waste" in output
    assert "Recording mining sessions" in output
    assert "Machine Stats (Power Mac G5)" in output
    assert "Global Stats" in output
    assert "Leaderboard (top 5)" in output
    assert "G4 Machines" in output
    assert "Badge Data (Power Mac G5)" in output
    assert "6 sessions recorded" not in output
    assert "10 sessions recorded" in output
    assert '"machine_id": "mac-g5-001"' in output
    assert '"badge": "green"' in output
