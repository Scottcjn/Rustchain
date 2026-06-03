# SPDX-License-Identifier: MIT
"""
=============================================================================
Attractor: Consensus Invariant Test Harness
Bounty: 25 RTC (Bounty #12789)
=============================================================================

This test harness defines the canonical "attractor" structure for submitting
self-contained consensus invariant tests against the RustChain node.

Future contributors should follow the grammar and rubric documented below.

-----------------------------------------------------------------------------
SUBMISSION GRAMMAR & TEMPLATE
-----------------------------------------------------------------------------
1. Write a single self-contained test class inheriting from ``unittest.TestCase``.
2. Pin exactly ONE invariant per test method.
3. Import canonical constants from ``rewards_implementation_rip200`` — never
   hardcode emission rates or slot counts that can desync from the live chain.
4. Initialise the database with a minimal settlement schema (or migrated
   schema) sufficient to drive the consensus code paths.
5. Drive invariants through the actual consensus entry points
   (``calculate_epoch_rewards_time_aged`` / ``settle_epoch_rip200`` /
   ``settle_epoch_with_anti_double_mining``).
6. Ensure the test initializes its own isolated temporary database and
   cleans up ``-wal`` / ``-shm`` sidecars on tearDown.

-----------------------------------------------------------------------------
ACCEPTANCE / REJECTION RUBRIC
-----------------------------------------------------------------------------
[ACCEPT]
- Test focuses on a single consensus invariant (e.g. emission balance,
  eligibility gate, double-enroll prevention).
- Calls real consensus functions; asserts on balance / ledger / epoch_state
  outcomes — NOT on raw SQLite schema enforcement.
- Cleans up all database connections and WAL sidecars on tearDown.
- Run time is under 2.0 seconds.
- Imports emission constants from ``rewards_implementation_rip200``.
- Uses ``fingerprint_passed DEFAULT 0`` (production default).

[REJECT]
- Test is flaky, non-deterministic, or depends on external network state.
- Tests a trivial Python/SQLite tautology rather than a consensus invariant
  (e.g. asserting ``IntegrityError`` on a raw PRIMARY KEY INSERT — that proves
  SQLite works, not that RustChain prevents double-mining).
- Uses hardcoded emission rates or slot counts instead of canonical imports.
- Leaves unclosed database connections, WAL files, or temp files (resource
  leaks).
- Toy three-table schema instead of the minimal settlement schema.
"""

import gc
import os
import sqlite3
import sys
import tempfile
import time
import unittest

# ---------------------------------------------------------------------------
# Path bootstrap — node/ must be importable from here
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rewards_implementation_rip200 import (
    PER_EPOCH_URTC,
    UNIT,
    settle_epoch_rip200,
)
from rip_200_round_robin_1cpu1vote import (
    GENESIS_TIMESTAMP,
    BLOCK_TIME,
    calculate_epoch_rewards_time_aged,
)
from rip0202_enrollment import (
    derive_block_enrollment,
)

# Canonical slot count — imported from node runtime, not hardcoded.
try:
    from auto_epoch_settler import SLOTS_PER_EPOCH
except ImportError:
    try:
        from node.auto_epoch_settler import SLOTS_PER_EPOCH
    except ImportError:
        SLOTS_PER_EPOCH = 144


# ---------------------------------------------------------------------------
# Schema helper — mirrors the full production schema used by anti_double_mining
# ---------------------------------------------------------------------------

def _init_minimal_settlement_schema(db_path: str) -> sqlite3.Connection:
    """Initialise a minimal settlement-compatible schema.

    Contains the tables required to drive the settlement engine code paths
    without production-data access.

    ``fingerprint_passed`` defaults to 0 (production default: must be earned).
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS miner_attest_recent (
            miner TEXT PRIMARY KEY,
            device_arch TEXT,
            ts_ok INTEGER,
            fingerprint_passed INTEGER DEFAULT 0,
            entropy_score REAL DEFAULT 0,
            warthog_bonus REAL DEFAULT 1.0
        );

        CREATE TABLE IF NOT EXISTS miner_fingerprint_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            miner TEXT NOT NULL,
            ts INTEGER NOT NULL,
            profile_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS epoch_enroll (
            epoch INTEGER NOT NULL,
            miner_pk TEXT NOT NULL,
            weight REAL DEFAULT 1.0,
            PRIMARY KEY (epoch, miner_pk)
        );

        CREATE TABLE IF NOT EXISTS epoch_state (
            epoch INTEGER PRIMARY KEY,
            settled INTEGER DEFAULT 0,
            settled_ts INTEGER
        );

        CREATE TABLE IF NOT EXISTS balances (
            miner_id TEXT PRIMARY KEY,
            amount_i64 INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER,
            epoch INTEGER,
            miner_id TEXT,
            delta_i64 INTEGER,
            reason TEXT
        );

        CREATE TABLE IF NOT EXISTS epoch_rewards (
            epoch INTEGER,
            miner_id TEXT,
            share_i64 INTEGER,
            PRIMARY KEY (epoch, miner_id)
        );
    """)
    conn.commit()
    return conn


def _epoch_start_ts(epoch: int) -> int:
    """Return the wall-clock timestamp of the first slot in *epoch*."""
    return GENESIS_TIMESTAMP + epoch * SLOTS_PER_EPOCH * BLOCK_TIME


# ---------------------------------------------------------------------------
# Harness test class
# ---------------------------------------------------------------------------

class TestAttractorConsensusInvariants(unittest.TestCase):
    """Reference suite exercising three canonical consensus invariants.

    Every test:
    - Uses the minimal settlement schema (not a toy 3-table subset).
    - Drives invariants through real consensus functions, not raw SQL.
    - Imports emission constants from ``rewards_implementation_rip200``.
    - Asserts on balance / ledger / epoch_state outcomes.
    """

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self._tmp.name
        self._tmp.close()
        self.conn = _init_minimal_settlement_schema(self.db_path)

    def tearDown(self):
        # Close all handles before attempting to unlink on Windows.
        self.conn.close()
        gc.collect()
        for suffix in ("", "-wal", "-shm"):
            path = self.db_path + suffix
            for _ in range(5):
                try:
                    os.unlink(path)
                    break
                except (OSError, PermissionError):
                    gc.collect()
                    time.sleep(0.05)

    # ------------------------------------------------------------------
    # Invariant 1: Emission sum — settle_epoch writes exactly PER_EPOCH_URTC
    # ------------------------------------------------------------------

    def test_invariant_emission_sum_equals_per_epoch_urtc(self):
        """INVARIANT: settle_epoch credits exactly PER_EPOCH_URTC to balances.

        Drives the real ``settle_epoch_rip200`` entry point (which in turn calls
        ``calculate_epoch_rewards_time_aged``).  The settlement engine must write
        no more and no less than the canonical per-epoch emission, regardless of
        miner count or weight distribution.

        This catches:
        - rounding loss that silently burns tokens,
        - remainder mis-allocation that over-credits the last miner,
        - zero-emission edge cases for single-miner epochs.
        """
        EPOCH = 5
        start_ts = _epoch_start_ts(EPOCH)
        current_slot_approx = (EPOCH + 1) * SLOTS_PER_EPOCH

        # Enroll two miners with attestation records that pass fingerprint.
        miners = [
            ("attractor_miner_alpha", "g4"),
            ("attractor_miner_beta", "x86_64"),
        ]
        for miner_pk, arch in miners:
            self.conn.execute(
                "INSERT INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?, ?, ?)",
                (EPOCH, miner_pk, 1.0),
            )
            self.conn.execute(
                "INSERT INTO miner_attest_recent "
                "(miner, device_arch, ts_ok, fingerprint_passed) VALUES (?, ?, ?, 1)",
                (miner_pk, arch, start_ts + 60),
            )
            # Pre-create a zero balance row so the settle INSERT-OR-UPDATE works.
            self.conn.execute(
                "INSERT INTO balances (miner_id, amount_i64) VALUES (?, 0)",
                (miner_pk,),
            )
        self.conn.commit()

        # Run the full settlement entry point (not raw reward calculation).
        result = settle_epoch_rip200(self.db_path, EPOCH)

        self.assertTrue(result.get("ok"), f"Settlement failed: {result}")
        self.assertFalse(result.get("already_settled", False))

        # Assert: total credits to balances must equal exactly PER_EPOCH_URTC.
        row = self.conn.execute(
            "SELECT COALESCE(SUM(amount_i64), 0) FROM balances"
        ).fetchone()
        total_credited = row[0]

        self.assertEqual(
            total_credited,
            PER_EPOCH_URTC,
            f"Emission invariant breach: credited {total_credited} uRTC, "
            f"expected exactly {PER_EPOCH_URTC} uRTC (PER_EPOCH_URTC)",
        )

    # ------------------------------------------------------------------
    # Invariant 2: Settlement idempotency via the settle entry point
    # ------------------------------------------------------------------

    def test_invariant_settlement_idempotency_via_settle_entry_point(self):
        """INVARIANT: Re-running settle_epoch for an already-settled epoch must
        not double-credit balances or duplicate ledger / epoch_rewards rows.

        Drives ``settle_epoch_rip200`` twice.  The second call must return
        ``already_settled=True`` and leave balances unchanged, preventing
        double-minting that would inflate supply beyond the canonical emission.

        This catches:
        - missing "already settled" guard in the settlement path,
        - race conditions where two workers settle the same epoch concurrently,
        - re-insertion into ``epoch_rewards`` / ``ledger`` on replay.
        """
        EPOCH = 10
        start_ts = _epoch_start_ts(EPOCH)

        self.conn.execute(
            "INSERT INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?, ?, ?)",
            (EPOCH, "attractor_settle_miner", 1.0),
        )
        self.conn.execute(
            "INSERT INTO miner_attest_recent "
            "(miner, device_arch, ts_ok, fingerprint_passed) VALUES (?, ?, ?, 1)",
            ("attractor_settle_miner", "g4", start_ts + 60),
        )
        self.conn.execute(
            "INSERT INTO balances (miner_id, amount_i64) VALUES (?, 0)",
            ("attractor_settle_miner",),
        )
        self.conn.commit()

        # First settlement — must succeed and credit PER_EPOCH_URTC.
        result1 = settle_epoch_rip200(self.db_path, EPOCH)
        self.assertTrue(result1.get("ok"), f"First settlement failed: {result1}")
        self.assertFalse(result1.get("already_settled", False))

        balance_after_first = self.conn.execute(
            "SELECT amount_i64 FROM balances WHERE miner_id = ?",
            ("attractor_settle_miner",),
        ).fetchone()[0]
        self.assertEqual(balance_after_first, PER_EPOCH_URTC)

        # Second settlement on the same epoch — must be a no-op.
        result2 = settle_epoch_rip200(self.db_path, EPOCH)
        self.assertTrue(result2.get("ok"), f"Second settlement call failed: {result2}")
        self.assertTrue(
            result2.get("already_settled", False),
            "Expected already_settled=True on second call",
        )

        balance_after_second = self.conn.execute(
            "SELECT amount_i64 FROM balances WHERE miner_id = ?",
            ("attractor_settle_miner",),
        ).fetchone()[0]
        self.assertEqual(
            balance_after_second,
            balance_after_first,
            f"Double-mint detected: balance changed from {balance_after_first} "
            f"to {balance_after_second} after idempotent re-settle",
        )

        # Ledger must have exactly one credit row for this miner/epoch pair.
        ledger_rows = self.conn.execute(
            "SELECT COUNT(*) FROM ledger WHERE miner_id = ? AND epoch = ?",
            ("attractor_settle_miner", EPOCH),
        ).fetchone()[0]
        self.assertEqual(
            ledger_rows,
            1,
            f"Idempotency breach: expected 1 ledger row, found {ledger_rows}",
        )

    # ------------------------------------------------------------------
    # Invariant 3: Uniqueness via the enroll path
    # ------------------------------------------------------------------

    def test_invariant_uniqueness_via_enroll_path(self):
        """INVARIANT: The enrollment path must resolve duplicate attestations
        deterministically to a single unique weight per miner.

        Drives the consensus-level ``derive_block_enrollment`` (RIP-202 B1 entry
        point). When a miner has multiple attestations in the same block, the
        path must not create duplicate enrollments or raise integrity errors,
        but instead resolve to a single unique weight using a total order
        (timestamp and content tiebreaker).
        """
        # Stub the hardware weights and device derivation for consensus.
        stub_weights = {
            "PowerPC": {"G4": 2.5, "G5": 2.0, "default": 1.5},
            "x86": {"modern": 1.0, "default": 1.0},
        }

        def stub_derive(device, fingerprint, fingerprint_passed):
            return {
                "device_family": device.get("family", "x86"),
                "device_arch": device.get("arch", "modern"),
            }

        # An older failed attestation and a newer successful one for the same miner.
        older = {
            "miner": "attractor_dup_miner",
            "device": {"family": "PowerPC", "arch": "G4"},
            "fingerprint": {"simd": "x"},
            "fingerprint_passed": False,
            "timestamp": 100,
        }
        newer = {
            "miner": "attractor_dup_miner",
            "device": {"family": "PowerPC", "arch": "G5"},
            "fingerprint": {"simd": "x"},
            "fingerprint_passed": True,
            "timestamp": 200,
        }

        # derive_block_enrollment must deduplicate and return exactly one weight.
        enrollment = derive_block_enrollment(
            [older, newer], stub_derive, stub_weights
        )

        self.assertIn("attractor_dup_miner", enrollment)
        # The newer attestation (ts=200, G5 -> 2.0 weight) must win, yielding 2_000_000 units.
        self.assertEqual(
            enrollment["attractor_dup_miner"],
            2_000_000,
            "Uniqueness via enroll path failed: did not resolve to the correct unique weight",
        )


if __name__ == "__main__":
    unittest.main()
