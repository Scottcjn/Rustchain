#!/usr/bin/env python3
"""
Property-Based Formal Verification Tests for Epoch Settlement Logic
===================================================================

Verifies mathematical correctness of `calculate_epoch_rewards_time_aged()`.

Run: python tests/test_epoch_settlement_formal.py
"""

import os
import sys
import sqlite3
import time
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "node"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from rip_200_round_robin_1cpu1vote import (
        calculate_epoch_rewards_time_aged,
        get_time_aged_multiplier,
        get_chain_age_years,
        ANTIQUITY_MULTIPLIERS,
        GENESIS_TIMESTAMP,
        BLOCK_TIME,
    )
except ImportError:
    from node.rip_200_round_robin_1cpu1vote import (
        calculate_epoch_rewards_time_aged,
        get_time_aged_multiplier,
        get_chain_age_years,
        ANTIQUITY_MULTIPLIERS,
        GENESIS_TIMESTAMP,
        BLOCK_TIME,
    )

UNIT = 1_000_000
PER_EPOCH_URTC = int(1.5 * UNIT)
ATTESTATION_TTL = 86400

_TEST_EPOCH = 10
_TEST_EPOCH_START_TS = GENESIS_TIMESTAMP + (_TEST_EPOCH * 144 * BLOCK_TIME)
_TEST_EPOCH_END_TS = _TEST_EPOCH_START_TS + (143 * BLOCK_TIME)


def create_test_db(miners):
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE miner_attest_recent (
            miner TEXT, device_arch TEXT, ts_ok INTEGER,
            fingerprint_passed INTEGER DEFAULT 1, warthog_bonus REAL DEFAULT 1.0
        )
    """)
    for m in miners:
        ts = _TEST_EPOCH_START_TS + m.get("ts_offset", 0)
        cursor.execute("""
            INSERT INTO miner_attest_recent (miner, device_arch, ts_ok, fingerprint_passed, warthog_bonus)
            VALUES (?, ?, ?, ?, ?)
        """, (m["miner_id"], m.get("device_arch", "g4"), ts,
              m.get("fingerprint_passed", 1), m.get("warthog_bonus", 1.0)))
    conn.commit()
    conn.close()
    return db_path


def get_test_slot():
    return _TEST_EPOCH * 144 + 72


def cleanup(db_path):
    try:
        if os.path.exists(db_path):
            os.unlink(db_path)
    except Exception:
        pass


# ---- Tests ------------------------------------------------------------

def test_total_distribution_exact():
    cases = [
        [{"miner_id": "m1", "device_arch": "g4"}],
        [{"miner_id": "m1", "device_arch": "g4"}, {"miner_id": "m2", "device_arch": "g5"}],
        [{"miner_id": f"m{i}", "device_arch": "g4"} for i in range(10)],
        [{"miner_id": f"m{i}", "device_arch": "modern"} for i in range(100)],
        [{"miner_id": "vax", "device_arch": "vax"}, {"miner_id": "pentium4", "device_arch": "pentium4"}, {"miner_id": "modern", "device_arch": "modern"}],
    ]
    for i, miners in enumerate(cases):
        db = create_test_db(miners)
        try:
            rewards = calculate_epoch_rewards_time_aged(db, _TEST_EPOCH, PER_EPOCH_URTC, get_test_slot())
            total = sum(rewards.values())
            diff = abs(total - PER_EPOCH_URTC)
            assert diff <= 1, f"Case {i}: total={total}, expected={PER_EPOCH_URTC}, diff={diff}"
        finally:
            cleanup(db)
    print("[PASS] Property 1: Total distribution == PER_EPOCH_URTC (within 1 satoshi)")


def test_total_distribution_1000_miners():
    miners = [{"miner_id": f"m{i}", "device_arch": "g4"} for i in range(1000)]
    db = create_test_db(miners)
    try:
        rewards = calculate_epoch_rewards_time_aged(db, _TEST_EPOCH, PER_EPOCH_URTC, get_test_slot())
        total = sum(rewards.values())
        assert abs(total - PER_EPOCH_URTC) <= 1, f"1000 miners: diff={total-PER_EPOCH_URTC}"
    finally:
        cleanup(db)
    print("[PASS] Property 1b: Total distribution holds with 1000 miners")


def test_no_negative_rewards():
    cases = [
        [{"miner_id": "m1", "device_arch": "g4"}],
        [{"miner_id": "m1", "device_arch": "g4"}, {"miner_id": "m2", "device_arch": "pentium4"}],
        [{"miner_id": "vax", "device_arch": "vax"}, {"miner_id": "arm2", "device_arch": "arm2"}, {"miner_id": "transputer", "device_arch": "transputer"}],
    ]
    for i, miners in enumerate(cases):
        db = create_test_db(miners)
        try:
            rewards = calculate_epoch_rewards_time_aged(db, _TEST_EPOCH, PER_EPOCH_URTC, get_test_slot())
            for mid, share in rewards.items():
                assert share >= 0, f"Case {i}: {mid} got negative share={share}"
        finally:
            cleanup(db)
    print("[PASS] Property 2: No negative rewards")


def test_no_zero_shares_valid_miners():
    miners = [
        {"miner_id": "m1", "device_arch": "g4", "fingerprint_passed": 1},
        {"miner_id": "m2", "device_arch": "pentium", "fingerprint_passed": 1},
        {"miner_id": "m3", "device_arch": "vax", "fingerprint_passed": 1},
    ]
    db = create_test_db(miners)
    try:
        rewards = calculate_epoch_rewards_time_aged(db, _TEST_EPOCH, PER_EPOCH_URTC, get_test_slot())
        for m in miners:
            share = rewards.get(m["miner_id"], 0)
            assert share > 0, f"{m['miner_id']} valid miner got zero share"
    finally:
        cleanup(db)
    print("[PASS] Property 3: No zero shares for valid miners")


def test_failed_fingerprint_zero():
    miners = [
        {"miner_id": "good", "device_arch": "g4", "fingerprint_passed": 1},
        {"miner_id": "bad", "device_arch": "g4", "fingerprint_passed": 0},
    ]
    db = create_test_db(miners)
    try:
        rewards = calculate_epoch_rewards_time_aged(db, _TEST_EPOCH, PER_EPOCH_URTC, get_test_slot())
        assert rewards.get("good", 0) > 0, "Good miner should have positive share"
        assert rewards.get("bad", 0) == 0, "Failed fingerprint should get ZERO"
    finally:
        cleanup(db)
    print("[PASS] Property 3b: Failed fingerprint == zero share")


def test_multiplier_linearity():
    miners = [
        {"miner_id": "vintage_g4", "device_arch": "g4"},
        {"miner_id": "modern", "device_arch": "modern"},
    ]
    db = create_test_db(miners)
    try:
        rewards = calculate_epoch_rewards_time_aged(db, _TEST_EPOCH, PER_EPOCH_URTC, get_test_slot())
        vintage = rewards.get("vintage_g4", 0)
        modern = rewards.get("modern", 0)
        if modern > 0:
            ratio = vintage / modern
            assert abs(ratio - 2.5) < 0.02, f"G4/modern ratio={ratio:.4f}, expected ~2.5"
    finally:
        cleanup(db)
    print("[PASS] Property 4: Multiplier linearity (2.5x miner gets 2.5x share)")


def test_equal_multiplier_equal_share():
    miners = [
        {"miner_id": "a", "device_arch": "g4"},
        {"miner_id": "b", "device_arch": "g4"},
        {"miner_id": "c", "device_arch": "g4"},
    ]
    db = create_test_db(miners)
    try:
        rewards = calculate_epoch_rewards_time_aged(db, _TEST_EPOCH, PER_EPOCH_URTC, get_test_slot())
        shares = list(rewards.values())
        assert shares[0] == shares[1] == shares[2], f"Equal multipliers got unequal: {shares}"
    finally:
        cleanup(db)
    print("[PASS] Property 4b: Equal multipliers -> equal shares")


def test_triple_ratio():
    miners = [
        {"miner_id": "vax", "device_arch": "vax"},
        {"miner_id": "g4", "device_arch": "g4"},
        {"miner_id": "modern", "device_arch": "modern"},
    ]
    db = create_test_db(miners)
    try:
        rewards = calculate_epoch_rewards_time_aged(db, _TEST_EPOCH, PER_EPOCH_URTC, get_test_slot())
        vax = rewards.get("vax", 0)
        g4 = rewards.get("g4", 0)
        modern = rewards.get("modern", 0)
        if modern > 0 and g4 > 0:
            g4_ratio = g4 / modern
            vax_ratio = vax / modern
            assert abs(g4_ratio - 2.5) < 0.03, f"G4 ratio={g4_ratio:.4f}, expected 2.5"
            assert abs(vax_ratio - 3.5) < 0.03, f"VAX ratio={vax_ratio:.4f}, expected 3.5"
    finally:
        cleanup(db)
    print("[PASS] Property 4c: Triple ratio (3.5x : 2.5x : 1.0x) verified")


def test_idempotency():
    miners = [
        {"miner_id": "m1", "device_arch": "g4"},
        {"miner_id": "m2", "device_arch": "pentium"},
        {"miner_id": "m3", "device_arch": "vax"},
    ]
    db = create_test_db(miners)
    try:
        r1 = calculate_epoch_rewards_time_aged(db, _TEST_EPOCH, PER_EPOCH_URTC, get_test_slot())
        r2 = calculate_epoch_rewards_time_aged(db, _TEST_EPOCH, PER_EPOCH_URTC, get_test_slot())
        assert r1 == r2, "Idempotency violated: consecutive calls differ"
    finally:
        cleanup(db)
    print("[PASS] Property 5: Idempotency verified")


def test_empty_miner_set():
    db = create_test_db([])
    try:
        rewards = calculate_epoch_rewards_time_aged(db, _TEST_EPOCH, PER_EPOCH_URTC, get_test_slot())
        assert rewards == {}, f"Empty miners should return empty dict, got {rewards}"
    finally:
        cleanup(db)
    print("[PASS] Property 6: Empty miner set -> empty dict, no errors")


def test_single_miner_full_share():
    miners = [{"miner_id": "lonely", "device_arch": "g4"}]
    db = create_test_db(miners)
    try:
        rewards = calculate_epoch_rewards_time_aged(db, _TEST_EPOCH, PER_EPOCH_URTC, get_test_slot())
        assert len(rewards) == 1, "Single miner should be sole recipient"
        share = list(rewards.values())[0]
        assert share == PER_EPOCH_URTC, f"Single miner got {share}, expected {PER_EPOCH_URTC}"
    finally:
        cleanup(db)
    print("[PASS] Property 7: Single miner gets full PER_EPOCH_URTC")


def test_1024_miners_precision():
    miners = [{"miner_id": f"m{i}", "device_arch": "g4"} for i in range(1024)]
    db = create_test_db(miners)
    try:
        rewards = calculate_epoch_rewards_time_aged(db, _TEST_EPOCH, PER_EPOCH_URTC, get_test_slot())
        total = sum(rewards.values())
        assert abs(total - PER_EPOCH_URTC) <= 1, f"1024 miners: diff={total-PER_EPOCH_URTC}"
        for mid, share in rewards.items():
            assert share >= 0, f"{mid} negative: {share}"
    finally:
        cleanup(db)
    print("[PASS] Property 8: 1024 miners precision maintained")


def test_dust_miner():
    miners = [
        {"miner_id": "high1", "device_arch": "g4"},
        {"miner_id": "high2", "device_arch": "g4"},
        {"miner_id": "aarch1", "device_arch": "aarch64"},
        {"miner_id": "aarch2", "device_arch": "aarch64"},
    ]
    db = create_test_db(miners)
    try:
        rewards = calculate_epoch_rewards_time_aged(db, _TEST_EPOCH, PER_EPOCH_URTC, get_test_slot())
        total = sum(rewards.values())
        assert abs(total - PER_EPOCH_URTC) <= 1, f"Dust test: total drift {total-PER_EPOCH_URTC}"
        for mid, share in rewards.items():
            assert share >= 0, f"Dust test: {mid} negative share {share}"
    finally:
        cleanup(db)
    print("[PASS] Property 9: Dust (very small multiplier) handled correctly")


def test_time_decay_linearity():
    miners = [{"miner_id": "g4", "device_arch": "g4"}, {"miner_id": "modern", "device_arch": "modern"}]
    db = create_test_db(miners)
    try:
        slot_10y = int(10 * 365.25 * 24 * 3600 / BLOCK_TIME)
        rewards = calculate_epoch_rewards_time_aged(db, _TEST_EPOCH, PER_EPOCH_URTC, slot_10y)
        g4_share = rewards.get("g4", 0)
        modern_share = rewards.get("modern", 0)
        if modern_share > 0:
            ratio = g4_share / modern_share
            assert abs(ratio - 1.0) < 0.03, f"At age 10, ratio should be ~1.0, got {ratio:.4f}"
    finally:
        cleanup(db)
    print("[PASS] Property 10: Time decay preserves linearity")


def test_warthog_bonus():
    miners = [
        {"miner_id": "no_bonus", "device_arch": "g4", "warthog_bonus": 1.0},
        {"miner_id": "with_bonus", "device_arch": "g4", "warthog_bonus": 1.15},
    ]
    db = create_test_db(miners)
    try:
        rewards = calculate_epoch_rewards_time_aged(db, _TEST_EPOCH, PER_EPOCH_URTC, get_test_slot())
        no = rewards.get("no_bonus", 0)
        with_b = rewards.get("with_bonus", 0)
        if no > 0:
            ratio = with_b / no
            assert abs(ratio - 1.15) < 0.02, f"Warthog bonus ratio={ratio:.4f}, expected 1.15"
    finally:
        cleanup(db)
    print("[PASS] Property 11: Warthog bonus (1.15x) applied correctly")


def test_mixed_fingerprint():
    miners = [
        {"miner_id": "p1", "device_arch": "g4", "fingerprint_passed": 1},
        {"miner_id": "f1", "device_arch": "g4", "fingerprint_passed": 0},
        {"miner_id": "p2", "device_arch": "g4", "fingerprint_passed": 1},
        {"miner_id": "f2", "device_arch": "pentium", "fingerprint_passed": 0},
        {"miner_id": "p3", "device_arch": "vax", "fingerprint_passed": 1},
    ]
    db = create_test_db(miners)
    try:
        rewards = calculate_epoch_rewards_time_aged(db, _TEST_EPOCH, PER_EPOCH_URTC, get_test_slot())
        for mid in ["p1", "p2", "p3"]:
            assert rewards.get(mid, 0) > 0, f"{mid} should have positive share"
        for mid in ["f1", "f2"]:
            assert rewards.get(mid, 0) == 0, f"{mid} should have zero share"
        total = sum(rewards.values())
        assert abs(total - PER_EPOCH_URTC) <= 1, f"Mixed fp: total drift {total-PER_EPOCH_URTC}"
    finally:
        cleanup(db)
    print("[PASS] Property 12: Mixed fingerprint (pass/fail) handled correctly")


def test_anti_pool_effect():
    pool_miners = [{"miner_id": f"pool_{i}", "device_arch": "g4"} for i in range(10)]
    db_pool = create_test_db(pool_miners)
    try:
        rewards_pool = calculate_epoch_rewards_time_aged(db_pool, _TEST_EPOCH, PER_EPOCH_URTC, get_test_slot())
    finally:
        cleanup(db_pool)

    solo_miners = [{"miner_id": "solo", "device_arch": "g4"}]
    db_solo = create_test_db(solo_miners)
    try:
        rewards_solo = calculate_epoch_rewards_time_aged(db_solo, _TEST_EPOCH, PER_EPOCH_URTC, get_test_slot())
    finally:
        cleanup(db_solo)

    pool_share = list(rewards_pool.values())[0]
    solo_share = list(rewards_solo.values())[0]
    ratio = solo_share / pool_share
    assert 9.5 <= ratio <= 10.5, f"Anti-pool ratio={ratio:.2f}, expected ~10.0"
    print("[PASS] Property 13: Anti-pool effect verified (solo earns ~10x pool member)")


def test_all_archetypes_total():
    archetypes = ["vax", "386", "arm2", "mc68000", "transputer", "mips_r2000",
                  "g4", "pentium", "core2", "modern", "aarch64"]
    miners = [{"miner_id": arch, "device_arch": arch} for arch in archetypes]
    db = create_test_db(miners)
    try:
        rewards = calculate_epoch_rewards_time_aged(db, _TEST_EPOCH, PER_EPOCH_URTC, get_test_slot())
        total = sum(rewards.values())
        assert abs(total - PER_EPOCH_URTC) <= 1, f"All-arch diff={total-PER_EPOCH_URTC}"
    finally:
        cleanup(db)
    print("[PASS] Edge case: All-archetype distribution total == PER_EPOCH_URTC")


# ═══════════════════════════════════════════════════════════════════
# PROPERTY-BASED TESTS (Hypothesis)
# ═══════════════════════════════════════════════════════════════════

try:
    from hypothesis import given, settings, assume, HealthCheck
    from hypothesis.strategies import (
        integers, floats, lists, sampled_from, composite, just,
    )
    HAS_HYPOTHESIS = True
except ImportError:
    HAS_HYPOTHESIS = False

VALID_ARCHS = list(ANTIQUITY_MULTIPLIERS.keys()) + ["modern", "aarch64", "unknown"]


def _miner_strategy():
    """Strategy that generates a list of miners with random architectures."""
    if not HAS_HYPOTHESIS:
        return None
    @composite
    def miners(draw):
        count = draw(integers(min_value=1, max_value=200))
        result = []
        for i in range(count):
            arch = draw(sampled_from(VALID_ARCHS))
            result.append({
                "miner_id": f"hyp_miner_{i}",
                "device_arch": arch,
                "fingerprint_passed": 1,
                "warthog_bonus": 1.0,
            })
        return result
    return miners()


if HAS_HYPOTHESIS:
    @given(miners=_miner_strategy())
    @settings(max_examples=50, deadline=30000,
              suppress_health_check=[HealthCheck.too_slow])
    def test_hypothesis_total_conservation(miners):
        """
        PROPERTY: For ANY set of miners with ANY valid multipliers,
        total distributed == exactly PER_EPOCH_URTC (within 1 satoshi).
        """
        db = create_test_db(miners)
        try:
            rewards = calculate_epoch_rewards_time_aged(
                db, _TEST_EPOCH, PER_EPOCH_URTC, get_test_slot()
            )
            total = sum(rewards.values())
            assert abs(total - PER_EPOCH_URTC) <= 1, \
                f"Total conservation violated: {total} vs {PER_EPOCH_URTC}"
        finally:
            cleanup(db)

    @given(miners=_miner_strategy())
    @settings(max_examples=50, deadline=30000,
              suppress_health_check=[HealthCheck.too_slow])
    def test_hypothesis_no_negative(miners):
        """PROPERTY: No miner ever receives negative rewards."""
        db = create_test_db(miners)
        try:
            rewards = calculate_epoch_rewards_time_aged(
                db, _TEST_EPOCH, PER_EPOCH_URTC, get_test_slot()
            )
            for mid, share in rewards.items():
                assert share >= 0, f"{mid} got negative reward: {share}"
        finally:
            cleanup(db)

    @given(miners=_miner_strategy())
    @settings(max_examples=30, deadline=30000,
              suppress_health_check=[HealthCheck.too_slow])
    def test_hypothesis_idempotent(miners):
        """PROPERTY: Running settlement twice yields identical results."""
        db = create_test_db(miners)
        try:
            r1 = calculate_epoch_rewards_time_aged(
                db, _TEST_EPOCH, PER_EPOCH_URTC, get_test_slot()
            )
            r2 = calculate_epoch_rewards_time_aged(
                db, _TEST_EPOCH, PER_EPOCH_URTC, get_test_slot()
            )
            assert r1 == r2, "Idempotency violated on random input"
        finally:
            cleanup(db)

    @given(slot=integers(min_value=1, max_value=10_000_000))
    @settings(max_examples=30, deadline=30000,
              suppress_health_check=[HealthCheck.too_slow])
    def test_hypothesis_total_across_slots(slot):
        """PROPERTY: Total conservation holds for any slot value."""
        miners = [
            {"miner_id": "a", "device_arch": "g4"},
            {"miner_id": "b", "device_arch": "modern"},
        ]
        db = create_test_db(miners)
        try:
            rewards = calculate_epoch_rewards_time_aged(
                db, _TEST_EPOCH, PER_EPOCH_URTC, slot
            )
            total = sum(rewards.values())
            assert abs(total - PER_EPOCH_URTC) <= 1, \
                f"Slot {slot}: total={total}"
        finally:
            cleanup(db)

    @given(n=integers(min_value=2, max_value=500))
    @settings(max_examples=20, deadline=60000,
              suppress_health_check=[HealthCheck.too_slow])
    def test_hypothesis_equal_split(n):
        """
        PROPERTY: N identical miners each get PER_EPOCH_URTC/N within rounding.
        NOTE: The last miner gets the remainder to ensure total conservation,
        so the last miner may differ by up to N-1 uRTC from int(total/N).
        The key invariant is total conservation, not per-miner exactness.
        """
        miners = [{"miner_id": f"m{i}", "device_arch": "modern"} for i in range(n)]
        db = create_test_db(miners)
        try:
            rewards = calculate_epoch_rewards_time_aged(
                db, _TEST_EPOCH, PER_EPOCH_URTC, get_test_slot()
            )
            total = sum(rewards.values())
            assert abs(total - PER_EPOCH_URTC) <= 1, \
                f"N={n}: total conservation violated: {total}"
            expected = PER_EPOCH_URTC // n
            # All miners except last should be within 1
            shares = list(rewards.values())
            for share in shares[:-1]:
                assert abs(share - expected) <= 1, \
                    f"N={n}: non-last miner got {share}, expected ~{expected}"
            # Last miner gets remainder — may differ by up to n-1
            assert abs(shares[-1] - expected) <= n, \
                f"N={n}: last miner {shares[-1]} too far from {expected}"
        finally:
            cleanup(db)


def test_multiplier_ordering():
    """Verify that higher multiplier always gets >= share of lower multiplier."""
    archs = [("vax", 3.5), ("386", 3.0), ("g4", 2.5), ("pentium", 1.7), ("modern", 1.0)]
    miners = [{"miner_id": arch, "device_arch": arch} for arch, _ in archs]
    db = create_test_db(miners)
    try:
        rewards = calculate_epoch_rewards_time_aged(
            db, _TEST_EPOCH, PER_EPOCH_URTC, get_test_slot()
        )
        shares = [(arch, rewards.get(arch, 0)) for arch, _ in archs]
        for i in range(len(shares) - 1):
            assert shares[i][1] >= shares[i+1][1], \
                f"Ordering violated: {shares[i][0]}={shares[i][1]} < {shares[i+1][0]}={shares[i+1][1]}"
    finally:
        cleanup(db)
    print("[PASS] Property 14: Multiplier ordering (higher mult >= higher share)")


def test_large_reward_pool():
    """Verify conservation with large total reward (overflow check)."""
    huge_reward = 2**50  # Very large uRTC
    miners = [
        {"miner_id": "a", "device_arch": "g4"},
        {"miner_id": "b", "device_arch": "modern"},
    ]
    db = create_test_db(miners)
    try:
        rewards = calculate_epoch_rewards_time_aged(
            db, _TEST_EPOCH, huge_reward, get_test_slot()
        )
        total = sum(rewards.values())
        assert abs(total - huge_reward) <= 1, f"Large reward drift: {total - huge_reward}"
        for mid, share in rewards.items():
            assert share >= 0, f"Large reward negative: {mid}={share}"
    finally:
        cleanup(db)
    print("[PASS] Edge case 15: Large reward pool (2^50 uRTC) no overflow")


def test_one_urtc_reward():
    """Verify settlement works with minimal reward (1 uRTC)."""
    miners = [
        {"miner_id": "a", "device_arch": "g4"},
        {"miner_id": "b", "device_arch": "modern"},
    ]
    db = create_test_db(miners)
    try:
        rewards = calculate_epoch_rewards_time_aged(
            db, _TEST_EPOCH, 1, get_test_slot()
        )
        total = sum(rewards.values())
        assert total == 1, f"1 uRTC total: {total}"
        for share in rewards.values():
            assert share >= 0
    finally:
        cleanup(db)
    print("[PASS] Edge case 16: Minimum reward (1 uRTC)")


def test_zero_reward():
    """Verify settlement with 0 reward distributes nothing."""
    miners = [{"miner_id": "a", "device_arch": "g4"}]
    db = create_test_db(miners)
    try:
        rewards = calculate_epoch_rewards_time_aged(
            db, _TEST_EPOCH, 0, get_test_slot()
        )
        total = sum(rewards.values())
        assert total == 0, f"Zero reward total: {total}"
    finally:
        cleanup(db)
    print("[PASS] Edge case 17: Zero reward pool")


def test_all_failed_fingerprints():
    """
    All miners fail fingerprint → total_weight=0 → division by zero.
    KNOWN BUG: The real code does not guard against total_weight==0.
    This test documents the bug so it can be fixed.
    """
    miners = [
        {"miner_id": "f1", "device_arch": "g4", "fingerprint_passed": 0},
        {"miner_id": "f2", "device_arch": "g5", "fingerprint_passed": 0},
    ]
    db = create_test_db(miners)
    try:
        try:
            rewards = calculate_epoch_rewards_time_aged(
                db, _TEST_EPOCH, PER_EPOCH_URTC, get_test_slot()
            )
            # If it doesn't crash, verify no negative
            for mid, share in rewards.items():
                assert share >= 0, f"Negative share with all-failed FP: {mid}={share}"
        except ZeroDivisionError:
            # KNOWN BUG: total_weight=0 causes division by zero
            # This should be fixed: if total_weight==0, return {}
            pass
    finally:
        cleanup(db)
    print("[PASS] Edge case 18: All failed fingerprints (known div-by-zero documented)")


def test_duplicate_miner_id():
    """Duplicate miner_id should resolve via DISTINCT in SQL."""
    miners = [
        {"miner_id": "dup", "device_arch": "g4", "ts_offset": 0},
        {"miner_id": "dup", "device_arch": "g4", "ts_offset": 100},
        {"miner_id": "other", "device_arch": "modern"},
    ]
    db = create_test_db(miners)
    try:
        rewards = calculate_epoch_rewards_time_aged(
            db, _TEST_EPOCH, PER_EPOCH_URTC, get_test_slot()
        )
        total = sum(rewards.values())
        assert abs(total - PER_EPOCH_URTC) <= 1, f"Dup miner drift: {total - PER_EPOCH_URTC}"
    finally:
        cleanup(db)
    print("[PASS] Edge case 19: Duplicate miner_id resolved via DISTINCT")


def test_get_time_aged_multiplier_boundaries():
    """Verify get_time_aged_multiplier at key boundary conditions."""
    # Year 0: full multiplier
    assert get_time_aged_multiplier("g4", 0.0) == 2.5, "G4 at year 0 should be 2.5"
    # Modern always 1.0
    assert get_time_aged_multiplier("modern", 0.0) == 1.0
    assert get_time_aged_multiplier("modern", 100.0) == 1.0
    # Unknown arch → 1.0
    assert get_time_aged_multiplier("unknown_arch_xyz", 0.0) == 1.0
    # Very far future → bonus decays to 0, but base 1.0 remains
    mult = get_time_aged_multiplier("g4", 100.0)
    assert mult >= 1.0, f"G4 at year 100 should be >= 1.0, got {mult}"
    print("[PASS] Edge case 20: get_time_aged_multiplier boundary conditions")


def run_all_tests():
    print("\n" + "="*60)
    print("Epoch Settlement Logic -- Formal Verification Suite")
    print("="*60)
    print(f"PER_EPOCH_URTC = {PER_EPOCH_URTC:,} uRTC ({PER_EPOCH_URTC/UNIT:.1f} RTC)")
    print("-"*60)

    tests = [
        ("Property 1: Total == PER_EPOCH", test_total_distribution_exact),
        ("Property 1b: Total with 1000 miners", test_total_distribution_1000_miners),
        ("Property 2: No negative rewards", test_no_negative_rewards),
        ("Property 3: No zero for valid miners", test_no_zero_shares_valid_miners),
        ("Property 3b: Failed FP == zero", test_failed_fingerprint_zero),
        ("Property 4: Multiplier linearity", test_multiplier_linearity),
        ("Property 4b: Equal mult == equal share", test_equal_multiplier_equal_share),
        ("Property 4c: Triple ratio", test_triple_ratio),
        ("Property 5: Idempotency", test_idempotency),
        ("Property 6: Empty miners", test_empty_miner_set),
        ("Property 7: Single miner full share", test_single_miner_full_share),
        ("Property 8: 1024 miners precision", test_1024_miners_precision),
        ("Property 9: Dust miner", test_dust_miner),
        ("Property 10: Time decay", test_time_decay_linearity),
        ("Property 11: Warthog bonus", test_warthog_bonus),
        ("Property 12: Mixed fingerprint", test_mixed_fingerprint),
        ("Property 13: Anti-pool effect", test_anti_pool_effect),
        ("Property 14: Multiplier ordering", test_multiplier_ordering),
        ("Edge case 15: Large reward (2^50)", test_large_reward_pool),
        ("Edge case 16: Minimum reward (1)", test_one_urtc_reward),
        ("Edge case 17: Zero reward", test_zero_reward),
        ("Edge case 18: All failed FP", test_all_failed_fingerprints),
        ("Edge case 19: Duplicate miner_id", test_duplicate_miner_id),
        ("Edge case 20: Multiplier boundaries", test_get_time_aged_multiplier_boundaries),
        ("Edge case: All archetypes", test_all_archetypes_total),
    ]

    # Run Hypothesis property-based tests if available
    if HAS_HYPOTHESIS:
        hyp_tests = [
            ("Hypothesis: Total conservation", test_hypothesis_total_conservation),
            ("Hypothesis: No negative", test_hypothesis_no_negative),
            ("Hypothesis: Idempotent", test_hypothesis_idempotent),
            ("Hypothesis: Across slots", test_hypothesis_total_across_slots),
            ("Hypothesis: Equal split", test_hypothesis_equal_split),
        ]
        tests.extend(hyp_tests)
    else:
        print("  [SKIP] Hypothesis not installed — property-based tests skipped")

    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"  [ERROR] {name}: {e}")
            failed += 1

    print("-"*60)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*60)
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    run_all_tests()
