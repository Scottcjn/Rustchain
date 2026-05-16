# SPDX-License-Identifier: MIT
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import node_sync_validator
from node_sync_validator import NodeSnapshot


def _snap(node, *, ok=True, error="", epoch=1, slot=10, tip_age=2, miners=None, balances=None):
    return NodeSnapshot(
        node=node,
        ok=ok,
        error=error,
        health={"tip_age_slots": tip_age} if ok else {},
        epoch={"epoch": epoch, "slot": slot} if ok else {},
        miners=list(miners or []),
        balances=dict(balances or {}),
    )


def test_compare_snapshots_reports_down_nodes_when_not_enough_online_nodes(monkeypatch):
    monkeypatch.setattr(node_sync_validator.time, "time", lambda: 12345)
    report = node_sync_validator.compare_snapshots(
        [_snap("a"), _snap("b", ok=False, error="timeout")],
        tip_drift_threshold=5,
    )

    assert report["generated_at"] == 12345
    assert report["nodes"] == ["a", "b"]
    assert report["down_nodes"] == [{"node": "b", "error": "timeout"}]
    assert all(not values for values in report["discrepancies"].values())


def test_compare_snapshots_detects_epoch_slot_tip_miner_and_balance_mismatches(monkeypatch):
    monkeypatch.setattr(node_sync_validator.time, "time", lambda: 99)
    report = node_sync_validator.compare_snapshots(
        [
            _snap("a", epoch=1, slot=10, tip_age=1, miners=["alice", "bob"], balances={"alice": 1.0}),
            _snap("b", epoch=2, slot=11, tip_age=9, miners=["alice"], balances={"alice": 1.5}),
        ],
        tip_drift_threshold=5,
    )
    d = report["discrepancies"]

    assert d["epoch_mismatch"] == [{"a": 1, "b": 2}]
    assert d["slot_mismatch"] == [{"a": 10, "b": 11}]
    assert d["tip_age_drift"] == [{"values": {"a": 1, "b": 9}, "drift": 8}]
    assert d["miner_presence_diff"] == [{"miner": "bob", "present_on": ["a"], "missing_on": ["b"]}]
    assert d["balance_mismatch"] == [{"miner": "alice", "balances": {"a": 1.0, "b": 1.5}}]


def test_compare_snapshots_ignores_failed_balance_samples():
    report = node_sync_validator.compare_snapshots(
        [
            _snap("a", miners=["alice"], balances={"alice": -1.0}),
            _snap("b", miners=["alice"], balances={"alice": 2.0}),
        ],
        tip_drift_threshold=5,
    )

    assert report["discrepancies"]["balance_mismatch"] == []


def test_build_summary_reports_ok_when_no_discrepancies():
    summary = node_sync_validator.build_summary(
        {
            "generated_at": 123,
            "nodes": ["a", "b"],
            "down_nodes": [],
            "discrepancies": {
                "epoch_mismatch": [],
                "slot_mismatch": [],
                "tip_age_drift": [],
                "miner_presence_diff": [],
                "balance_mismatch": [],
            },
        }
    )

    assert "Generated at: 123" in summary
    assert "Nodes checked: a, b" in summary
    assert "- epoch_mismatch: 0" in summary
    assert "Status: OK (no discrepancies detected)" in summary


def test_build_summary_reports_attention_for_down_nodes_and_discrepancies():
    summary = node_sync_validator.build_summary(
        {
            "generated_at": 123,
            "nodes": ["a", "b"],
            "down_nodes": [{"node": "b", "error": "timeout"}],
            "discrepancies": {
                "epoch_mismatch": [{"a": 1, "b": 2}],
                "slot_mismatch": [],
                "tip_age_drift": [],
                "miner_presence_diff": [],
                "balance_mismatch": [],
            },
        }
    )

    assert "Down/unreachable nodes:" in summary
    assert "- b: timeout" in summary
    assert "- epoch_mismatch: 1" in summary
    assert "Status: ATTENTION (review discrepancy details in JSON)" in summary
