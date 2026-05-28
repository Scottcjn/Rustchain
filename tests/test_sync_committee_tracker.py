# SPDX-License-Identifier: MIT
"""Tests for the sync committee rotation tracker."""

from pathlib import Path

from tools.sync_committee_tracker.sync_committee_tracker import (
    CommitteeHistory,
    build_snapshot,
    normalize_miners,
    render_metrics,
    select_committee,
)


def test_normalize_miners_accepts_common_payload_shapes():
    payload = {
        "miners": [
            {"miner_id": "RTC2", "device_arch": "g4", "weight": 2},
            {"miner_pk": "RTC1", "arch": "modern", "multiplier": 1.5},
            {"miner": "RTC3", "device_arch": "POWER8"},
            {"wallet": "", "arch": "ignored"},
            {"address": "RTC2", "arch": "duplicate", "weight": 4},
        ]
    }

    miners = normalize_miners(payload)

    assert [miner.miner_id for miner in miners] == ["RTC1", "RTC2", "RTC3"]
    assert miners[0].arch == "modern"
    assert miners[1].weight == 4
    assert miners[2].arch == "POWER8"


def test_committee_selection_is_stable_for_epoch():
    miners = normalize_miners(
        [{"miner_id": f"RTC{i}", "device_arch": "test"} for i in range(12)]
    )

    first = select_committee(miners, epoch=42, committee_size=4)
    second = select_committee(list(reversed(miners)), epoch=42, committee_size=4)

    assert [miner.miner_id for miner in first] == [miner.miner_id for miner in second]
    assert len(first) == 4


def test_build_snapshot_includes_dashboard_metrics():
    snapshot = build_snapshot(
        {"epoch": 10, "slot": 25, "blocks_per_epoch": 100},
        [{"miner_id": f"RTC{i}", "device_arch": "test"} for i in range(4)],
        committee_size=3,
        observed_at=123,
    )

    assert snapshot["epoch"] == 10
    assert snapshot["committee_size"] == 3
    assert snapshot["active_miners"] == 4
    assert snapshot["next_rotation_epoch"] == 11
    assert snapshot["slots_until_rotation"] == 75
    assert [member["position"] for member in snapshot["committee"]] == [1, 2, 3]


def test_history_records_latest_and_change_status(tmp_path: Path):
    db = tmp_path / "history.db"
    history = CommitteeHistory(db)
    snapshot = build_snapshot(
        {"epoch": 1, "slot": 2, "blocks_per_epoch": 10},
        [{"miner_id": "RTC1"}, {"miner_id": "RTC2"}],
        observed_at=100,
    )

    assert history.record(snapshot) is True
    assert history.record(snapshot) is False
    latest = history.latest()

    assert latest is not None
    assert latest["epoch"] == 1
    assert latest["committee"] == snapshot["committee"]


def test_render_metrics_exposes_rotation_values():
    snapshot = build_snapshot(
        {"epoch": 3, "slot": 8, "blocks_per_epoch": 10},
        [{"miner_id": "RTC1", "device_arch": "g4"}],
        observed_at=100,
    )

    metrics = render_metrics(snapshot)

    assert "rustchain_sync_committee_epoch 3" in metrics
    assert "rustchain_sync_committee_slots_until_rotation 2" in metrics
    assert 'rustchain_sync_committee_position{miner="RTC1",arch="g4"} 1' in metrics
