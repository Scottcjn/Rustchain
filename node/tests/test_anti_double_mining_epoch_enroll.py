# SPDX-License-Identifier: MIT
#!/usr/bin/env python3
"""Unit coverage for anti_double_mining epoch_enroll fallback paths."""

import json
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from anti_double_mining import detect_duplicate_identities, get_epoch_miner_groups


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE epoch_enroll (epoch INTEGER, miner_pk TEXT)")
    conn.execute(
        "CREATE TABLE miner_attest_recent ("
        "miner TEXT PRIMARY KEY, device_arch TEXT, ts_ok INTEGER, "
        "fingerprint_passed INTEGER DEFAULT 1, entropy_score REAL)"
    )
    conn.execute(
        "CREATE TABLE miner_fingerprint_history ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, miner TEXT, ts INTEGER, profile_json TEXT)"
    )
    return conn


def _profile(serial):
    return json.dumps({"checks": {"cpu_serial": {"data": {"serial": serial}}}})


def test_detect_duplicates_prefers_epoch_enroll_when_attestation_is_stale():
    conn = _conn()
    for miner in ("miner-a", "miner-b"):
        conn.execute("INSERT INTO epoch_enroll VALUES (?, ?)", (7, miner))
        conn.execute(
            "INSERT INTO miner_attest_recent VALUES (?, ?, ?, ?, ?)",
            (miner, "g4", 1, 1, 0.5),
        )
        conn.execute(
            "INSERT INTO miner_fingerprint_history (miner, ts, profile_json) VALUES (?, ?, ?)",
            (miner, 99, _profile("same-machine")),
        )
    conn.commit()

    duplicates = detect_duplicate_identities(conn, 7, epoch_start_ts=1000, epoch_end_ts=2000)

    assert len(duplicates) == 1
    assert set(duplicates[0].associated_miner_ids) == {"miner-a", "miner-b"}


def test_get_epoch_miner_groups_uses_epoch_enroll_for_stale_attestations():
    conn = _conn()
    rows = [
        ("miner-a", "same-machine"),
        ("miner-b", "same-machine"),
        ("miner-c", "other-machine"),
    ]
    for miner, serial in rows:
        conn.execute("INSERT INTO epoch_enroll VALUES (?, ?)", (3, miner))
        conn.execute(
            "INSERT INTO miner_attest_recent VALUES (?, ?, ?, ?, ?)",
            (miner, "g4", 1, 1, 0.5),
        )
        conn.execute(
            "INSERT INTO miner_fingerprint_history (miner, ts, profile_json) VALUES (?, ?, ?)",
            (miner, 99, _profile(serial)),
        )
    conn.commit()

    groups = get_epoch_miner_groups(conn, 3)

    group_sets = [set(v) for v in groups.values()]
    assert {"miner-a", "miner-b"} in group_sets
    assert {"miner-c"} in group_sets


def test_get_epoch_miner_groups_falls_back_to_attestation_window_without_enroll():
    from anti_double_mining import GENESIS_TIMESTAMP

    conn = _conn()
    conn.execute(
        "INSERT INTO miner_attest_recent VALUES (?, ?, ?, ?, ?)",
        ("miner-a", "g4", GENESIS_TIMESTAMP + 60, 1, 0.5),
    )
    conn.execute(
        "INSERT INTO miner_fingerprint_history (miner, ts, profile_json) VALUES (?, ?, ?)",
        ("miner-a", 99, _profile("fallback-machine")),
    )
    conn.commit()

    groups = get_epoch_miner_groups(conn, 0)

    assert list(groups.values()) == [["miner-a"]]
