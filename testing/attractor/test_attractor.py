"""Tests for the attractor harness itself + the reference invariants.

Run:  pytest testing/attractor/test_attractor.py -v
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from attractor import HarnessUsageError, InvariantViolation, invariant  # noqa: E402
from attractor.harness import REGISTRY, Ctx, InvariantSpec  # noqa: E402
from attractor import examples  # noqa: E402,F401  (registers reference invariants)


# --- the three reference invariants must be green -------------------------

@pytest.mark.parametrize("inv_id", ["INV-EMISSION-001", "INV-ENROLL-002", "INV-SETTLE-003"])
def test_reference_invariant_is_green(inv_id):
    spec = REGISTRY[inv_id]
    ctx = Ctx(spec)
    spec.func(ctx)
    assert ctx.checks, "an invariant test must perform at least one ctx.check()"


def test_reference_invariants_are_deterministic():
    """Same seed, same result: no flaky submissions allowed."""
    for spec in REGISTRY.values():
        for _ in range(5):
            ctx = Ctx(spec, seed=1337)
            spec.func(ctx)
            first = list(ctx.checks)
            ctx2 = Ctx(spec, seed=1337)
            spec.func(ctx2)
            assert ctx2.checks == first


def test_registry_metadata_is_complete():
    assert len(REGISTRY) >= 3
    for inv_id, spec in REGISTRY.items():
        assert isinstance(spec, InvariantSpec)
        assert spec.id == inv_id
        assert "/" in spec.scope
        assert len(spec.statement) >= 15
        assert spec.adversarial is True


# --- grammar enforcement ---------------------------------------------------

def test_rejects_bad_id():
    with pytest.raises(HarnessUsageError):
        @invariant(id="bad id", statement="something that is long enough", scope="a/b")
        def _f(ctx):  # pragma: no cover
            ctx.check(True, "never runs")


def test_rejects_duplicate_id():
    @invariant(id="INV-DUP-900", statement="a duplicate id must be refused", scope="a/b")
    def _f(ctx):  # pragma: no cover
        ctx.check(True, "placeholder check")

    with pytest.raises(HarnessUsageError):
        @invariant(id="INV-DUP-900", statement="a duplicate id must be refused", scope="a/b")
        def _g(ctx):  # pragma: no cover
            ctx.check(True, "placeholder check")


def test_rejects_vague_statement_and_scope():
    with pytest.raises(HarnessUsageError):
        @invariant(id="INV-VAGUE-901", statement="short", scope="a/b")
        def _f(ctx):  # pragma: no cover
            ctx.check(True, "placeholder check")

    with pytest.raises(HarnessUsageError):
        @invariant(id="INV-VAGUE-902", statement="a sufficiently long statement", scope="noslash")
        def _g(ctx):  # pragma: no cover
            ctx.check(True, "placeholder check")


def test_rejects_test_without_checks():
    @invariant(id="INV-EMPTY-903", statement="tests must assert something real", scope="a/b")
    def _f(ctx):
        return None

    with pytest.raises(HarnessUsageError):
        _f()


def test_check_requires_reason():
    spec = REGISTRY["INV-SETTLE-003"]
    ctx = Ctx(spec)
    with pytest.raises(HarnessUsageError):
        ctx.check(True, "x")


def test_violation_is_reported():
    @invariant(id="INV-FAIL-904", statement="a failing invariant must raise", scope="a/b")
    def _f(ctx):
        ctx.check(False, "this condition is deliberately false")

    with pytest.raises(InvariantViolation) as exc:
        _f()
    assert "INV-FAIL-904" in str(exc.value)


# --- adversary helpers -----------------------------------------------------

def test_adversary_helpers():
    ctx = Ctx(REGISTRY["INV-ENROLL-002"])
    adv = ctx.adversary("t")
    assert adv.replay([1, 2], times=3) == [1, 1, 1, 2, 2, 2]
    assert sorted(adv.shuffle([1, 2, 3, 4])) == [1, 2, 3, 4]
    assert adv.inject([1, 2, 3], 9, count=2).count(9) == 2
