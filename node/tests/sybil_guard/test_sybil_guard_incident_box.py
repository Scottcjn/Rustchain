# SPDX-License-Identifier: MIT
"""Incident signature must catch BOTH waves and still clear every honest miner.

Wave 2 (24 wallets, same source addresses) had 4 wallets just outside the
original wave-1-fitted box (clock_drift_cv 0.0080-0.0083, thermal 0.8123). The
box was widened to the generator's likely bounds; these tests pin that.
"""
import json

import sybil_guard as sg
from sg_helpers import load_json


def _profiles(rows):
    return [(r["miner"], json.loads(r["profile_json"])) for r in rows]


def _hit_wallets(rows):
    return {m for m, p in _profiles(rows) if sg.matches_incident_signature(p)}


def test_box_is_the_widened_generator_bounds():
    assert sg.INCIDENT_20260924_BOX == {
        "clock_drift_cv": (0.008, 0.030),
        "thermal_variance": (0.8, 6.0),
        "jitter_cv": (0.015, 0.25),
        "cache_hierarchy_ratio": (1.8, 2.9),
    }


def test_wave2_all_24_wallets_hit():
    rows = load_json("wave2_profiles.json")
    wallets = {r["miner"] for r in rows}
    assert len(wallets) == 24
    assert _hit_wallets(rows) == wallets


def test_wave1_plus_wave2_is_144_of_144(sybil_rows):
    w2 = load_json("wave2_profiles.json")
    all_wallets = {r["miner"] for r in sybil_rows} | {r["miner"] for r in w2}
    assert len(all_wallets) == 144
    assert _hit_wallets(sybil_rows) | _hit_wallets(w2) == all_wallets


def test_widened_box_flags_zero_honest_miners(honest_rows):
    assert _hit_wallets(honest_rows) == set()
    assert len({r["miner"] for r in honest_rows}) == 86


def test_wave2_edge_profiles_that_the_old_box_missed_are_caught():
    old = {"clock_drift_cv": (0.0085, 0.0299), "thermal_variance": (0.8515, 5.9022),
           "jitter_cv": (0.0153, 0.2473), "cache_hierarchy_ratio": (1.8034, 2.8961)}
    missed_by_old = [
        p for _, p in _profiles(load_json("wave2_profiles.json"))
        if not all(lo <= p[m] <= hi for m, (lo, hi) in old.items())
    ]
    assert len(missed_by_old) == 4
    assert all(sg.matches_incident_signature(p) for p in missed_by_old)
