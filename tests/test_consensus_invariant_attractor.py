#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reference adversarial tests for the consensus invariant attractor bounty."""

import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "node"))

from anti_double_mining import compute_machine_identity_hash, select_representative_miner
from tests.consensus_invariant_harness import (
    ConsensusInvariantCase,
    assert_consensus_invariant,
)


class TestConsensusInvariantAttractor(unittest.TestCase):
    def test_consensus__machine_identity_stable__fingerprint_key_reorder(self):
        def oracle():
            left = {
                "checks": {
                    "clock_drift": {"data": {"mean_ns": 101.2345, "cv": 0.00123456}},
                    "cpu_serial": {"data": {"serial": "BOARD-SERIAL-42"}},
                }
            }
            right = {
                "checks": {
                    "cpu_serial": {"data": {"serial": "BOARD-SERIAL-42"}},
                    "clock_drift": {"data": {"cv": 0.00123456, "mean_ns": 101.2345}},
                }
            }

            self.assertEqual(
                compute_machine_identity_hash("ppc_g4", left),
                compute_machine_identity_hash("ppc_g4", right),
            )

        assert_consensus_invariant(
            ConsensusInvariantCase(
                invariant_id="consensus.machine_identity.canonical_fingerprint",
                statement="Machine identity is invariant to JSON object ordering.",
                fixture="Two semantically identical hardware fingerprints with reordered keys.",
                adversarial_move="Reorder nested fingerprint check keys and data keys.",
                oracle=oracle,
            )
        )

    def test_consensus__machine_identity_separates__architecture_alias(self):
        def oracle():
            fingerprint = {
                "checks": {
                    "cpu_serial": {"data": {"serial": "BOARD-SERIAL-99"}},
                    "cache_timing": {"data": {"hierarchy_ratio": 2.5}},
                }
            }

            self.assertNotEqual(
                compute_machine_identity_hash("ppc_g4", fingerprint),
                compute_machine_identity_hash("ppc_g5", fingerprint),
            )

        assert_consensus_invariant(
            ConsensusInvariantCase(
                invariant_id="consensus.machine_identity.architecture_separation",
                statement="A physical fingerprint under a different device architecture is a different machine identity.",
                fixture="One stable fingerprint evaluated under two architecture labels.",
                adversarial_move="Replay the same fingerprint while changing only device_arch.",
                oracle=oracle,
            )
        )

    def test_consensus__representative_selection_idempotent__input_order_shuffle(self):
        def oracle():
            conn = sqlite3.connect(":memory:")
            try:
                conn.executescript(
                    """
                    CREATE TABLE miner_attest_recent (
                        miner TEXT PRIMARY KEY,
                        device_arch TEXT,
                        ts_ok INTEGER,
                        entropy_score REAL
                    );
                    CREATE TABLE epoch_enroll (
                        epoch INTEGER,
                        miner_pk TEXT,
                        weight REAL,
                        PRIMARY KEY (epoch, miner_pk)
                    );
                    """
                )
                rows = [
                    ("alias-high-entropy", 1.0, 1728000200, 0.99),
                    ("canonical-high-weight", 5.0, 1728000000, 0.10),
                    ("alias-newer", 1.0, 1728000300, 0.50),
                ]
                for miner, weight, ts_ok, entropy in rows:
                    conn.execute(
                        "INSERT INTO miner_attest_recent (miner, device_arch, ts_ok, entropy_score) VALUES (?, ?, ?, ?)",
                        (miner, "ppc_g4", ts_ok, entropy),
                    )
                    conn.execute(
                        "INSERT INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?, ?, ?)",
                        (9, miner, weight),
                    )
                conn.commit()

                forward = [row[0] for row in rows]
                reversed_order = list(reversed(forward))

                self.assertEqual(
                    select_representative_miner(conn, forward, epoch=9),
                    "canonical-high-weight",
                )
                self.assertEqual(
                    select_representative_miner(conn, reversed_order, epoch=9),
                    "canonical-high-weight",
                )
            finally:
                conn.close()

        assert_consensus_invariant(
            ConsensusInvariantCase(
                invariant_id="consensus.duplicate_miner.representative_idempotent",
                statement="Duplicate-miner representative selection is deterministic and preserves the highest enrolled epoch weight.",
                fixture="Three aliases for one machine in an in-memory epoch enrollment snapshot.",
                adversarial_move="Shuffle candidate miner order and give aliases fresher timestamps or higher entropy.",
                oracle=oracle,
            )
        )


if __name__ == "__main__":
    unittest.main()
