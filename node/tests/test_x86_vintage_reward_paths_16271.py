# SPDX-License-Identifier: MIT
"""Bounty #16271 — complete vintage-x86 anti-spoof hardening of the reward paths.

PR #8022 clamped the enroll-weight tier inside the attestation handler
(``_derive_enroll_weight_device``). This suite closes the two consumers that
still paid the vintage multiplier from the *self-reported* stored label with no
corroboration in the deciding call:

1. ``resolve_enroll_weight_device`` (POST /epoch/enroll) read
   ``miner_attest_recent.device_family/device_arch`` — the general classifier
   identity — straight into ``HARDWARE_WEIGHTS``. A miner that attested once
   with an unvalidated ``x86/486`` identity could enroll every later epoch
   (attestation TTL is 24h and enrollment does not require a fresh attest) at
   the 2.0x tier while its hardware contradicts it.
2. The settlement antiquity fallbacks in
   ``rip_200_round_robin_1cpu1vote.calculate_epoch_rewards_time_aged`` and
   ``anti_double_mining._calculate_anti_double_mining_rewards_conn`` keyed
   ``ANTIQUITY_MULTIPLIERS`` (486 = 2.9, 386 = 3.0) off the same unvouched
   stored label whenever the epoch had no ``epoch_enroll`` snapshot.

Bounty requirements covered here:
- spoofed vintage + no corroboration -> clamp (both paths);
- honest TSC-less 486 keeps its tier: the corroborated verdict is snapshotted
  into ``epoch_enroll`` at attestation and settlement honors that snapshot
  untouched (no clock-drift gate anywhere in these paths);
- flags-only / bare-brand / no-evidence payloads -> clamp (the enroll path has
  no measurement oracle at all, so every stored x86-vintage label clamps;
  measurement-shape corroboration is already covered by the #8022 suite);
- no blast radius: non-x86 tiers (g4/ARM/console) and stored identity rows are
  never rewritten — only the reward lookup for this epoch changes;
- down-only: clamping maps to the neutral rate, never upward.
"""

import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest

from _node_test_utils import release_node_modules

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")
if NODE_DIR not in sys.path:
    sys.path.insert(0, NODE_DIR)

from rip_200_round_robin_1cpu1vote import (
    BLOCK_TIME,
    GENESIS_TIMESTAMP,
    _weight_to_units,
    calculate_epoch_rewards_time_aged,
    sanitize_unvouched_x86_vintage_arch,
)

EPOCH = 10
SLOTS_PER_EPOCH = 144
POT = 1_500_000


def _epoch_window(epoch):
    start = GENESIS_TIMESTAMP + epoch * SLOTS_PER_EPOCH * BLOCK_TIME
    end = GENESIS_TIMESTAMP + ((epoch + 1) * SLOTS_PER_EPOCH - 1) * BLOCK_TIME
    return start, end


class ResolveEnrollWeightDeviceTest(unittest.TestCase):
    """POST /epoch/enroll must not pay vintage tiers off an unvouched label."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        # Capture/restore (mirrors test_enroll_weight_device_spoof): leaving a
        # RUSTCHAIN_DB_PATH that points into our cleaned-up temp dir would make
        # any later node-module suite in a combined pytest session fail to open
        # its database.
        cls._prev = {k: os.environ.get(k) for k in ("RUSTCHAIN_DB_PATH", "RC_ADMIN_KEY")}
        os.environ["RUSTCHAIN_DB_PATH"] = os.path.join(cls._tmp.name, "x86-enroll.db")
        os.environ["RC_ADMIN_KEY"] = "0123456789abcdef0123456789abcdef"
        release_node_modules()
        spec = importlib.util.spec_from_file_location("rcnode_x86_enroll_test", MODULE_PATH)
        cls.mod = importlib.util.module_from_spec(spec)
        sys.modules["rcnode_x86_enroll_test"] = cls.mod
        spec.loader.exec_module(cls.mod)

    @classmethod
    def tearDownClass(cls):
        release_node_modules()
        for k, v in cls._prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        cls._tmp.cleanup()

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute(
            "CREATE TABLE miner_attest_recent (miner TEXT PRIMARY KEY, device_family TEXT, device_arch TEXT)"
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def _stored(self, family, arch, miner="m1"):
        self.conn.execute(
            "INSERT INTO miner_attest_recent (miner, device_family, device_arch) VALUES (?, ?, ?)",
            (miner, family, arch),
        )
        self.conn.commit()

    def test_stored_spoofed_vintage_x86_clamps_to_neutral(self):
        for arch in ("486", "386", "pentium", "pentium_mmx", "pentium_iii"):
            with self.subTest(arch=arch):
                self._stored("x86", arch)
                self.assertEqual(
                    self.mod.resolve_enroll_weight_device(self.conn, "m1", {}),
                    ("x86", "default"),
                )
                self.conn.execute("DELETE FROM miner_attest_recent")
                self.conn.commit()

    def test_stored_vintage_claim_is_not_rescued_by_unsigned_body_fingerprint(self):
        # An attacker can ship a full fingerprint dict AND claim the payload was
        # canonically verified: enrollment signatures cover only
        # (miner_pubkey|miner_id|epoch), so nothing in this call corroborates it.
        self._stored("x86", "486")
        body = {
            "fingerprint": {"checks": {"device_age_oracle": {"passed": True, "data": {"cpu_model": "Am486DX4"}}}},
            "canonical_payload_verified": True,
        }
        self.assertEqual(
            self.mod.resolve_enroll_weight_device(self.conn, "m1", body),
            ("x86", "default"),
        )

    def test_body_fallback_vintage_claim_clamps_without_verified_device(self):
        # Legacy row present but with no stored verified device (NULL family):
        # the body fallback still must not hand out a vintage tier.
        self.conn.execute("INSERT INTO miner_attest_recent (miner, device_family, device_arch) VALUES ('m1', NULL, NULL)")
        self.conn.commit()
        body = {"device": {"family": "x86_64", "arch": "pentium"}}
        self.assertEqual(
            self.mod.resolve_enroll_weight_device(self.conn, "m1", body),
            ("x86", "default"),
        )

    def test_no_row_no_evidence_clamps_body_vintage(self):
        body = {"device": {"family": "x86", "arch": "486"}}
        self.assertEqual(
            self.mod.resolve_enroll_weight_device(self.conn, "unknown_miner", body),
            ("x86", "default"),
        )

    def test_non_x86_vintage_tiers_keep_their_stored_weight(self):
        # Blast radius: honest vintage ARM/PowerPC/console identities are not
        # x86 and must resolve exactly as stored (their detectors already vouch
        # for them at attestation).
        for family, arch in (("PowerPC", "g4"), ("ARM", "arm2"), ("console", "nes_6502")):
            with self.subTest(family=family):
                self._stored(family, arch)
                self.assertEqual(
                    self.mod.resolve_enroll_weight_device(self.conn, "m1", {}),
                    (family, arch),
                )
                self.conn.execute("DELETE FROM miner_attest_recent")
                self.conn.commit()

    def test_modern_x86_identity_passes_through_unchanged(self):
        self._stored("x86", "modern")
        self.assertEqual(
            self.mod.resolve_enroll_weight_device(self.conn, "m1", {}),
            ("x86", "modern"),
        )

    def test_clamp_does_not_rewrite_stored_identity(self):
        # Requirement 4: the API/inventory view of the device stays intact.
        self._stored("x86", "486")
        self.mod.resolve_enroll_weight_device(self.conn, "m1", {})
        row = self.conn.execute(
            "SELECT device_family, device_arch FROM miner_attest_recent WHERE miner='m1'"
        ).fetchone()
        self.assertEqual(row, ("x86", "486"))

    def test_clamped_weight_is_neutral_not_inflated(self):
        # The clamp target is the same x86/default rate the merged #8022 clamp
        # pays on the attestation path: at the neutral 1.0 ceiling, strictly
        # below every vintage tier it replaces, never inflated upward.
        weights = self.mod.HARDWARE_WEIGHTS["x86"]
        self.assertEqual(weights["default"], 1.0)
        for arch in sorted(self.mod._X86_VINTAGE_REWARD_ARCHES):
            with self.subTest(arch=arch):
                self.assertLess(weights["default"], weights[arch])


class _SettlementFixture(unittest.TestCase):
    """Shared minimal schema for calculate_epoch_rewards_time_aged (mirrors
    test_settlement_integrity._setup_db). DB files are unique per test inside a
    class-level temp dir: Windows holds a lingering handle after sqlite close,
    so per-test unlink flakily fails (same reason as the #8022 suite's
    ignore_cleanup_errors TemporaryDirectory)."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)

    def setUp(self):
        self.db_path = os.path.join(
            self._tmp.name, f"{type(self).__name__}.{self.id().rsplit('.', 1)[-1]}.db"
        )
        self.conn = sqlite3.connect(self.db_path)
        self.conn.executescript(
            """
            CREATE TABLE epoch_enroll (epoch INTEGER, miner_pk TEXT, weight REAL, PRIMARY KEY (epoch, miner_pk));
            CREATE TABLE miner_attest_recent (miner TEXT PRIMARY KEY, device_arch TEXT, fingerprint_passed INTEGER DEFAULT 1, entropy_score REAL DEFAULT 0, ts_ok INTEGER);
            CREATE TABLE miner_fingerprint_history (miner TEXT, ts INTEGER, profile_json TEXT);
            CREATE TABLE epoch_state (epoch INTEGER PRIMARY KEY, settled INTEGER DEFAULT 0, settled_ts INTEGER);
            """
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def attest(self, miner, device_arch):
        start, end = _epoch_window(EPOCH)
        self.conn.execute(
            "INSERT INTO miner_attest_recent (miner, device_arch, fingerprint_passed, entropy_score, ts_ok)"
            " VALUES (?, ?, 1, 0.5, ?)",
            (miner, device_arch, (start + end) // 2),
        )
        self.conn.commit()

    def enroll(self, miner, weight_units):
        self.conn.execute(
            "INSERT INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?, ?, ?)",
            (EPOCH, miner, weight_units),
        )
        self.conn.commit()

    def settle(self):
        return calculate_epoch_rewards_time_aged(
            self.db_path, EPOCH, POT, EPOCH * SLOTS_PER_EPOCH + 72, b"ab" * 32
        )


class SettlementFallbackClampTest(_SettlementFixture):
    def test_unenrolled_spoofed_486_settles_like_modern(self):
        # No epoch_enroll rows at all -> antiquity fallback fires.
        self.attest("spoof", "486")
        self.attest("honest", "modern")
        rewards = self.settle()
        self.assertEqual(rewards["spoof"], rewards["honest"])

    def test_unenrolled_spoofed_386_and_pentium_settle_like_modern(self):
        for arch in ("386", "pentium", "pentium_mmx", "pentium_pro"):
            with self.subTest(arch=arch):
                self.conn.execute("DELETE FROM miner_attest_recent")
                self.conn.commit()
                self.attest("spoof", arch)
                self.attest("honest", "modern")
                rewards = self.settle()
                self.assertEqual(rewards["spoof"], rewards["honest"])

    def test_honest_enrolled_vintage_snapshot_is_honored(self):
        # The corroborated tier reaches settlement via the epoch_enroll snapshot
        # written by the attestation auto-enroll; the fallback clamp must not
        # touch it (no honest reward cliff). Legacy REAL weights are raw floats
        # and get scaled once by _weight_to_units.
        self.attest("vintage", "486")
        self.enroll("vintage", 2.0)
        self.attest("honest", "modern")
        self.enroll("honest", 0.8)
        rewards = self.settle()
        expected = POT * 2_000_000_000 // (2_000_000_000 + _weight_to_units(0.8))
        # The distributor hands out the indivisible uRTC remainder by largest-
        # remainder order, so allow the one-unit rounding spread.
        self.assertLessEqual(abs(rewards["vintage"] - expected), 1)
        self.assertGreater(rewards["vintage"], rewards["honest"])

    def test_non_x86_vintage_fallback_is_untouched(self):
        # Blast radius: g4/68k/console antiquity keys keep their premium even
        # without an enrollment snapshot — only x86 labels need a vouch.
        self.attest("mac", "g4")
        self.attest("honest", "modern")
        rewards = self.settle()
        self.assertGreater(rewards["mac"], rewards["honest"])

    def test_failed_fingerprint_still_zero_in_fallback(self):
        self.attest("spoof", "486")
        self.conn.execute("UPDATE miner_attest_recent SET fingerprint_passed=0 WHERE miner='spoof'")
        self.conn.commit()
        rewards = self.settle()
        self.assertNotIn("spoof", rewards)


class SanitizeSharedHelperTest(unittest.TestCase):
    def test_x86_vintage_keys_clamp_down_only_to_modern(self):
        for arch in self.mod_arches():
            self.assertEqual(sanitize_unvouched_x86_vintage_arch(arch), "modern")

    @staticmethod
    def mod_arches():
        return (
            "386", "486", "pentium", "pentium_mmx", "pentium_pro",
            "pentium_ii", "pentium_iii", "pentium_m_banias",
            "pentium_m_dothan", "pentium_m_yonah",
        )

    def test_every_other_label_passes_through(self):
        for arch in ("modern", "default", "unknown", "x86_64", "g4", "g5",
                     "68000", "nes_6502", "arm2", "aarch64", ""):
            self.assertEqual(sanitize_unvouched_x86_vintage_arch(arch), arch)

    def test_case_insensitive_clamp(self):
        self.assertEqual(sanitize_unvouched_x86_vintage_arch("Pentium_MMX"), "modern")
        self.assertEqual(sanitize_unvouched_x86_vintage_arch(" 486 "), "modern")


class AdmSettlementFallbackClampTest(unittest.TestCase):
    """The ADM path (settle_epoch_rip200 -> anti_double_mining) is the preferred
    production settlement; its no-snapshot fallback must clamp identically."""

    def setUp(self):
        self.db_path = os.path.join(
            tempfile.gettempdir(), f"test_16271_adm_{os.getpid()}.db"
        )
        from anti_double_mining import setup_test_scenario

        setup_test_scenario(self.db_path)
        self.conn = sqlite3.connect(self.db_path)
        # Start from a clean fleet: the fixture's miners all attest as g4.
        self.conn.execute("DELETE FROM miner_attest_recent")
        self.conn.execute("DELETE FROM miner_fingerprint_history")
        self.conn.execute("DELETE FROM epoch_enroll")
        # current_slot for "now" lands the test epoch far in the past, matching
        # the existing TestAntiDoubleMiningRewards harness.
        import time as _time

        self.current_slot = max(0, int((_time.time() - GENESIS_TIMESTAMP) // BLOCK_TIME))
        self.epoch = (self.current_slot // SLOTS_PER_EPOCH) - 1
        start = GENESIS_TIMESTAMP + self.epoch * SLOTS_PER_EPOCH * BLOCK_TIME
        end = start + SLOTS_PER_EPOCH * BLOCK_TIME
        for miner, arch, seed in (("spoof-486", "486", "aa"), ("honest-modern", "modern", "bb")):
            self.conn.execute(
                "INSERT INTO miner_attest_recent (miner, device_arch, ts_ok, entropy_score, fingerprint_passed)"
                " VALUES (?, ?, ?, 0.5, 1)",
                (miner, arch, (start + end) // 2),
            )
            profile = {"checks": {"cpu_serial": {"data": {"serial": seed * 8}}}}
            self.conn.execute(
                "INSERT INTO miner_fingerprint_history (miner, ts, profile_json) VALUES (?, ?, ?)",
                (miner, (start + end) // 2, json.dumps(profile)),
            )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_adm_fallback_clamps_spoofed_486_to_modern_share(self):
        from anti_double_mining import calculate_anti_double_mining_rewards

        rewards, _ = calculate_anti_double_mining_rewards(
            self.db_path, epoch=self.epoch, total_reward_urtc=POT, current_slot=self.current_slot
        )
        self.assertEqual(set(rewards), {"spoof-486", "honest-modern"})
        self.assertEqual(rewards["spoof-486"], rewards["honest-modern"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
