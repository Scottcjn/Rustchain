# SPDX-License-Identifier: MIT

from tools import node_sync_validator as validator


def _snapshot(node, *, ok=True, error="", epoch=1, slot=1, tip=0, miners=None, balances=None):
    return validator.NodeSnapshot(
        node=node,
        ok=ok,
        error=error,
        health={"tip_age_slots": tip} if ok else {},
        epoch={"epoch": epoch, "slot": slot} if ok else {},
        miners=miners or [],
        balances=balances or {},
    )


def test_compare_snapshots_reports_cross_node_discrepancies(monkeypatch):
    monkeypatch.setattr(validator.time, "time", lambda: 1234)

    report = validator.compare_snapshots(
        [
            _snapshot("node-a", epoch=7, slot=10, tip=1, miners=["shared", "only-a"], balances={"shared": 1.0}),
            _snapshot("node-b", epoch=8, slot=11, tip=9, miners=["shared", "only-b"], balances={"shared": 1.5}),
            _snapshot("node-down", ok=False, error="timeout"),
        ],
        tip_drift_threshold=5,
    )

    assert report["generated_at"] == 1234
    assert report["down_nodes"] == [{"node": "node-down", "error": "timeout"}]
    assert report["discrepancies"]["epoch_mismatch"] == [{"node-a": 7, "node-b": 8}]
    assert report["discrepancies"]["slot_mismatch"] == [{"node-a": 10, "node-b": 11}]
    assert report["discrepancies"]["tip_age_drift"] == [{"values": {"node-a": 1, "node-b": 9}, "drift": 8}]
    assert {"miner": "only-a", "present_on": ["node-a"], "missing_on": ["node-b"]} in report["discrepancies"]["miner_presence_diff"]
    assert report["discrepancies"]["balance_mismatch"] == [{"miner": "shared", "balances": {"node-a": 1.0, "node-b": 1.5}}]


def test_compare_snapshots_with_single_live_node_only_reports_down_nodes(monkeypatch):
    monkeypatch.setattr(validator.time, "time", lambda: 99)

    report = validator.compare_snapshots(
        [
            _snapshot("node-a", epoch=3, slot=4, miners=["miner-a"]),
            _snapshot("node-b", ok=False, error="connection refused"),
        ],
        tip_drift_threshold=1,
    )

    assert report["generated_at"] == 99
    assert report["down_nodes"] == [{"node": "node-b", "error": "connection refused"}]
    assert all(not values for values in report["discrepancies"].values())


def test_snapshot_node_samples_balances_and_records_balance_failures(monkeypatch):
    def fake_get_json(base, endpoint, timeout, verify_ssl):
        assert base == "https://node.example"
        assert timeout == 2.5
        assert verify_ssl is True
        if endpoint == "/health":
            return {"tip_age_slots": 0}
        if endpoint == "/epoch":
            return {"epoch": 2, "slot": 10}
        if endpoint == "/api/miners":
            return [{"miner": "miner-a"}, {"miner_id": "miner-b"}, {"miner": ""}]
        if endpoint == "/wallet/balance?miner_id=miner-a":
            return {"amount_rtc": "4.25"}
        if endpoint == "/wallet/balance?miner_id=miner-b":
            raise RuntimeError("balance timeout")
        raise AssertionError(endpoint)

    monkeypatch.setattr(validator, "get_json", fake_get_json)

    snap = validator.snapshot_node("https://node.example", timeout=2.5, verify_ssl=True, sample_balances=2)

    assert snap.ok is True
    assert snap.health == {"tip_age_slots": 0}
    assert snap.epoch == {"epoch": 2, "slot": 10}
    assert snap.miners == ["miner-a", "miner-b"]
    assert snap.balances == {"miner-a": 4.25, "miner-b": -1.0}


def test_build_summary_reports_ok_and_attention_statuses():
    ok_report = {
        "generated_at": 1,
        "nodes": ["node-a", "node-b"],
        "down_nodes": [],
        "discrepancies": {
            "epoch_mismatch": [],
            "slot_mismatch": [],
            "tip_age_drift": [],
            "miner_presence_diff": [],
            "balance_mismatch": [],
        },
    }
    attention_report = {
        **ok_report,
        "down_nodes": [{"node": "node-b", "error": "timeout"}],
    }

    assert "Status: OK (no discrepancies detected)" in validator.build_summary(ok_report)
    attention = validator.build_summary(attention_report)
    assert "Down/unreachable nodes:" in attention
    assert "Status: ATTENTION (review discrepancy details in JSON)" in attention
