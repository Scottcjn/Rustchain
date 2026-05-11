from tools.node_sync_validator import NodeSnapshot, build_summary, compare_snapshots


def make_snapshot(
    node,
    *,
    ok=True,
    error="",
    epoch=1,
    slot=10,
    tip_age_slots=2,
    miners=None,
    balances=None,
):
    return NodeSnapshot(
        node=node,
        ok=ok,
        error=error,
        health={"tip_age_slots": tip_age_slots},
        epoch={"epoch": epoch, "slot": slot},
        miners=list(miners or []),
        balances=dict(balances or {}),
    )


def test_compare_snapshots_reports_down_nodes_and_returns_without_quorum():
    report = compare_snapshots(
        [
            make_snapshot("https://node-a"),
            make_snapshot("https://node-b", ok=False, error="timeout"),
        ],
        tip_drift_threshold=5,
    )

    assert report["down_nodes"] == [{"node": "https://node-b", "error": "timeout"}]
    assert report["discrepancies"]["epoch_mismatch"] == []
    assert report["discrepancies"]["miner_presence_diff"] == []


def test_compare_snapshots_detects_epoch_slot_tip_and_miner_drift():
    report = compare_snapshots(
        [
            make_snapshot(
                "https://node-a",
                epoch=7,
                slot=101,
                tip_age_slots=1,
                miners=["alice", "bob"],
            ),
            make_snapshot(
                "https://node-b",
                epoch=8,
                slot=103,
                tip_age_slots=9,
                miners=["alice"],
            ),
        ],
        tip_drift_threshold=5,
    )

    assert report["discrepancies"]["epoch_mismatch"] == [
        {"https://node-a": 7, "https://node-b": 8}
    ]
    assert report["discrepancies"]["slot_mismatch"] == [
        {"https://node-a": 101, "https://node-b": 103}
    ]
    assert report["discrepancies"]["tip_age_drift"] == [
        {"values": {"https://node-a": 1, "https://node-b": 9}, "drift": 8}
    ]
    assert report["discrepancies"]["miner_presence_diff"] == [
        {
            "miner": "bob",
            "present_on": ["https://node-a"],
            "missing_on": ["https://node-b"],
        }
    ]


def test_compare_snapshots_detects_sampled_balance_mismatch_only_for_common_miners():
    report = compare_snapshots(
        [
            make_snapshot(
                "https://node-a",
                miners=["alice", "bob"],
                balances={"alice": 1.0, "bob": 5.0},
            ),
            make_snapshot(
                "https://node-b",
                miners=["alice", "carol"],
                balances={"alice": 1.0000001, "carol": 2.0},
            ),
        ],
        tip_drift_threshold=5,
    )

    assert report["discrepancies"]["balance_mismatch"] == [
        {"miner": "alice", "balances": {"https://node-a": 1.0, "https://node-b": 1.0000001}}
    ]


def test_build_summary_reports_ok_when_no_discrepancies():
    report = compare_snapshots(
        [
            make_snapshot("https://node-a", miners=["alice"], balances={"alice": 3.0}),
            make_snapshot("https://node-b", miners=["alice"], balances={"alice": 3.0}),
        ],
        tip_drift_threshold=5,
    )

    summary = build_summary(report)

    assert "Nodes checked: https://node-a, https://node-b" in summary
    assert "- balance_mismatch: 0" in summary
    assert "Status: OK (no discrepancies detected)" in summary


def test_build_summary_reports_attention_for_down_nodes():
    report = compare_snapshots(
        [
            make_snapshot("https://node-a"),
            make_snapshot("https://node-b", ok=False, error="connection refused"),
        ],
        tip_drift_threshold=5,
    )

    summary = build_summary(report)

    assert "Down/unreachable nodes:" in summary
    assert "- https://node-b: connection refused" in summary
    assert "Status: ATTENTION (review discrepancy details in JSON)" in summary
