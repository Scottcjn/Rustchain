# SPDX-License-Identifier: MIT
"""Unit tests for the cross-node sync validator helpers."""

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "tools" / "node_sync_validator.py"


def load_module():
    spec = importlib.util.spec_from_file_location("node_sync_validator", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def snapshot(module, node, *, epoch=1, slot=10, tip_age=0, miners=None, balances=None, ok=True, error=""):
    return module.NodeSnapshot(
        node=node,
        ok=ok,
        error=error,
        health={"tip_age_slots": tip_age},
        epoch={"epoch": epoch, "slot": slot},
        miners=list(miners or []),
        balances=dict(balances or {}),
    )


def test_normalize_miners_response_accepts_paginated_api_shape():
    module = load_module()

    miners, total, miner_hash = module.normalize_miners_response({
        "miners": [
            {"miner": "alice"},
            {"miner_id": "bob"},
            {"wallet": "carol"},
            {"miner": ""},
        ],
        "pagination": {"count": 3, "limit": 100, "offset": 0, "total": 42},
    })

    assert miners == ["alice", "bob", "carol"]
    assert total == 42
    assert miner_hash == module.stable_miner_set_hash(["carol", "alice", "bob"])


def test_snapshot_node_fetches_stats_and_paginated_miner_totals(monkeypatch):
    module = load_module()

    def fake_get_json(node, endpoint, timeout, verify_ssl):
        assert node == "https://node-a"
        assert timeout == 1.5
        assert verify_ssl is False
        return {
            "/health": {"tip_age_slots": 0},
            "/epoch": {"epoch": 7, "slot": 99, "enrolled_miners": 2},
            "/api/miners": {
                "miners": [{"miner": "alice"}, {"miner": "bob"}],
                "pagination": {"total": 2},
            },
            "/api/stats": {"epoch": 7, "total_miners": 2, "total_balance": 19.5},
        }[endpoint]

    monkeypatch.setattr(module, "get_json", fake_get_json)

    snap = module.snapshot_node("https://node-a", timeout=1.5, verify_ssl=False, sample_balances=0)

    assert snap.ok is True
    assert snap.miners == ["alice", "bob"]
    assert snap.miner_total == 2
    assert snap.miner_set_hash == module.stable_miner_set_hash(["bob", "alice"])
    assert snap.stats == {"epoch": 7, "total_miners": 2, "total_balance": 19.5}


def test_compare_snapshots_records_down_nodes_without_false_discrepancies():
    module = load_module()

    report = module.compare_snapshots([
        snapshot(module, "https://node-a", miners=["m1"]),
        snapshot(module, "https://node-b", ok=False, error="timeout"),
    ], tip_drift_threshold=5)

    assert report["down_nodes"] == [{"node": "https://node-b", "error": "timeout"}]
    assert report["discrepancies"]["epoch_mismatch"] == []
    assert report["discrepancies"]["miner_presence_diff"] == []


def test_compare_snapshots_detects_epoch_slot_and_tip_drift():
    module = load_module()

    report = module.compare_snapshots([
        snapshot(module, "n1", epoch=4, slot=100, tip_age=1),
        snapshot(module, "n2", epoch=5, slot=103, tip_age=9),
    ], tip_drift_threshold=5)

    assert report["discrepancies"]["epoch_mismatch"] == [{"n1": 4, "n2": 5}]
    assert report["discrepancies"]["slot_mismatch"] == [{"n1": 100, "n2": 103}]
    assert report["discrepancies"]["tip_age_drift"] == [
        {"values": {"n1": 1, "n2": 9}, "drift": 8}
    ]


def test_compare_snapshots_reports_miner_presence_and_balance_differences():
    module = load_module()

    report = module.compare_snapshots([
        snapshot(module, "n1", miners=["alice", "bob"], balances={"alice": 10.0, "bob": 5.0}),
        snapshot(module, "n2", miners=["alice"], balances={"alice": 12.0}),
    ], tip_drift_threshold=5)

    assert report["discrepancies"]["miner_presence_diff"] == [
        {"miner": "bob", "present_on": ["n1"], "missing_on": ["n2"]}
    ]
    assert report["discrepancies"]["balance_mismatch"] == [
        {"miner": "alice", "balances": {"n1": 10.0, "n2": 12.0}}
    ]


def test_compare_snapshots_reports_same_epoch_miner_and_stats_drift():
    module = load_module()

    left = snapshot(module, "n1", epoch=167, slot=24091, miners=["alice", "bob"])
    left.epoch["enrolled_miners"] = 13
    left.miner_total = 12
    left.miner_set_hash = module.stable_miner_set_hash(left.miners)
    left.stats = {"epoch": 167, "total_miners": 719, "total_balance": 439878.132361}

    right = snapshot(module, "n2", epoch=167, slot=24091, miners=[])
    right.epoch["enrolled_miners"] = 0
    right.miner_total = 0
    right.miner_set_hash = module.stable_miner_set_hash(right.miners)
    right.stats = {"epoch": 167, "total_miners": 388, "total_balance": 539252.318562}

    report = module.compare_snapshots([left, right], tip_drift_threshold=5)

    assert report["discrepancies"]["epoch_mismatch"] == []
    assert report["discrepancies"]["slot_mismatch"] == []
    assert report["discrepancies"]["enrolled_miners_mismatch"] == [{"n1": 13, "n2": 0}]
    assert report["discrepancies"]["miner_count_mismatch"] == [{"n1": 12, "n2": 0}]
    assert report["discrepancies"]["miner_set_hash_mismatch"] == [
        {
            "n1": module.stable_miner_set_hash(["alice", "bob"]),
            "n2": module.stable_miner_set_hash([]),
        }
    ]
    assert report["discrepancies"]["stats_total_miners_mismatch"] == [{"n1": 719, "n2": 388}]
    assert report["discrepancies"]["stats_total_balance_mismatch"] == [
        {"n1": 439878.132361, "n2": 539252.318562}
    ]


def test_compare_snapshots_ignores_negative_missing_balance_samples():
    module = load_module()

    report = module.compare_snapshots([
        snapshot(module, "n1", miners=["alice"], balances={"alice": -1.0}),
        snapshot(module, "n2", miners=["alice"], balances={"alice": 3.0}),
    ], tip_drift_threshold=5)

    assert report["discrepancies"]["balance_mismatch"] == []


def test_build_summary_marks_clean_and_attention_reports():
    module = load_module()
    clean = module.compare_snapshots([
        snapshot(module, "n1", miners=["alice"], balances={"alice": 3.0}),
        snapshot(module, "n2", miners=["alice"], balances={"alice": 3.0}),
    ], tip_drift_threshold=5)
    dirty = module.compare_snapshots([
        snapshot(module, "n1", miners=["alice"]),
        snapshot(module, "n2", ok=False, error="refused"),
    ], tip_drift_threshold=5)

    assert "Status: OK (no discrepancies detected)" in module.build_summary(clean)
    assert "Down/unreachable nodes:" in module.build_summary(dirty)
    assert "Status: ATTENTION (review discrepancy details in JSON)" in module.build_summary(dirty)
