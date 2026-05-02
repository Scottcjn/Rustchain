# SPDX-License-Identifier: MIT
"""
Test: P2P attestation sync downgrades entropy_score via unconditional overwrite

Vulnerability:
  rustchain_p2p_gossip.py::_save_attestation_to_db used
  `entropy_score = excluded.entropy_score` on CONFLICT DO UPDATE, allowing
  any P2P peer to overwrite a locally-measured high entropy_score with 0
  (or any lower value) by sending a crafted attestation message.

  entropy_score is security-relevant because:
  - It is the primary tiebreaker in anti-double-mining canonical miner
    selection (anti_double_mining.py: ORDER BY entropy_score DESC).
  - It is loaded into the P2P CRDT state (_load_state_from_db).
  - It is a quality signal in claims eligibility and dashboards.

  A malicious peer can send entropy_score=0 for a victim miner, causing
  the victim's legitimate high-entropy attestation to be deprioritized
  in duplicate detection, potentially allowing the attacker's spoofed
  miner ID to be selected as canonical.

Fix:
  Apply MAX() to entropy_score, same pattern as fingerprint_passed:
    entropy_score = MAX(
        COALESCE(miner_attest_recent.entropy_score, 0),
        excluded.entropy_score)
"""

import os
import sqlite3
import sys
import tempfile
import unittest

# Add node directory to path
NODE_DIR = os.path.join(os.path.dirname(__file__), "..", "node")
sys.path.insert(0, NODE_DIR)


class TestP2PEntropyScoreDowngrade(unittest.TestCase):
    """Validate that P2P-synced attestations cannot downgrade entropy_score."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self._init_db()

    def tearDown(self):
        try:
            os.close(self.db_fd)
        except OSError:
            pass
        os.unlink(self.db_path)

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE miner_attest_recent (
                    miner TEXT PRIMARY KEY,
                    ts_ok INTEGER NOT NULL,
                    device_family TEXT,
                    device_arch TEXT,
                    entropy_score REAL DEFAULT 0,
                    fingerprint_passed INTEGER DEFAULT 0,
                    source_ip TEXT
                );
                CREATE TABLE miner_attest_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    miner TEXT NOT NULL,
                    ts_ok INTEGER NOT NULL,
                    device_family TEXT,
                    device_arch TEXT,
                    entropy_score REAL DEFAULT 0,
                    fingerprint_passed INTEGER DEFAULT 0
                );
            """)

    # ------------------------------------------------------------------
    # Simulate the OLD (vulnerable) P2P save behaviour
    # ------------------------------------------------------------------

    def _p2p_save_old(self, miner, ts_ok, device_family="unknown", device_arch="unknown", entropy_score=0):
        """OLD: unconditional entropy_score overwrite — vulnerable."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO miner_attest_recent
                    (miner, ts_ok, device_family, device_arch, entropy_score)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(miner) DO UPDATE SET
                    ts_ok = excluded.ts_ok,
                    device_family = excluded.device_family,
                    device_arch = excluded.device_arch,
                    entropy_score = excluded.entropy_score,
                    fingerprint_passed = COALESCE(
                        MAX(COALESCE(miner_attest_recent.fingerprint_passed, 0),
                            COALESCE(excluded.fingerprint_passed, miner_attest_recent.fingerprint_passed)),
                        miner_attest_recent.fingerprint_passed)
            """,
                (miner, ts_ok, device_family, device_arch, entropy_score),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Simulate the FIXED P2P save behaviour
    # ------------------------------------------------------------------

    def _p2p_save_fixed(self, miner, ts_ok, device_family="unknown", device_arch="unknown", entropy_score=0):
        """FIXED: MAX() protects entropy_score from downgrade."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO miner_attest_recent
                    (miner, ts_ok, device_family, device_arch, entropy_score)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(miner) DO UPDATE SET
                    ts_ok = excluded.ts_ok,
                    device_family = excluded.device_family,
                    device_arch = excluded.device_arch,
                    entropy_score = MAX(
                        COALESCE(miner_attest_recent.entropy_score, 0),
                        excluded.entropy_score),
                    fingerprint_passed = COALESCE(
                        MAX(COALESCE(miner_attest_recent.fingerprint_passed, 0),
                            COALESCE(excluded.fingerprint_passed, miner_attest_recent.fingerprint_passed)),
                        miner_attest_recent.fingerprint_passed)
            """,
                (miner, ts_ok, device_family, device_arch, entropy_score),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Helpers: simulate local node setting entropy_score directly
    # ------------------------------------------------------------------

    def _local_set_entropy(self, miner, entropy_score, ts_ok=1000):
        """Simulate local node recording a legitimate high-entropy attestation."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO miner_attest_recent
                    (miner, ts_ok, device_family, device_arch, entropy_score, fingerprint_passed)
                VALUES (?, ?, ?, ?, ?, 1)
                ON CONFLICT(miner) DO UPDATE SET
                    ts_ok = excluded.ts_ok,
                    entropy_score = excluded.entropy_score,
                    fingerprint_passed = MAX(miner_attest_recent.fingerprint_passed, excluded.fingerprint_passed)
            """,
                (miner, ts_ok, "powerpc", "ppc", entropy_score),
            )
            conn.commit()

    def _get_entropy(self, miner):
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT entropy_score FROM miner_attest_recent WHERE miner=?", (miner,)).fetchone()
            return row[0] if row else None

    # ------------------------------------------------------------------
    # Tests — demonstrate the bug (OLD behaviour)
    # ------------------------------------------------------------------

    def test_old_p2p_downgrade_zero_erases_high_entropy(self):
        """OLD: malicious P2P peer sends entropy_score=0, erasing legitimate 0.95."""
        miner = "n64-legit-miner"
        self._local_set_entropy(miner, entropy_score=0.95)
        self.assertEqual(self._get_entropy(miner), 0.95)

        # Malicious P2P peer sends attestation with entropy_score=0
        self._p2p_save_old(miner, ts_ok=1001, entropy_score=0)
        score = self._get_entropy(miner)
        self.assertEqual(score, 0, "BUG: P2P peer erased entropy_score from 0.95 → 0 via unconditional overwrite")

    def test_old_p2p_partial_downgrade(self):
        """OLD: attacker sends moderate score to reduce victim's ranking."""
        miner = "n64-legit-miner"
        self._local_set_entropy(miner, entropy_score=0.95)

        # Attacker sends lower but non-zero score
        self._p2p_save_old(miner, ts_ok=1001, entropy_score=0.3)
        score = self._get_entropy(miner)
        self.assertEqual(score, 0.3, "BUG: P2P peer downgraded entropy_score from 0.95 → 0.3")

    # ------------------------------------------------------------------
    # Tests — verify the fix
    # ------------------------------------------------------------------

    def test_fixed_p2p_zero_cannot_downgrade(self):
        """FIXED: malicious P2P peer sends entropy_score=0, high score preserved."""
        miner = "n64-legit-miner"
        self._local_set_entropy(miner, entropy_score=0.95)

        self._p2p_save_fixed(miner, ts_ok=1001, entropy_score=0)
        score = self._get_entropy(miner)
        self.assertEqual(score, 0.95, "FIX: entropy_score=0.95 should be preserved despite P2P peer sending 0")

    def test_fixed_p2p_lower_score_cannot_downgrade(self):
        """FIXED: P2P peer sends lower score, original preserved."""
        miner = "n64-legit-miner"
        self._local_set_entropy(miner, entropy_score=0.95)

        self._p2p_save_fixed(miner, ts_ok=1001, entropy_score=0.3)
        score = self._get_entropy(miner)
        self.assertEqual(score, 0.95, "FIX: entropy_score=0.95 should be preserved despite P2P peer sending 0.3")

    def test_fixed_p2p_higher_score_allowed_to_upgrade(self):
        """FIXED: if P2P peer sends a HIGHER score, it should be accepted."""
        miner = "n64-legit-miner"
        self._local_set_entropy(miner, entropy_score=0.5)

        self._p2p_save_fixed(miner, ts_ok=1001, entropy_score=0.95)
        score = self._get_entropy(miner)
        self.assertEqual(score, 0.95, "FIX: higher entropy_score from P2P peer should be accepted (0.5 → 0.95)")

    def test_fixed_p2p_first_attestation_still_works(self):
        """FIXED: first attestation (no prior record) should still set entropy_score."""
        miner = "n64-new-miner"
        self._p2p_save_fixed(miner, ts_ok=1000, entropy_score=0.7)
        score = self._get_entropy(miner)
        self.assertEqual(score, 0.7, "FIX: first attestation should set entropy_score normally")

    def test_fixed_p2p_null_entropy_treated_as_zero(self):
        """FIXED: NULL entropy_score in existing record treated as 0 for MAX()."""
        miner = "n64-null-entropy"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO miner_attest_recent
                    (miner, ts_ok, device_family, device_arch, entropy_score, fingerprint_passed)
                VALUES (?, ?, ?, ?, NULL, 1)
            """,
                (
                    miner,
                    999,
                    "x86",
                    "modern",
                ),
            )
            conn.commit()

        self._p2p_save_fixed(miner, ts_ok=1000, entropy_score=0.5)
        score = self._get_entropy(miner)
        self.assertEqual(score, 0.5, "FIX: NULL → 0 via COALESCE, so 0.5 should be accepted")

    # ------------------------------------------------------------------
    # End-to-end: anti-double-mining canonical selection impact
    # ------------------------------------------------------------------

    def test_old_behaviour_downgrade_changes_canonical_miner(self):
        """OLD: P2P downgrade causes anti-double-mining to pick wrong canonical miner."""
        # Two miner IDs claiming same machine (simulated double-mining scenario)
        legit = "miner-legit"
        spoof = "miner-spoof"

        # Local node measured high entropy for legit miner
        self._local_set_entropy(legit, entropy_score=0.95, ts_ok=1000)
        # Spoofed attestation with low entropy
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO miner_attest_recent
                    (miner, ts_ok, device_family, device_arch, entropy_score, fingerprint_passed)
                VALUES (?, ?, ?, ?, ?, 0)
            """,
                (spoof, 1001, "x86", "modern", 0.1),
            )
            conn.commit()

        # Before P2P attack: legit has highest entropy
        self.assertEqual(self._get_entropy(legit), 0.95)

        # Attacker sends P2P attestation with entropy_score=0 for legit
        self._p2p_save_old(legit, ts_ok=1002, entropy_score=0)

        # Now spoof has higher entropy (0.1 > 0.0) — wrong canonical miner
        legit_score = self._get_entropy(legit)
        spoof_score = self._get_entropy(spoof)
        self.assertLess(legit_score, spoof_score, "BUG: after P2P downgrade, spoof has higher entropy than legit")

    def test_fixed_behaviour_canonical_miner_preserved(self):
        """FIXED: legit miner keeps highest entropy despite P2P attack."""
        legit = "miner-legit"
        spoof = "miner-spoof"

        self._local_set_entropy(legit, entropy_score=0.95, ts_ok=1000)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO miner_attest_recent
                    (miner, ts_ok, device_family, device_arch, entropy_score, fingerprint_passed)
                VALUES (?, ?, ?, ?, ?, 0)
            """,
                (spoof, 1001, "x86", "modern", 0.1),
            )
            conn.commit()

        # Attacker sends P2P attestation with entropy_score=0 for legit
        self._p2p_save_fixed(legit, ts_ok=1002, entropy_score=0)

        legit_score = self._get_entropy(legit)
        spoof_score = self._get_entropy(spoof)
        self.assertGreater(legit_score, spoof_score, "FIX: legit miner should still have highest entropy (0.95 > 0.1)")


if __name__ == "__main__":
    unittest.main()
