#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Attestation identity: phased enforcement and first-signer-hijack protection.

Ported from the live production node, which carried a complete three-phase
signed-attestation rollout that never reached main. Main meanwhile pinned
whatever public key a client presented:

    signing_pubkey=pubkey_hex or None

That is a capture vector. `signing_pubkey` is the authority `/epoch/enroll`
verifies against, so whoever signed first for a symbolic identity such as
`dual-g4-125` became its owner, and the real operator was locked out. The
production code decides which keys are safe to pin, and this file pins that
decision so a later change cannot quietly restore trust-on-first-use for
identities that cannot prove ownership.

The phases exist so the vintage fleet is not cut off mid-upgrade, which is the
same rollout mistake that made the unsigned-attestation PR unmergeable:

    log_only     (default) verify if present, enforce nothing
    enforce_new            new identities must sign, grandfathered stay unsigned
    enforce_all            everyone signs
"""

import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = os.path.join(ROOT, "node")
sys.path.insert(0, NODE)
os.environ.setdefault("RC_ADMIN_KEY", "t" * 64)

_spec = importlib.util.spec_from_file_location(
    "rc_node_id", os.path.join(NODE, "rustchain_v2_integrated_v2.2.1_rip200.py")
)
MOD = importlib.util.module_from_spec(_spec)
sys.modules["rc_node_id"] = MOD
_spec.loader.exec_module(MOD)


class EnforceModeTest(unittest.TestCase):

    def setUp(self):
        os.environ.pop("RTC_ATTEST_ENFORCE_MODE", None)

    tearDown = setUp

    def test_default_is_log_only_so_a_deploy_changes_nothing(self):
        """The whole point of the phasing: shipping this must be a no-op."""
        self.assertEqual(MOD._attest_enforce_mode(), "log_only")

    def test_each_phase_is_selectable_by_env(self):
        for mode in ("log_only", "enforce_new", "enforce_all"):
            os.environ["RTC_ATTEST_ENFORCE_MODE"] = mode
            self.assertEqual(MOD._attest_enforce_mode(), mode)

    def test_an_unknown_mode_falls_back_to_log_only(self):
        """A typo in an env var must not silently start rejecting the fleet."""
        for junk in ("enforce", "ENFORCE_ALL_PLEASE", "1", ""):
            os.environ["RTC_ATTEST_ENFORCE_MODE"] = junk
            self.assertEqual(MOD._attest_enforce_mode(), "log_only")


class SelfCertifyingAddressTest(unittest.TestCase):
    """Only an address derived from a key may be pinned on first sight."""

    def test_canonical_rtc_hex_address_is_self_certifying(self):
        self.assertTrue(MOD._is_rtc_hex_address("RTC" + "a1b2c3d4" * 5))

    def test_symbolic_legacy_names_are_not(self):
        """These are the identities a first signer could otherwise capture."""
        for name in ("dual-g4-125", "power8-s824-sophia", "victus-x86-scott",
                     "cobalt-qube3-scott", "g5-selena-179"):
            self.assertFalse(MOD._is_rtc_hex_address(name), name)

    def test_uppercase_hex_is_rejected(self):
        """Node-derived addresses are lowercase; accepting both would let one
        machine hold two spellings of the same identity."""
        self.assertFalse(MOD._is_rtc_hex_address("RTC" + "A1B2C3D4" * 5))

    def test_wrong_length_and_junk_rejected(self):
        for bad in ("RTC", "RTC" + "a" * 39, "RTC" + "a" * 41,
                    "rtc" + "a" * 40, "", None, 12345, b"RTC" + b"a" * 40):
            self.assertFalse(MOD._is_rtc_hex_address(bad), repr(bad))


class UnsignedAllowlistTest(unittest.TestCase):

    def setUp(self):
        os.environ.pop("RTC_UNSIGNED_ATTEST_ALLOWLIST", None)

    tearDown = setUp

    def test_empty_by_default(self):
        self.assertEqual(MOD._attest_unsigned_allowlist(), set())

    def test_parses_and_strips_a_comma_list(self):
        os.environ["RTC_UNSIGNED_ATTEST_ALLOWLIST"] = " dual-g4-125 , g5-selena-179 ,"
        self.assertEqual(MOD._attest_unsigned_allowlist(),
                         {"dual-g4-125", "g5-selena-179"})

    def test_matching_is_case_sensitive(self):
        """Miner ids are case-sensitive on the node; folding case here would
        conflate two distinct identities into one allowlist entry."""
        os.environ["RTC_UNSIGNED_ATTEST_ALLOWLIST"] = "dual-g4-125"
        allow = MOD._attest_unsigned_allowlist()
        self.assertIn("dual-g4-125", allow)
        self.assertNotIn("DUAL-G4-125", allow)


class PinDecisionIsWiredTest(unittest.TestCase):
    """The decision must reach the database, not sit in a local variable."""

    SRC = os.path.join(NODE, "rustchain_v2_integrated_v2.2.1_rip200.py")

    def test_the_pinned_key_is_the_decided_key_not_the_supplied_one(self):
        src = open(self.SRC).read()
        self.assertIn("signing_pubkey=pin_pubkey", src)
        self.assertNotIn(
            "signing_pubkey=pubkey_hex or None", src,
            "main pinned whatever the client sent, which is the capture vector",
        )

    def test_the_hijack_protection_branches_are_present(self):
        """Each branch is a distinct way to refuse a pin; losing any one of
        them reopens capture for that class of identity."""
        src = open(self.SRC).read()
        for marker in ("is_pin_frozen", "derives_to_addr",
                       "is_grandfathered", "pin_pubkey = None"):
            self.assertIn(marker, src, marker)

    def test_admin_rotation_path_exists(self):
        """Without it, an honest owner who loses a key is locked out for good,
        which is what makes strict pinning safe to turn on at all."""
        src = open(self.SRC).read()
        self.assertIn("/admin/attest/key", src)
        self.assertIn("def admin_attest_key", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
