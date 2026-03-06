import sqlite3

import integrated_node


def _seq(values, key):
    return [{"ts": i, "profile": {key: v}} for i, v in enumerate(values, start=1)]


def test_fingerprint_history_keeps_last_10_snapshots(tmp_path):
    db_path = tmp_path / "temporal.db"
    with sqlite3.connect(db_path) as conn:
        for i in range(12):
            fp = {
                "checks": {
                    "clock_drift": {"data": {"cv": 0.02 + i * 0.001}},
                    "thermal_entropy": {"data": {"variance": 2.0 + i * 0.1}},
                    "instruction_jitter": {"data": {"cv": 0.04 + i * 0.001}},
                    "cache_timing": {"data": {"hierarchy_ratio": 3.0 + i * 0.05}},
                }
            }
            integrated_node.append_fingerprint_snapshot(conn, "miner-a", fp, 1_000 + i)

        rows = conn.execute(
            "SELECT ts FROM miner_fingerprint_history WHERE miner=? ORDER BY ts ASC",
            ("miner-a",),
        ).fetchall()

    assert len(rows) == 10
    assert rows[0][0] == 1_002
    assert rows[-1][0] == 1_011


def test_validate_temporal_consistency_real_sequence_passes():
    seq = []
    for i, cv in enumerate([0.015, 0.020, 0.018, 0.022, 0.019, 0.017], start=1):
        seq.append(
            {
                "ts": i,
                "profile": {
                    "clock_drift_cv": cv,
                    "thermal_variance": 2.0 + (i % 3) * 0.2,
                    "jitter_cv": 0.04 + (i % 2) * 0.004,
                    "cache_hierarchy_ratio": 3.2 + (i % 2) * 0.1,
                },
            }
        )

    out = integrated_node.validate_temporal_consistency(seq)
    assert out["review_flag"] is False
    assert out["score"] >= 0.9


def test_validate_temporal_consistency_frozen_sequence_flagged():
    seq = []
    for i in range(1, 7):
        seq.append(
            {
                "ts": i,
                "profile": {
                    "clock_drift_cv": 0.02,
                    "thermal_variance": 2.5,
                    "jitter_cv": 0.03,
                    "cache_hierarchy_ratio": 3.4,
                },
            }
        )

    out = integrated_node.validate_temporal_consistency(seq)
    assert out["review_flag"] is True
    assert any(flag.startswith("frozen_profile") for flag in out["flags"])


def test_validate_temporal_consistency_noisy_sequence_flagged():
    seq = []
    noisy_clock = [0.002, 0.25, 0.004, 0.29, 0.003, 0.27]
    noisy_thermal = [0.1, 18.0, 0.2, 16.0, 0.15, 20.0]
    for i, (cv, thermal) in enumerate(zip(noisy_clock, noisy_thermal), start=1):
        seq.append(
            {
                "ts": i,
                "profile": {
                    "clock_drift_cv": cv,
                    "thermal_variance": thermal,
                    "jitter_cv": 0.02 if i % 2 else 0.3,
                    "cache_hierarchy_ratio": 3.0 if i % 2 else 9.0,
                },
            }
        )

    out = integrated_node.validate_temporal_consistency(seq)
    assert out["review_flag"] is True
    assert any(flag.startswith("noisy_profile") for flag in out["flags"])
