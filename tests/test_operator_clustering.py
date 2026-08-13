#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""RIP-309d: cluster by operator, then ask whether the members are independent.

Every other control here is per-miner, so a farm of N identities is N cheap,
independent trust-building exercises. Clustering makes the operator the unit,
which is what the contributor-tenure panel demanded: per-cluster, not
per-account.

The trap is that co-location proves nothing. On this chain the largest cluster
is an honest lab — seven machines behind one WAN address — so clustering alone
would penalise the most genuine vintage fleet on the network first. The half
that discriminates is whether the members' measurement histories are
independent.

The fixtures below are the REAL medians observed on that lab, and a synthetic
farm built to be plausible rather than easy to catch. If a change makes the
lab look correlated, that change is wrong.
"""

import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = os.path.join(ROOT, "node")
sys.path.insert(0, NODE)

os.environ.setdefault("RC_ADMIN_KEY", "t" * 64)

_spec = importlib.util.spec_from_file_location(
    "rc_node_cl", os.path.join(NODE, "rustchain_v2_integrated_v2.2.1_rip200.py")
)
MOD = importlib.util.module_from_spec(_spec)
sys.modules["rc_node_cl"] = MOD
_spec.loader.exec_module(MOD)

# Medians measured on production, 2026-08-11. A Cobalt Qube 3 (K6-2), a
# POWER8-era host, an HP Victus and a Power Mac G5 — a ~58x spread.
REAL_LAB = {
    "cobalt-qube3-scott": 0.00206,
    "modern-sophiacore-3a168058": 0.07619,
    "victus-x86-scott": 0.11021,
    "g5-selena-179": 0.12266,
}

# One generator, jittered a little. Deliberately not identical, because a
# competent forger would not emit identical values.
SYNTHETIC_FARM = {f"farm_{i}": 0.0800 + (i % 5) * 0.0009 for i in range(12)}


class _DB:
    def __init__(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.conn = sqlite3.connect(self.tmp.name)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            "CREATE TABLE ip_rate_limit(client_ip TEXT, miner_id TEXT, ts INTEGER)")
        self.conn.execute(
            "CREATE TABLE hardware_bindings(hardware_id TEXT, bound_miner TEXT)")
        self.conn.execute("CREATE TABLE miner_macs(miner TEXT, mac_hash TEXT)")
        MOD.ensure_fingerprint_history_table(self.conn)

    def add_miner(self, ip, miner, median, samples=8):
        import json
        self.conn.execute(
            "INSERT INTO ip_rate_limit(client_ip, miner_id, ts) VALUES (?,?,0)",
            (ip, miner))
        for i in range(samples):
            # Physical wobble around the median, well inside the frozen/noisy
            # bands, so history depth is never the thing being tested here.
            v = median * (0.85 + 0.30 * ((i * 7) % 11) / 10.0)
            self.conn.execute(
                "INSERT INTO miner_fingerprint_history(miner, ts, profile_json) "
                "VALUES (?,?,?)",
                (miner, 1786520000 + i * 1800,
                 json.dumps({"clock_drift_cv": v})))
        self.conn.commit()

    def close(self):
        self.conn.close()
        os.unlink(self.tmp.name)


class ClusterBuildingTest(unittest.TestCase):

    def setUp(self):
        self.db = _DB()

    def tearDown(self):
        self.db.close()

    def test_miners_sharing_an_address_are_one_cluster(self):
        for name, med in REAL_LAB.items():
            self.db.add_miner("209.194.25.46", name, med)
        self.db.add_miner("8.8.4.4", "someone-else", 0.09)
        clusters = MOD.build_operator_clusters(self.db.conn)
        big = max(clusters, key=len)
        self.assertEqual(set(big), set(REAL_LAB))
        self.assertIn(["someone-else"], clusters)

    def test_a_solo_miner_is_its_own_cluster(self):
        self.db.add_miner("1.2.3.4", "solo", 0.09)
        self.assertIn(["solo"], MOD.build_operator_clusters(self.db.conn))

    def test_clustering_is_transitive_across_signals(self):
        """Two miners on different IPs sharing hardware are one operator."""
        self.db.add_miner("1.1.1.1", "a", 0.09)
        self.db.add_miner("2.2.2.2", "b", 0.09)
        self.db.conn.execute(
            "INSERT INTO hardware_bindings(hardware_id, bound_miner) VALUES (?,?)",
            ("hw-1", "a"))
        self.db.conn.execute(
            "INSERT INTO hardware_bindings(hardware_id, bound_miner) VALUES (?,?)",
            ("hw-1", "b"))
        self.db.conn.commit()
        clusters = MOD.build_operator_clusters(self.db.conn)
        self.assertTrue(any(set(c) == {"a", "b"} for c in clusters), clusters)


class IndependenceDiscriminatorTest(unittest.TestCase):
    """The half that decides whether clustering means anything."""

    def setUp(self):
        self.db = _DB()

    def tearDown(self):
        self.db.close()

    def test_the_real_lab_reads_as_independent(self):
        """If this ever fails, the control has turned on the honest fleet.

        These are production medians from seven machines behind one address.
        A Qube at 0.002 and a G5 at 0.123 are not one generator.
        """
        for name, med in REAL_LAB.items():
            self.db.add_miner("209.194.25.46", name, med)
        verdict = MOD.cluster_independence(self.db.conn, list(REAL_LAB))
        self.assertEqual(verdict["state"], "independent", verdict)
        self.assertGreater(verdict["spread"], MOD.CLUSTER_INDEPENDENT_SPREAD)

    def test_a_synthetic_farm_reads_as_correlated(self):
        for name, med in SYNTHETIC_FARM.items():
            self.db.add_miner("203.0.113.7", name, med)
        verdict = MOD.cluster_independence(self.db.conn, list(SYNTHETIC_FARM))
        self.assertEqual(verdict["state"], "correlated", verdict)
        self.assertLess(verdict["spread"], MOD.CLUSTER_INDEPENDENT_SPREAD)

    def test_the_two_are_separated_by_a_wide_margin(self):
        """Not a knife-edge: the threshold should not need luck to work."""
        for name, med in REAL_LAB.items():
            self.db.add_miner("209.194.25.46", name, med)
        for name, med in SYNTHETIC_FARM.items():
            self.db.add_miner("203.0.113.7", name, med)
        lab = MOD.cluster_independence(self.db.conn, list(REAL_LAB))["spread"]
        farm = MOD.cluster_independence(self.db.conn, list(SYNTHETIC_FARM))["spread"]
        self.assertGreater(lab, farm * 3,
                           f"lab spread {lab} is not clearly above farm {farm}")

    def test_a_small_group_is_not_judged(self):
        self.db.add_miner("5.5.5.5", "x", 0.09)
        self.db.add_miner("5.5.5.5", "y", 0.09)
        v = MOD.cluster_independence(self.db.conn, ["x", "y"])
        self.assertEqual(v["state"], "too_small_to_judge")

    def test_missing_history_is_not_judged_as_correlated(self):
        v = MOD.cluster_independence(self.db.conn, ["ghost1", "ghost2", "ghost3"])
        self.assertEqual(v["state"], "insufficient_history")


class ObserveOnlyTest(unittest.TestCase):
    """Phase 0 must report, never dock."""

    SRC = os.path.join(NODE, "rustchain_v2_integrated_v2.2.1_rip200.py")

    def test_clustering_does_not_touch_reward_weight(self):
        src = open(self.SRC).read()
        for forbidden in ("hw_weight * cluster", "cluster_independence(conn, members)[",
                          "* cluster_independence"):
            self.assertNotIn(forbidden, src)

    def test_the_false_positive_is_documented_in_the_code(self):
        """An operator running identical machines looks correlated by
        construction. Anyone wiring this to money must meet that first."""
        src = open(self.SRC).read()
        self.assertIn("KNOWN FALSE POSITIVE", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
