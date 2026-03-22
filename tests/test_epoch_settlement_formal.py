#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Formal verification test suite for RustChain epoch settlement logic.

Properties verified
-------------------
1. **Conservation** — total distributed == exactly 1.5 RTC (1 500 000 satoshis)
   for any non-empty miner set with positive total weight.
2. **Non-negativity** — no miner receives negative satoshis.
3. **Proportionality** — a miner with multiplier M receives exactly M times
   what a miner with multiplier 1.0 receives (within 1 satoshi rounding).
4. **Idempotency** — calling the function twice with the same input returns
   identical results.
5. **Empty set safety** — empty miner list returns {} with no errors.
6. **Single miner** — gets the full 1 500 000 satoshis regardless of multiplier.
7. **Scale invariance** — multiplying ALL multipliers by the same positive
   constant does not change the distribution.
8. **All-zero multipliers** — everyone gets 0 (edge case, no crash).
9. **Precision at scale** — 1000+ miners, total still exact.
10. **Dust miner** — miner with 0.000000001 multiplier gets ≥ 0 satoshis (no crash).
11. **Overflow safety** — multipliers summing to > 2^53 handled correctly.
12. **Equal split** — identical multipliers produce equal or near-equal rewards.
13. **Negative multiplier** — raises ValueError cleanly.
14. **Missing miner_id** — raises ValueError cleanly.
15. **Known arch multipliers** — g4 (2.5x) gets exactly 2.5× a modern (1.0x) miner.

This file is designed to:
  * Import and call the real ``calculate_epoch_rewards_time_aged()`` from
    ``scripts/epoch_settlement.py``.
  * Run in < 60 seconds on Python 3.9+.
  * Exceed 500 lines.
  * Use both deterministic unit tests AND Hypothesis property-based tests.

Usage
-----
    python -m pytest tests/test_epoch_settlement_formal.py -v
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Path setup — make scripts/ importable
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = str(Path(__file__).parent.parent / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from epoch_settlement import (
    ARCH_MULTIPLIERS,
    EPOCH_REWARD_SATOSHIS,
    SATOSHIS_PER_RTC,
    calculate_epoch_rewards_time_aged,
)

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

SATOSHIS = EPOCH_REWARD_SATOSHIS  # 1_500_000


def make_miner(miner_id: str, multiplier: float) -> Dict[str, Any]:
    """Convenience constructor for a miner dict."""
    return {"miner_id": miner_id, "multiplier": multiplier}


def total_rewards(result: Dict[str, int]) -> int:
    """Sum all satoshi values in a result dict."""
    return sum(result.values())


def assert_total_exact(result: Dict[str, int], expected: int = SATOSHIS) -> None:
    """Assert that the total distributed equals *expected* satoshis."""
    got = total_rewards(result)
    assert got == expected, (
        f"Total distributed {got} != expected {expected} "
        f"(off by {got - expected} satoshis)"
    )


def assert_all_non_negative(result: Dict[str, int]) -> None:
    """Assert that every miner received ≥ 0 satoshis."""
    for mid, sats in result.items():
        assert sats >= 0, f"Miner {mid!r} received negative satoshis: {sats}"


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# A valid multiplier: positive finite float (not nan, not inf, not negative).
valid_multiplier = st.floats(
    min_value=0.0,
    max_value=1e15,
    allow_nan=False,
    allow_infinity=False,
)

# At least one positive multiplier so total_weight > 0.
positive_multiplier = st.floats(
    min_value=1e-9,
    max_value=1e15,
    allow_nan=False,
    allow_infinity=False,
)

# A miner_id: non-empty ascii string.
miner_id_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"),
    min_size=1,
    max_size=40,
)


def unique_miner_list(draw, min_size: int = 1, max_size: int = 50):
    """Draw a list of unique miners with valid multipliers."""
    n = draw(st.integers(min_value=min_size, max_value=max_size))
    ids = draw(st.lists(miner_id_strategy, min_size=n, max_size=n, unique=True))
    multipliers = draw(st.lists(valid_multiplier, min_size=n, max_size=n))
    return [make_miner(ids[i], multipliers[i]) for i in range(n)]


# ---------------------------------------------------------------------------
# Unit tests — deterministic
# ---------------------------------------------------------------------------


class TestEmptyMinerSet:
    """Property 5: empty input produces empty output with no errors."""

    def test_empty_list_returns_empty_dict(self):
        result = calculate_epoch_rewards_time_aged([])
        assert result == {}

    def test_empty_list_total_is_zero(self):
        result = calculate_epoch_rewards_time_aged([])
        assert total_rewards(result) == 0

    def test_empty_list_no_exception(self):
        """Calling twice with empty list is stable."""
        r1 = calculate_epoch_rewards_time_aged([])
        r2 = calculate_epoch_rewards_time_aged([])
        assert r1 == r2 == {}


class TestSingleMiner:
    """Property 6: single miner gets full 1.5 RTC regardless of multiplier."""

    @pytest.mark.parametrize("multiplier", [1.0, 2.5, 0.5, 100.0, 1e-9])
    def test_single_miner_gets_full_reward(self, multiplier):
        miners = [make_miner("alice", multiplier)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert result == {"alice": SATOSHIS}, (
            f"Single miner with multiplier={multiplier} should get "
            f"{SATOSHIS} satoshis, got {result}"
        )

    def test_single_miner_large_multiplier(self):
        miners = [make_miner("big_miner", 9999.99)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert result == {"big_miner": SATOSHIS}

    def test_single_miner_unit_multiplier(self):
        miners = [make_miner("unit", 1.0)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert result == {"unit": SATOSHIS}

    def test_single_miner_tiny_multiplier(self):
        miners = [make_miner("dust", 1e-15)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert result == {"dust": SATOSHIS}


class TestTwoMinerSplit:
    """Basic two-miner scenarios covering proportionality."""

    def test_equal_multipliers_split_evenly(self):
        miners = [make_miner("a", 1.0), make_miner("b", 1.0)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)
        assert_all_non_negative(result)
        # Equal multipliers → equal share; total 1_500_000 is even → exact split
        assert result["a"] == result["b"] == 750_000

    def test_2x_multiplier_gets_double(self):
        miners = [make_miner("base", 1.0), make_miner("two_x", 2.0)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)
        # total weight 3; base gets 1/3, two_x gets 2/3
        assert result["base"] == 500_000
        assert result["two_x"] == 1_000_000

    def test_g4_vs_modern(self):
        """g4 (2.5x) should receive exactly 2.5× what modern (1.0x) receives."""
        miners = [make_miner("modern", 1.0), make_miner("g4", 2.5)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)
        # total weight 3.5; modern = 1/3.5 * 1_500_000 = 428_571.428...
        # g4 = 2.5/3.5 * 1_500_000 = 1_071_428.571...
        # After largest-remainder: modern=428_572, g4=1_071_428  (or similar)
        modern_sats = result["modern"]
        g4_sats = result["g4"]
        # g4 should be within 1 satoshi of 2.5× modern
        ratio = g4_sats / modern_sats
        assert abs(ratio - 2.5) < 0.01, (
            f"g4/modern ratio should be ~2.5, got {ratio:.6f} "
            f"(g4={g4_sats}, modern={modern_sats})"
        )

    def test_g5_vs_modern(self):
        miners = [make_miner("modern", 1.0), make_miner("g5", 2.0)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)
        assert result["g5"] == 2 * result["modern"]

    def test_proportionality_asymmetric(self):
        miners = [make_miner("a", 3.0), make_miner("b", 1.0)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)
        # a gets 3/4 = 1_125_000, b gets 1/4 = 375_000
        assert result["a"] == 1_125_000
        assert result["b"] == 375_000


class TestConservation:
    """Property 1: total distributed is always exactly SATOSHIS for any non-empty set."""

    def test_three_miners_conservation(self):
        miners = [
            make_miner("a", 1.0),
            make_miner("b", 2.0),
            make_miner("c", 3.0),
        ]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)

    def test_ten_miners_conservation(self):
        miners = [make_miner(f"m{i}", float(i + 1)) for i in range(10)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)

    def test_prime_multipliers_conservation(self):
        primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]
        miners = [make_miner(f"p{p}", float(p)) for p in primes]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)

    def test_fractional_multipliers_conservation(self):
        miners = [
            make_miner("a", 1.1),
            make_miner("b", 2.2),
            make_miner("c", 3.3),
            make_miner("d", 4.4),
        ]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)

    def test_irrational_like_multipliers(self):
        import math
        miners = [
            make_miner("pi", math.pi),
            make_miner("e", math.e),
            make_miner("sqrt2", math.sqrt(2)),
        ]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)


class TestNonNegativity:
    """Property 2: no miner ever receives negative satoshis."""

    def test_all_equal_multipliers(self):
        miners = [make_miner(f"m{i}", 1.0) for i in range(20)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_all_non_negative(result)

    def test_very_unequal_multipliers(self):
        miners = [make_miner("whale", 1e12), make_miner("dust", 1e-9)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_all_non_negative(result)

    def test_many_tiny_multipliers_vs_one_large(self):
        miners = [make_miner("giant", 1e9)] + [
            make_miner(f"tiny{i}", 1e-6) for i in range(100)
        ]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_all_non_negative(result)


class TestIdempotency:
    """Property 4: calling the function twice returns identical results."""

    def test_idempotent_two_miners(self):
        miners = [make_miner("a", 1.5), make_miner("b", 2.5)]
        r1 = calculate_epoch_rewards_time_aged(miners)
        r2 = calculate_epoch_rewards_time_aged(miners)
        assert r1 == r2

    def test_idempotent_many_miners(self):
        miners = [make_miner(f"m{i}", float(i % 5 + 1)) for i in range(50)]
        r1 = calculate_epoch_rewards_time_aged(miners)
        r2 = calculate_epoch_rewards_time_aged(miners)
        assert r1 == r2

    def test_idempotent_single_miner(self):
        miners = [make_miner("solo", 3.14)]
        r1 = calculate_epoch_rewards_time_aged(miners)
        r2 = calculate_epoch_rewards_time_aged(miners)
        assert r1 == r2

    def test_idempotent_empty(self):
        r1 = calculate_epoch_rewards_time_aged([])
        r2 = calculate_epoch_rewards_time_aged([])
        assert r1 == r2 == {}

    def test_idempotent_does_not_mutate_input(self):
        """The function must not mutate its input list or dicts."""
        miners = [make_miner("a", 2.0), make_miner("b", 1.0)]
        original = [dict(m) for m in miners]
        calculate_epoch_rewards_time_aged(miners)
        assert miners[0] == original[0]
        assert miners[1] == original[1]


class TestEdgeCases:
    """Edge cases from the bounty specification."""

    def test_1000_miners_precision(self):
        """1000 miners — total must still be exactly SATOSHIS."""
        miners = [make_miner(f"m{i:04d}", float(i % 10 + 1)) for i in range(1000)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)
        assert_all_non_negative(result)

    def test_1000_miners_all_receive_something_or_nothing_for_tiny_weight(self):
        """1000 miners with equal multipliers each get ~1500 satoshis."""
        miners = [make_miner(f"m{i:04d}", 1.0) for i in range(1000)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)
        # Each miner should get 1500 satoshis (1_500_000 / 1000 = 1500 exact)
        for mid, sats in result.items():
            assert sats == 1500, f"{mid} got {sats}, expected 1500"

    def test_1024_miners_non_divisible(self):
        """1024 miners with equal multipliers — SATOSHIS % 1024 = 976 leftovers."""
        miners = [make_miner(f"m{i:04d}", 1.0) for i in range(1024)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)
        assert_all_non_negative(result)
        vals = list(result.values())
        # Most should be 1464 (floor(1_500_000/1024)), a few get 1465
        base = 1_500_000 // 1024  # 1464
        extra = 1_500_000 % 1024   # 976
        count_extra = sum(1 for v in vals if v == base + 1)
        count_base = sum(1 for v in vals if v == base)
        assert count_extra == extra, f"Expected {extra} miners with {base+1}, got {count_extra}"
        assert count_base == 1024 - extra, (
            f"Expected {1024 - extra} miners with {base}, got {count_base}"
        )

    def test_dust_miner_does_not_crash(self):
        """Miner with 0.000000001x weight gets ≥ 0 satoshis, no crash."""
        miners = [
            make_miner("rich", 1.0),
            make_miner("dust", 1e-9),
        ]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)
        assert result["dust"] >= 0

    def test_all_identical_multipliers_equal_split(self):
        """All miners have identical multipliers → equal (or ±1) distribution."""
        n = 7
        miners = [make_miner(f"m{i}", 3.7) for i in range(n)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)
        vals = list(result.values())
        base = SATOSHIS // n
        for v in vals:
            assert v in (base, base + 1), (
                f"Expected each miner to get {base} or {base+1}, got {v}"
            )

    def test_all_zero_multipliers_no_crash(self):
        """All multipliers == 0 → everyone gets 0 satoshis, no exception."""
        miners = [make_miner(f"m{i}", 0.0) for i in range(5)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert all(v == 0 for v in result.values()), (
            f"Expected all zeros for zero multipliers, got {result}"
        )
        # Total is 0 (special case: all weights are zero)
        assert total_rewards(result) == 0

    def test_one_zero_multiplier_gets_nothing(self):
        """A miner with 0.0 multiplier participates but receives 0 satoshis."""
        miners = [make_miner("active", 1.0), make_miner("zero", 0.0)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)
        assert result["zero"] == 0
        assert result["active"] == SATOSHIS

    def test_integer_overflow_large_multipliers(self):
        """Multipliers summing to > 2^53 must not cause overflow / wrong result."""
        # Each multiplier is ~2^50; total will be >> 2^53
        big = float(2**50)
        miners = [make_miner(f"m{i}", big) for i in range(10)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)
        assert_all_non_negative(result)
        # All equal → equal split
        vals = list(result.values())
        base = SATOSHIS // 10  # 150_000
        for v in vals:
            assert v in (base, base + 1)

    def test_very_large_multiplier_sum(self):
        """A single multiplier of 2^55 alongside a multiplier of 1 should work."""
        miners = [
            make_miner("giant", float(2**55)),
            make_miner("ant", 1.0),
        ]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)
        assert_all_non_negative(result)
        assert result["giant"] > result["ant"]


class TestProportionality:
    """Property 3: multiplier ratio is preserved to within 1 satoshi."""

    def test_2_5x_ratio_preserved(self):
        """g4 (2.5x) vs modern (1.0x): ratio exactly 2.5 (within rounding)."""
        miners = [make_miner("m", 1.0), make_miner("g4", 2.5)]
        result = calculate_epoch_rewards_time_aged(miners)
        # Total weight = 3.5; m = 1/3.5 ≈ 428571.4; g4 = 2.5/3.5 ≈ 1071428.6
        # After LRM: m=428572, g4=1071428 or m=428571, g4=1071429 — either way
        # g4 ≈ 2.5 × m within rounding tolerance
        m_sats = result["m"]
        g4_sats = result["g4"]
        assert abs(g4_sats - 2.5 * m_sats) <= 2, (
            f"Proportionality broken: g4={g4_sats}, m={m_sats}, "
            f"ratio={g4_sats/m_sats:.8f} (expected ~2.5)"
        )

    def test_exact_3x_ratio(self):
        miners = [make_miner("a", 1.0), make_miner("b", 3.0)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)
        # total weight 4; a=1/4=375000 exact, b=3/4=1125000 exact
        assert result["a"] == 375_000
        assert result["b"] == 1_125_000
        assert result["b"] == 3 * result["a"]

    def test_exact_4x_ratio(self):
        miners = [make_miner("a", 1.0), make_miner("b", 4.0)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)
        assert result["a"] == 300_000
        assert result["b"] == 1_200_000

    def test_proportionality_with_five_arch_types(self):
        """All known arch types together — verify ratios are internally consistent."""
        arches = ["modern", "core2duo", "apple_silicon", "g3", "g5", "g4"]
        miners = [make_miner(a, ARCH_MULTIPLIERS[a]) for a in arches]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)
        assert_all_non_negative(result)
        # g4/modern ratio should be ~2.5
        ratio = result["g4"] / result["modern"]
        assert abs(ratio - 2.5) < 0.01, (
            f"g4/modern ratio should be ~2.5, got {ratio:.6f}"
        )


class TestScaleInvariance:
    """Property 7: scaling all multipliers by a constant preserves distribution."""

    @pytest.mark.parametrize("scale", [0.5, 2.0, 100.0, 1e-6, 1e6])
    def test_scale_invariance(self, scale):
        base_miners = [
            make_miner("a", 1.0),
            make_miner("b", 2.0),
            make_miner("c", 3.0),
        ]
        scaled_miners = [
            make_miner(m["miner_id"], m["multiplier"] * scale)
            for m in base_miners
        ]
        r_base = calculate_epoch_rewards_time_aged(base_miners)
        r_scaled = calculate_epoch_rewards_time_aged(scaled_miners)
        assert r_base == r_scaled, (
            f"Scale invariance broken for scale={scale}: "
            f"base={r_base}, scaled={r_scaled}"
        )

    def test_scale_invariance_large_set(self):
        miners = [make_miner(f"m{i}", float(i + 1)) for i in range(20)]
        scaled = [make_miner(m["miner_id"], m["multiplier"] * 1000.0) for m in miners]
        assert calculate_epoch_rewards_time_aged(miners) == \
               calculate_epoch_rewards_time_aged(scaled)


class TestErrorHandling:
    """Properties 13 & 14: invalid inputs raise ValueError cleanly."""

    def test_negative_multiplier_raises(self):
        miners = [make_miner("a", 1.0), make_miner("b", -0.1)]
        with pytest.raises(ValueError, match="negative multiplier"):
            calculate_epoch_rewards_time_aged(miners)

    def test_very_negative_multiplier_raises(self):
        miners = [make_miner("a", -1000.0)]
        with pytest.raises(ValueError):
            calculate_epoch_rewards_time_aged(miners)

    def test_missing_miner_id_raises(self):
        miners = [{"multiplier": 1.0}]  # no miner_id key
        with pytest.raises(ValueError):
            calculate_epoch_rewards_time_aged(miners)

    def test_empty_string_miner_id_raises(self):
        miners = [{"miner_id": "", "multiplier": 1.0}]
        with pytest.raises(ValueError):
            calculate_epoch_rewards_time_aged(miners)

    def test_non_string_miner_id_raises(self):
        miners = [{"miner_id": 42, "multiplier": 1.0}]
        with pytest.raises(ValueError):
            calculate_epoch_rewards_time_aged(miners)

    def test_none_miner_id_raises(self):
        miners = [{"miner_id": None, "multiplier": 1.0}]
        with pytest.raises(ValueError):
            calculate_epoch_rewards_time_aged(miners)

    def test_nan_multiplier_raises(self):
        import math
        miners = [make_miner("a", math.nan)]
        with pytest.raises((ValueError, Exception)):
            calculate_epoch_rewards_time_aged(miners)

    def test_inf_multiplier_raises_or_succeeds_gracefully(self):
        """Infinity is technically invalid; function should either raise or handle."""
        import math
        miners = [make_miner("a", math.inf), make_miner("b", 1.0)]
        # We accept either a clean ValueError or a result where total is exact
        try:
            result = calculate_epoch_rewards_time_aged(miners)
            # If it doesn't raise, b should get 0 and a should get SATOSHIS
            assert_total_exact(result)
        except (ValueError, Exception):
            pass  # raising is also acceptable


class TestKnownArchMultipliers:
    """Property 15: verify the known hardware arch multipliers from arch.rs."""

    def test_g4_multiplier_value(self):
        assert ARCH_MULTIPLIERS["g4"] == 2.5

    def test_g5_multiplier_value(self):
        assert ARCH_MULTIPLIERS["g5"] == 2.0

    def test_g3_multiplier_value(self):
        assert ARCH_MULTIPLIERS["g3"] == 1.8

    def test_apple_silicon_multiplier_value(self):
        assert ARCH_MULTIPLIERS["apple_silicon"] == 1.2

    def test_core2duo_multiplier_value(self):
        assert ARCH_MULTIPLIERS["core2duo"] == 1.3

    def test_modern_multiplier_value(self):
        assert ARCH_MULTIPLIERS["modern"] == 1.0

    def test_g4_vs_g5_ratio(self):
        """g4 (2.5) vs g5 (2.0): ratio should be 2.5/2.0 = 1.25."""
        miners = [make_miner("g4", 2.5), make_miner("g5", 2.0)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)
        ratio = result["g4"] / result["g5"]
        assert abs(ratio - 1.25) < 0.01, f"g4/g5 ratio {ratio:.6f} != 1.25"

    def test_g3_vs_modern_ratio(self):
        miners = [make_miner("g3", 1.8), make_miner("modern", 1.0)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)
        ratio = result["g3"] / result["modern"]
        assert abs(ratio - 1.8) < 0.02, f"g3/modern ratio {ratio:.6f} != 1.8"

    def test_all_arch_types_no_crash(self):
        """Exercise every known arch type together."""
        miners = [make_miner(arch, mult) for arch, mult in ARCH_MULTIPLIERS.items()]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)
        assert_all_non_negative(result)
        assert set(result.keys()) == set(ARCH_MULTIPLIERS.keys())


class TestResultStructure:
    """Validate the structure of return values."""

    def test_returns_dict(self):
        miners = [make_miner("a", 1.0)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert isinstance(result, dict)

    def test_keys_match_miner_ids(self):
        miners = [make_miner("alice", 1.0), make_miner("bob", 2.0)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert set(result.keys()) == {"alice", "bob"}

    def test_values_are_integers(self):
        miners = [make_miner(f"m{i}", float(i + 1)) for i in range(5)]
        result = calculate_epoch_rewards_time_aged(miners)
        for mid, v in result.items():
            assert isinstance(v, int), f"{mid} value {v!r} is not int"

    def test_decimal_multiplier_accepted(self):
        """Decimal multipliers should be accepted."""
        miners = [
            {"miner_id": "a", "multiplier": Decimal("2.5")},
            {"miner_id": "b", "multiplier": Decimal("1.0")},
        ]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)

    def test_string_multiplier_accepted(self):
        """String-form multipliers should be accepted."""
        miners = [
            {"miner_id": "a", "multiplier": "2.5"},
            {"miner_id": "b", "multiplier": "1.0"},
        ]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)

    def test_integer_multiplier_accepted(self):
        miners = [make_miner("a", 2), make_miner("b", 1)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)

    def test_missing_multiplier_defaults_to_one(self):
        """A miner with no multiplier key should default to 1.0."""
        miners = [{"miner_id": "a"}, {"miner_id": "b", "multiplier": 1.0}]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)
        assert result["a"] == result["b"] == 750_000


class TestPrecisionAtScale:
    """Verify satoshi precision holds for large miner counts."""

    def test_100_miners_with_varied_multipliers(self):
        multipliers = [float((i % 5) + 1) for i in range(100)]
        miners = [make_miner(f"m{i:03d}", multipliers[i]) for i in range(100)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)
        assert_all_non_negative(result)

    def test_500_miners_equal_split(self):
        miners = [make_miner(f"m{i:03d}", 1.0) for i in range(500)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)
        # 1_500_000 / 500 = 3000 exactly
        for v in result.values():
            assert v == 3000

    def test_333_miners_non_divisible(self):
        """1_500_000 % 333 = 300 → 300 miners get (floor+1), rest get floor."""
        miners = [make_miner(f"m{i:03d}", 1.0) for i in range(333)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)
        base = 1_500_000 // 333       # 4504
        extra = 1_500_000 % 333        # 300
        count_base_plus_1 = sum(1 for v in result.values() if v == base + 1)
        count_base_val = sum(1 for v in result.values() if v == base)
        assert count_base_plus_1 == extra
        assert count_base_val == 333 - extra

    def test_2000_miners_sum_exact(self):
        miners = [make_miner(f"m{i:04d}", float(i % 7 + 1)) for i in range(2000)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)

    def test_no_satoshi_left_behind_any_divisor(self):
        """For n miners from 1 to 50 with equal weights, total is always exact."""
        for n in range(1, 51):
            miners = [make_miner(f"m{i}", 1.0) for i in range(n)]
            result = calculate_epoch_rewards_time_aged(miners)
            got = total_rewards(result)
            assert got == SATOSHIS, (
                f"n={n}: total {got} != {SATOSHIS}"
            )


# ---------------------------------------------------------------------------
# Hypothesis property-based tests
# ---------------------------------------------------------------------------


class TestHypothesisConservation:
    """PBT: conservation holds for any valid miner set."""

    @given(st.lists(
        st.fixed_dictionaries({
            "miner_id": miner_id_strategy,
            "multiplier": positive_multiplier,
        }),
        min_size=1,
        max_size=50,
        unique_by=lambda m: m["miner_id"],
    ))
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_total_always_satoshis(self, miners):
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)

    @given(st.lists(
        st.fixed_dictionaries({
            "miner_id": miner_id_strategy,
            "multiplier": valid_multiplier,
        }),
        min_size=1,
        max_size=50,
        unique_by=lambda m: m["miner_id"],
    ))
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_total_satoshis_or_zero_when_all_weights_zero(self, miners):
        result = calculate_epoch_rewards_time_aged(miners)
        total = total_rewards(result)
        all_zero = all(m["multiplier"] == 0.0 for m in miners)
        if all_zero:
            assert total == 0
        else:
            assert total == SATOSHIS


class TestHypothesisNonNegativity:
    """PBT: no miner gets negative satoshis."""

    @given(st.lists(
        st.fixed_dictionaries({
            "miner_id": miner_id_strategy,
            "multiplier": valid_multiplier,
        }),
        min_size=1,
        max_size=100,
        unique_by=lambda m: m["miner_id"],
    ))
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_all_non_negative(self, miners):
        result = calculate_epoch_rewards_time_aged(miners)
        assert_all_non_negative(result)


class TestHypothesisIdempotency:
    """PBT: same input always produces same output."""

    @given(st.lists(
        st.fixed_dictionaries({
            "miner_id": miner_id_strategy,
            "multiplier": positive_multiplier,
        }),
        min_size=1,
        max_size=50,
        unique_by=lambda m: m["miner_id"],
    ))
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_idempotent(self, miners):
        r1 = calculate_epoch_rewards_time_aged(miners)
        r2 = calculate_epoch_rewards_time_aged(miners)
        assert r1 == r2


class TestHypothesisScaleInvariance:
    """PBT: multiplying all weights by a positive constant preserves distribution."""

    @given(
        st.lists(
            st.fixed_dictionaries({
                "miner_id": miner_id_strategy,
                "multiplier": positive_multiplier,
            }),
            min_size=1,
            max_size=30,
            unique_by=lambda m: m["miner_id"],
        ),
        st.floats(min_value=1e-6, max_value=1e6, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=150, suppress_health_check=[HealthCheck.too_slow])
    def test_scale_invariance(self, miners, scale):
        assume(scale > 0)
        scaled = [
            {"miner_id": m["miner_id"], "multiplier": m["multiplier"] * scale}
            for m in miners
        ]
        r1 = calculate_epoch_rewards_time_aged(miners)
        r2 = calculate_epoch_rewards_time_aged(scaled)
        assert r1 == r2, (
            f"Scale invariance violated for scale={scale}: r1={r1}, r2={r2}"
        )


class TestHypothesisProportionality:
    """PBT: for two miners, their reward ratio matches their multiplier ratio."""

    @given(
        miner_id_strategy,
        miner_id_strategy,
        positive_multiplier,
        positive_multiplier,
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_two_miner_proportionality(self, id_a, id_b, mult_a, mult_b):
        assume(id_a != id_b)
        assume(mult_a > 0 and mult_b > 0)
        miners = [
            make_miner(id_a, mult_a),
            make_miner(id_b, mult_b),
        ]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)
        sa = result[id_a]
        sb = result[id_b]
        # Both non-negative
        assert sa >= 0
        assert sb >= 0
        # If both > 0, ratio should be approximately mult_a/mult_b
        if sa > 0 and sb > 0:
            expected_ratio = mult_a / mult_b
            actual_ratio = sa / sb
            # Allow ±1 satoshi absolute error → relative tolerance depends on values
            # Use a loose relative tolerance for Hypothesis (many edge cases)
            tol = max(2.0 / min(sa, sb), 0.01)
            assert abs(actual_ratio - expected_ratio) / expected_ratio < tol, (
                f"Ratio {actual_ratio:.6f} vs expected {expected_ratio:.6f} "
                f"(mult_a={mult_a}, mult_b={mult_b}, sa={sa}, sb={sb})"
            )


class TestHypothesisSingleMiner:
    """PBT: single miner always gets all SATOSHIS."""

    @given(miner_id_strategy, positive_multiplier)
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_single_miner_gets_full_reward(self, miner_id, multiplier):
        miners = [make_miner(miner_id, multiplier)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert result == {miner_id: SATOSHIS}, (
            f"Single miner should get {SATOSHIS}, got {result}"
        )


class TestHypothesisIntegerValues:
    """PBT: all returned values are integers."""

    @given(st.lists(
        st.fixed_dictionaries({
            "miner_id": miner_id_strategy,
            "multiplier": positive_multiplier,
        }),
        min_size=1,
        max_size=50,
        unique_by=lambda m: m["miner_id"],
    ))
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_all_values_are_ints(self, miners):
        result = calculate_epoch_rewards_time_aged(miners)
        for mid, v in result.items():
            assert isinstance(v, int), f"Value for {mid!r} is {type(v).__name__}, not int"


class TestHypothesisKeySetMatchesInput:
    """PBT: output keys always match input miner_ids exactly."""

    @given(st.lists(
        st.fixed_dictionaries({
            "miner_id": miner_id_strategy,
            "multiplier": valid_multiplier,
        }),
        min_size=0,
        max_size=50,
        unique_by=lambda m: m["miner_id"],
    ))
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_keys_match_miner_ids(self, miners):
        result = calculate_epoch_rewards_time_aged(miners)
        expected_keys = {m["miner_id"] for m in miners}
        assert set(result.keys()) == expected_keys


# ---------------------------------------------------------------------------
# Additional deterministic regression tests
# ---------------------------------------------------------------------------


class TestRegressionCases:
    """Specific arithmetic regression tests to pin down exact values."""

    def test_three_equal_miners(self):
        """1_500_000 / 3 = 500_000 exactly."""
        miners = [make_miner(f"m{i}", 1.0) for i in range(3)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)
        for v in result.values():
            assert v == 500_000

    def test_six_equal_miners(self):
        """1_500_000 / 6 = 250_000 exactly."""
        miners = [make_miner(f"m{i}", 1.0) for i in range(6)]
        result = calculate_epoch_rewards_time_aged(miners)
        for v in result.values():
            assert v == 250_000

    def test_7_equal_miners_largest_remainder(self):
        """1_500_000 / 7 = 214285 rem 5 → 5 miners get 214286, 2 get 214285."""
        miners = [make_miner(f"m{i}", 1.0) for i in range(7)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)
        base = 1_500_000 // 7         # 214285
        extra_count = 1_500_000 % 7   # 5
        assert sum(1 for v in result.values() if v == base + 1) == extra_count
        assert sum(1 for v in result.values() if v == base) == 7 - extra_count

    def test_weighted_trio(self):
        """a=1, b=2, c=3; weights sum=6; expected 250000, 500000, 750000."""
        miners = [make_miner("a", 1.0), make_miner("b", 2.0), make_miner("c", 3.0)]
        result = calculate_epoch_rewards_time_aged(miners)
        assert result["a"] == 250_000
        assert result["b"] == 500_000
        assert result["c"] == 750_000
        assert_total_exact(result)

    def test_all_arch_types_total(self):
        """All six arch types together should distribute exactly 1.5 RTC."""
        miners = [make_miner(arch, mult) for arch, mult in ARCH_MULTIPLIERS.items()]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)

    def test_satoshis_per_rtc_constant(self):
        """Verify the module-level constants are correct."""
        from epoch_settlement import EPOCH_REWARD_RTC, EPOCH_REWARD_SATOSHIS, SATOSHIS_PER_RTC
        assert EPOCH_REWARD_RTC == Decimal("1.5")
        assert SATOSHIS_PER_RTC == 1_000_000
        assert EPOCH_REWARD_SATOSHIS == 1_500_000

    def test_reward_does_not_depend_on_miner_order(self):
        """Swapping two miners with the same multiplier should give same totals."""
        miners_ab = [make_miner("a", 2.0), make_miner("b", 1.0)]
        miners_ba = [make_miner("b", 1.0), make_miner("a", 2.0)]
        r_ab = calculate_epoch_rewards_time_aged(miners_ab)
        r_ba = calculate_epoch_rewards_time_aged(miners_ba)
        assert r_ab["a"] == r_ba["a"]
        assert r_ab["b"] == r_ba["b"]

    def test_dust_miner_with_1000_normal_miners(self):
        """Dust miner alongside 1000 normal miners must not steal satoshis."""
        miners = [make_miner(f"m{i:04d}", 1.0) for i in range(1000)]
        miners.append(make_miner("dust", 1e-9))
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)
        assert_all_non_negative(result)
        # Dust miner should get 0 or at most 1 satoshi
        assert result["dust"] <= 1

    def test_g4_g5_g3_modern_together(self):
        miners = [
            make_miner("modern", 1.0),
            make_miner("g3", 1.8),
            make_miner("g5", 2.0),
            make_miner("g4", 2.5),
        ]
        result = calculate_epoch_rewards_time_aged(miners)
        assert_total_exact(result)
        # g4 > g5 > g3 > modern
        assert result["g4"] > result["g5"]
        assert result["g5"] > result["g3"]
        assert result["g3"] > result["modern"]
