"""Repro: RIP-200 v2 drops the modern_x86 loyalty bonus from reward weighting.

Module docstring of rip_200_round_robin_1cpu1vote_v2.py states:
    "Modern x86 (<5 years): Starts at 0.1x, earns 15%/year loyalty bonus"
and __main__ prints "Loyalty bonuses do NOT decay (reward for commitment)".

calculate_epoch_rewards_v2 computes the loyalty-aware multiplier into
`base_mult` (passing db_path + miner_id) but then discards it, using
`get_time_aged_multiplier(arch, chain_age_years, device_info)` instead --
which internally calls get_device_multiplier(device_info) WITHOUT db_path /
miner_id, so get_loyalty_bonus() is never reached and the weight collapses
back to the 0.1 base rate.
"""

import importlib.util
import os
import sqlite3
import sys
import time

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SPEC = importlib.util.spec_from_file_location(
    "rip200_v2", os.path.join(_REPO, "node", "rip_200_round_robin_1cpu1vote_v2.py")
)
rip200_v2 = importlib.util.module_from_spec(_SPEC)
sys.modules["rip200_v2"] = rip200_v2
_SPEC.loader.exec_module(rip200_v2)

SECONDS_PER_YEAR = 365.25 * 24 * 3600


def _make_db(path, miners):
    """miners: list of (miner_id, arch, year, first_attest_ts)."""
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE miner_attest_recent ("
        " miner TEXT, device_arch TEXT, device_family TEXT,"
        " device_model TEXT, device_year INTEGER, ts_ok INTEGER)"
    )
    conn.execute("CREATE TABLE miner_attest_history (miner TEXT, ts_ok INTEGER)")

    # Epoch 0 window, so attestations must land inside it.
    epoch_ts = rip200_v2.GENESIS_TIMESTAMP + 100

    for miner_id, arch, year, first_attest in miners:
        conn.execute(
            "INSERT INTO miner_attest_recent VALUES (?,?,?,?,?,?)",
            (miner_id, arch, "", "", year, epoch_ts),
        )
        conn.execute(
            "INSERT INTO miner_attest_history VALUES (?,?)", (miner_id, first_attest)
        )
    conn.commit()
    conn.close()


def test_loyalty_bonus_is_honoured_in_epoch_reward_weight(tmp_path):
    """A 4-year-loyal modern_x86 miner must out-earn a brand-new one."""
    db = str(tmp_path / "chain.db")
    now = int(time.time())

    # veteran: first attested 4 years ago -> loyalty = 4 * 0.15 = 0.60
    #          expected weight = 0.1 + 0.60 = 0.70
    # rookie:  first attested today       -> loyalty ~ 0.0, weight = 0.1
    _make_db(
        db,
        [
            ("veteran", "modern_x86", 2023, now - int(4 * SECONDS_PER_YEAR)),
            ("rookie", "modern_x86", 2023, now),
        ],
    )

    # Sanity: the loyalty-aware path itself works when given db_path+miner_id.
    veteran_mult = rip200_v2.get_device_multiplier(
        {"arch": "modern_x86", "year": 2023}, db, "veteran"
    )
    assert veteran_mult == pytest.approx(0.70, abs=0.01), (
        "precondition: get_device_multiplier must grant the loyalty bonus"
    )

    total_reward = 1_500_000  # uRTC
    rewards = rip200_v2.calculate_epoch_rewards_v2(
        db, epoch=0, total_reward_urtc=total_reward, current_slot=10
    )

    assert set(rewards) == {"veteran", "rookie"}
    assert sum(rewards.values()) == total_reward

    # weights 0.70 vs 0.10 -> veteran should receive 87.5% of the pot.
    assert rewards["veteran"] > rewards["rookie"], (
        "loyal miner must earn more than a brand-new miner, got "
        f"veteran={rewards['veteran']} rookie={rewards['rookie']}"
    )
    assert rewards["veteran"] == pytest.approx(total_reward * 0.875, rel=0.01)
    assert rewards["rookie"] == pytest.approx(total_reward * 0.125, rel=0.01)


def test_vintage_weights_unchanged(tmp_path):
    """No regression: PowerPC/vintage weighting must not shift.

    A G4 has a fixed 2.5x base and takes the decay path; the loyalty lookup
    must not touch it. Asserted against the decay formula through the public
    reward path, so this holds both before and after the fix.
    """
    db = str(tmp_path / "chain.db")
    now = int(time.time())
    # The rookie has no loyalty history, so its weight is the flat 0.1 base
    # either way -- isolating the G4 side of the split.
    _make_db(db, [("g4box", "g4", 2003, now), ("rookie", "modern_x86", 2023, now)])

    chain_age = rip200_v2.get_chain_age_years(10)
    expected_g4 = 1.0 + 1.5 * (1 - rip200_v2.DECAY_RATE_PER_YEAR * chain_age)
    expected_share = expected_g4 / (expected_g4 + 0.1)

    total_reward = 1_000_000
    rewards = rip200_v2.calculate_epoch_rewards_v2(
        db, epoch=0, total_reward_urtc=total_reward, current_slot=10
    )
    assert rewards["g4box"] == pytest.approx(total_reward * expected_share, rel=0.01)


def test_null_device_arch_does_not_crash(tmp_path):
    """A loyal miner with a NULL device_arch column must still be weighted.

    calculate_epoch_rewards_v2 passes the raw nullable `device_arch` column
    through as `device_arch`. Once loyalty lifts the base above 0.1, the decay
    branch reads `device_arch.lower()` for the first time, so a NULL arch has
    to be tolerated there.
    """
    db = str(tmp_path / "chain.db")
    now = int(time.time())
    _make_db(db, [("nullarch", None, 2023, now - int(4 * SECONDS_PER_YEAR))])

    rewards = rip200_v2.calculate_epoch_rewards_v2(
        db, epoch=0, total_reward_urtc=1_000_000, current_slot=10
    )
    assert rewards == {"nullarch": 1_000_000}
