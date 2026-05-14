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
