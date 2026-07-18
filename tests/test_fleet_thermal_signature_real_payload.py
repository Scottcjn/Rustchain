# SPDX-License-Identifier: MIT
"""Regression: fleet thermal_signature must be populated from the real payload.

`record_fleet_signals_from_request` read `thermal_drift.data.entropy` /
`drift_magnitude`. No producer in the repo emits either key: `check_thermal_drift`
(node/fingerprint_checks.py, and identically in every miner build) emits
`cold_avg_ns / hot_avg_ns / cold_stdev / hot_stdev / drift_ratio`.

So `thermal_signature` was written NULL for every real attestation, and the thermal
branch of `_detect_fingerprint_similarity` (`if sig_a.get("thermal_signature") and
sig_b.get("thermal_signature")`) could never be true — the detector silently ran on
3 of its 4 signals while still requiring `shared_hashes >= 2`.

Every existing fleet test fabricates the consumer's imaginary `{"entropy": ...}`
schema, so the green suite proved nothing here. These tests build the payload from
`check_thermal_drift`'s actual output shape instead.
"""
import os
import sqlite3
import sys
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO, "rips", "python", "rustchain"))
sys.path.insert(0, os.path.join(REPO, "node"))

import fleet_immune_system as fis


def _real_thermal_payload(drift_ratio):
    """The shape check_thermal_drift actually returns (node/fingerprint_checks.py)."""
    return {
        "checks": {
            "thermal_drift": {
                "data": {
                    "cold_avg_ns": 1_000_000,
                    "hot_avg_ns": int(1_000_000 * drift_ratio),
                    "cold_stdev": 5000,
                    "hot_stdev": 4800,
                    "drift_ratio": round(drift_ratio, 4),
                }
            }
        }
    }


class ThermalSignatureFromRealPayloadTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db = sqlite3.connect(self.path)
        self.addCleanup(lambda: os.path.exists(self.path) and os.unlink(self.path))
        self.addCleanup(self.db.close)

    def _record(self, miner, drift_ratio, ip="10.0.0.1"):
        fis.record_fleet_signals_from_request(
            self.db, miner=miner, epoch=1,
            fingerprint=_real_thermal_payload(drift_ratio),
            attest_ts=1_700_000_000, ip_address=ip,
        )

    def _thermal(self, miner):
        row = self.db.execute(
            "SELECT thermal_signature FROM fleet_signals WHERE miner = ?", (miner,)
        ).fetchone()
        return row[0] if row else None

    def test_real_producer_payload_populates_thermal_signature(self):
        self._record("MINER_A", 1.0523)
        self.assertIsNotNone(
            self._thermal("MINER_A"),
            "thermal_signature is NULL for a real check_thermal_drift payload — "
            "the consumer reads keys no producer emits",
        )
        self.assertAlmostEqual(self._thermal("MINER_A"), 1.0523, places=4)

    def test_legacy_entropy_key_still_wins(self):
        """Legacy payloads must keep working (same tolerance as hardware_binding_v2)."""
        fis.record_fleet_signals_from_request(
            self.db, miner="LEGACY", epoch=1,
            fingerprint={"checks": {"thermal_drift": {"data": {"entropy": 0.42,
                                                              "drift_ratio": 1.05}}}},
            attest_ts=1_700_000_000, ip_address="10.0.0.2",
        )
        self.assertAlmostEqual(self._thermal("LEGACY"), 0.42, places=4)

    def test_absent_thermal_check_stays_null(self):
        fis.record_fleet_signals_from_request(
            self.db, miner="NO_THERMAL", epoch=1, fingerprint={"checks": {}},
            attest_ts=1_700_000_000, ip_address="10.0.0.3",
        )
        self.assertIsNone(self._thermal("NO_THERMAL"))

    def test_thermal_branch_of_similarity_detector_can_fire(self):
        """End-to-end: a cloned fleet's near-identical thermal profiles must count.

        Six machines on one /24 with thermal ratios inside the detector's 10%
        band. On main every thermal_signature is NULL, so this signal contributes
        nothing to `shared_hashes` and the fleet scores lower than it should.
        """
        for i in range(6):
            self._record(f"CLONE_{i}", 1.0500 + i * 0.0002, ip=f"10.0.0.{10 + i}")

        stored = self.db.execute(
            "SELECT COUNT(*) FROM fleet_signals WHERE epoch = 1 "
            "AND thermal_signature IS NOT NULL"
        ).fetchone()[0]
        self.assertEqual(
            stored, 6,
            "thermal_signature NULL for real payloads -> the detector's thermal "
            "branch is unreachable and fleet detection runs on 3 of 4 signals",
        )

        scores = fis.compute_fleet_scores(self.db, epoch=1)
        self.assertEqual(len(scores), 6)
        for miner, score in scores.items():
            self.assertGreater(
                score, 0.0,
                f"{miner} scored {score} — a 6-machine clone fleet on one subnet "
                "should not read as solo",
            )


if __name__ == "__main__":
    unittest.main()
