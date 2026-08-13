#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""RIP-309c: bind the measurement to the challenge, not just the envelope.

The attestation envelope is already fresh. `/attest/submit` requires a live
server-issued challenge from `/attest/challenge`, single-use, 300s expiry,
optionally bound to a miner_id. That is real replay protection — for the
submission.

It says nothing about when the numbers inside were measured. A client can wrap
values measured once, long ago, in a nonce fetched a second ago. The reference
client does exactly that: `miners/linux/rustchain_linux_miner.py` measures at
startup and the re-measure before each attestation is guarded by
`not self.fingerprint_data`, so it never re-runs. Honest clients replay their
own measurements for the life of the process, and a forger needs to measure
nothing at all, ever.

Binding derives the size of the timing workload from the challenge. The client
already holds the nonce before it measures, so nothing about the protocol order
has to change. A binding built for a different nonce carries the wrong
iteration count, which the server catches by recomputation alone, with no
hardware model required.

Phase 0 is observation only. `absent` must stay a normal, non-failing state, or
this repeats the hard cutover that made the unsigned-attestation change
unmergeable.
"""

import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = os.path.join(ROOT, "node")
sys.path.insert(0, NODE)

_spec = importlib.util.spec_from_file_location(
    "rc_node_fb", os.path.join(NODE, "rustchain_v2_integrated_v2.2.1_rip200.py")
)
MOD = importlib.util.module_from_spec(_spec)
sys.modules["rc_node_fb"] = MOD
_spec.loader.exec_module(MOD)

workload = MOD.derive_measurement_workload
verify = MOD.verify_measurement_binding

NONCE_A = "a1b2c3d4" + "0" * 56
NONCE_B = "ffee0011" + "0" * 56


def _binding(nonce, iterations=None, duration_ns=None, rate_ns=50_000):
    iters = workload(nonce) if iterations is None else iterations
    return {
        "nonce": nonce,
        "iterations": iters,
        "duration_ns": duration_ns if duration_ns is not None else iters * rate_ns,
    }


class WorkloadDerivationTest(unittest.TestCase):

    def test_deterministic_for_a_given_nonce(self):
        self.assertEqual(workload(NONCE_A), workload(NONCE_A))

    def test_different_nonces_give_different_workloads(self):
        self.assertNotEqual(workload(NONCE_A), workload(NONCE_B))

    def test_stays_in_a_bounded_range(self):
        lo = MOD.MEASUREMENT_WORKLOAD_MIN
        hi = lo + MOD.MEASUREMENT_WORKLOAD_SPAN
        for n in (NONCE_A, NONCE_B, "0" * 64, "f" * 64, "", "zz", None):
            self.assertGreaterEqual(workload(n), lo)
            self.assertLess(workload(n), hi)

    def test_non_hex_nonce_does_not_crash(self):
        self.assertIsInstance(workload("zzzz----"), int)


class BindingVerificationTest(unittest.TestCase):

    def test_a_correct_binding_is_accepted(self):
        v = verify(NONCE_A, _binding(NONCE_A))
        self.assertTrue(v["ok"])
        self.assertEqual(v["state"], "bound")

    def test_a_binding_built_for_another_nonce_is_stale(self):
        """The core of the mechanism: replay carries the wrong workload."""
        replayed = _binding(NONCE_B)          # measured for a previous round
        replayed["nonce"] = NONCE_A           # re-wrapped in a fresh challenge
        v = verify(NONCE_A, replayed)
        self.assertFalse(v["ok"])
        self.assertEqual(v["state"], "stale")
        self.assertIn("workload_mismatch", v["reason"])

    def test_a_lied_about_nonce_is_caught_before_the_workload_check(self):
        v = verify(NONCE_A, _binding(NONCE_B))
        self.assertFalse(v["ok"])
        self.assertEqual(v["state"], "mismatch")

    def test_absent_binding_is_not_a_failure_state(self):
        """Rollout safety: unbound clients must remain ordinary, not rejected."""
        v = verify(NONCE_A, None)
        self.assertEqual(v["state"], "absent")
        self.assertFalse(v["ok"])

    def test_malformed_bindings_never_raise(self):
        for junk in ("string", 42, [], {"iterations": "many"},
                     {"iterations": None}, {"nonce": NONCE_A}):
            v = verify(NONCE_A, junk)
            self.assertIn("state", v)
            self.assertFalse(v["ok"])

    def test_non_positive_duration_rejected(self):
        for bad in (0, -1):
            v = verify(NONCE_A, _binding(NONCE_A, duration_ns=bad))
            self.assertFalse(v["ok"])
            self.assertEqual(v["state"], "malformed")

    def test_rate_within_tolerance_of_own_history_is_accepted(self):
        v = verify(NONCE_A, _binding(NONCE_A, rate_ns=50_000), expected_rate_ns=55_000)
        self.assertTrue(v["ok"], v)

    def test_rate_wildly_faster_than_claimed_hardware_is_flagged(self):
        """An emulator answering at modern speed while claiming vintage silicon."""
        v = verify(NONCE_A, _binding(NONCE_A, rate_ns=10), expected_rate_ns=50_000)
        self.assertFalse(v["ok"])
        self.assertEqual(v["state"], "rate_implausible")

    def test_rate_check_is_skipped_when_no_history_is_known(self):
        v = verify(NONCE_A, _binding(NONCE_A, rate_ns=10), expected_rate_ns=None)
        self.assertTrue(v["ok"], "cold start must not fail on an unknown rate")


class PhaseZeroIsObserveOnlyTest(unittest.TestCase):
    """Phase 0 must not gate rewards. Adoption first, enforcement later."""

    SRC = os.path.join(NODE, "rustchain_v2_integrated_v2.2.1_rip200.py")

    def test_binding_verdict_does_not_touch_weight_yet(self):
        import ast
        src = open(self.SRC).read()
        tree = ast.parse(src)
        calls = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == "verify_measurement_binding"
        ]
        self.assertEqual(len(calls), 1, "expected exactly one phase-0 call site")
        self.assertNotIn("measurement_binding_verdict) *", src)
        self.assertNotIn("hw_weight * measurement_binding", src)

    def test_the_next_workload_is_advertised_to_clients(self):
        """A client must be able to adopt binding without a coordinated release."""
        src = open(self.SRC).read()
        self.assertIn("measurement_workload_next", src)
        self.assertIn("measurement_binding_state", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
