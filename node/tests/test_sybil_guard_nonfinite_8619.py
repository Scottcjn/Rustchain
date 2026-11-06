# SPDX-License-Identifier: Apache-2.0
"""Regression tests for Issue #8619: non-finite and non-coercible weights in sybil_guard."""

import math
import sqlite3
import pytest

from node import sybil_guard


@pytest.mark.parametrize(
    "bad_weight",
    [
        None,
        "N/A",
        "",
        "nan",
        "inf",
        "-inf",
        float("nan"),
        float("inf"),
        float("-inf"),
        -1.5,
        True,
        False,
        {},
        [],
    ],
)
@pytest.mark.parametrize(
    "state",
    [
        sybil_guard.STATE_PROBATION,
        sybil_guard.STATE_GRANDFATHERED,
        sybil_guard.STATE_TRUSTED,
        sybil_guard.STATE_UNAVAILABLE,
        sybil_guard.STATE_ADMISSION_QUEUED,
        sybil_guard.STATE_QUEUED,
    ],
)
def test_enrollment_weight_rejects_nonfinite_and_garbage(bad_weight, state):
    status = {"state": state, "needs_review": 0, "established": True}
    result = sybil_guard.enrollment_weight(bad_weight, status)
    assert isinstance(result, float)
    assert math.isfinite(result)
    assert result == 0.0


def test_enrollment_weight_preserves_valid_finite_weights():
    assert sybil_guard.enrollment_weight(2.5, {"state": sybil_guard.STATE_GRANDFATHERED}) == 2.5
    assert sybil_guard.enrollment_weight(2.5, {"state": sybil_guard.STATE_PROBATION}) == sybil_guard.PROBATION_WEIGHT_CAP
    assert sybil_guard.enrollment_weight(0.8, {"state": sybil_guard.STATE_PROBATION}) == 0.8
    assert sybil_guard.enrollment_weight(1.75, {"state": sybil_guard.STATE_TRUSTED, "reason": "operator_allowlist"}) == 1.75


def test_hold_for_settlement_survives_nan_and_inf_weights():
    conn = sqlite3.connect(":memory:")
    sybil_guard.init_schema(conn)
    conn.execute(
        "INSERT INTO miner_probation (miner, state, first_seen, last_seen, needs_review, review_reason, updated_at) "
        "VALUES (?, ?, 1000, 1000, 1, 'incident', 1000)",
        ("miner-held", sybil_guard.STATE_PROBATION),
    )
    conn.commit()
    held = sybil_guard.hold_for_settlement(
        conn,
        epoch=42,
        miners=["miner-held"],
        weights={"miner-held": float("inf")},
        record=True,
    )
    assert "miner-held" in held
