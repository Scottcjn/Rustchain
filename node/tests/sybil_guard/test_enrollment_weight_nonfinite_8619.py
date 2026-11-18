# SPDX-License-Identifier: MIT
"""Regression tests for #8619: non-finite and non-numeric weights in the
enrollment -> epoch-weight money chain must fail CLOSED (0), never pass
through raw, never raise.

Pure module + node module import: no network, no live DB.
"""
import math

import pytest

import sg_helpers  # noqa: F401  (node/ on sys.path)
import sybil_guard as sg

NAN = float("nan")
INF = float("inf")

STATES = {
    "probation": {"state": sg.STATE_PROBATION},
    "grandfathered": {"state": sg.STATE_GRANDFATHERED},
    "trusted": {"state": sg.STATE_TRUSTED, "reason": "graduated", "last_binding_state": "bound"},
    "unavailable_established": {"state": sg.STATE_UNAVAILABLE, "established": True},
    "not_a_dict": None,
}

GARBAGE = [None, "N/A", "", "abc", object(), [], {}, NAN, INF, -INF, -1.0, -0.5]


@pytest.mark.parametrize("state_name", sorted(STATES))
@pytest.mark.parametrize("bad", GARBAGE, ids=[repr(g)[:12] for g in GARBAGE])
def test_enrollment_weight_garbage_fails_closed(state_name, bad):
    out = sg.enrollment_weight(bad, STATES[state_name])
    assert isinstance(out, float), f"{state_name}: returned raw {out!r}"
    assert math.isfinite(out)
    assert out == 0.0


@pytest.mark.parametrize("state_name", sorted(STATES))
def test_enrollment_weight_numeric_strings_and_ints_still_work(state_name):
    # Coercible inputs keep today's behaviour (cap applies per state).
    for good in (1, "2.5", 2.5):
        out = sg.enrollment_weight(good, STATES[state_name])
        assert isinstance(out, float) and math.isfinite(out) and out >= 0.0


def test_enrollment_weight_huge_finite_is_finite_and_capped_or_passed():
    # A huge finite weight is still finite; the converter (below) is what caps
    # it. enrollment_weight must at least not blow up or return non-float.
    out = sg.enrollment_weight(1e308, STATES["grandfathered"])
    assert isinstance(out, float) and math.isfinite(out)


# ---------------------------------------------------------------- node side

@pytest.fixture(scope="module")
def node(tmp_path_factory):
    db = tmp_path_factory.mktemp("n8619") / "node.db"
    return sg_helpers.load_node(db, "nonfinite_8619")


@pytest.mark.parametrize("bad", [NAN, INF, -INF, "nan", "inf", "-inf", "Infinity",
                                 None, "N/A", object(), -1.0, -1e308],
                         ids=lambda b: repr(b)[:12])
def test_epoch_weight_to_units_rejects_nonfinite_and_garbage(node, bad):
    units = node.epoch_weight_to_units(bad)
    assert isinstance(units, int)
    assert units == 0


def test_epoch_weight_to_units_caps_huge_finite_at_max(node):
    assert node.epoch_weight_to_units(1e308) == node.MAX_EPOCH_WEIGHT_UNITS
    assert node.epoch_weight_to_units(node.MAX_EPOCH_WEIGHT + 1) == node.MAX_EPOCH_WEIGHT_UNITS
    assert node.epoch_weight_to_units(node.MAX_EPOCH_WEIGHT) == node.MAX_EPOCH_WEIGHT_UNITS
    # result must fit SQLite's 64-bit INTEGER column
    assert node.epoch_weight_to_units(1e308) < 2 ** 63


def test_epoch_weight_to_units_normal_values_unchanged(node):
    assert node.epoch_weight_to_units(2.5) == 2_500_000_000
    assert node.epoch_weight_to_units("0.000000001") == 1
    assert node.epoch_weight_to_units(0) == 0
    assert node.epoch_weight_to_units(1.0 * 0.75) == 750_000_000


@pytest.mark.parametrize("bad", [NAN, INF, -INF, "nan", None, "x", -3.0, 1e308],
                         ids=lambda b: repr(b)[:12])
def test_normalize_epoch_weight_units_legacy_real_garbage(node, bad):
    units = node.normalize_epoch_weight_units(bad)
    assert isinstance(units, int)
    assert 0 <= units <= node.MAX_EPOCH_WEIGHT_UNITS


def test_apply_temporal_consistency_with_probation_fails_closed_on_garbage(node):
    for bad in (NAN, INF, None, "N/A"):
        for st in STATES.values():
            out = node.apply_temporal_consistency_to_weight(bad, {}, st)
            assert isinstance(out, float) and math.isfinite(out) and out == 0.0
