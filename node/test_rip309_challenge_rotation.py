#!/usr/bin/env python3
"""Targeted tests for RIP-309 Phase 4 challenge rotation."""

import hashlib
import unittest

from rip_309_measurement_rotation import (
    CHALLENGE_TYPES,
    derive_epoch_nonce,
    get_epoch_challenge_plan,
    get_epoch_measurement_config,
)


class Rip309ChallengeRotationTests(unittest.TestCase):
    def test_nonce_is_deterministic_for_same_prev_hash(self):
        prev_hash = hashlib.sha256(b"same-block").hexdigest()
        self.assertEqual(derive_epoch_nonce(prev_hash), derive_epoch_nonce(prev_hash))

    def test_challenge_plan_is_deterministic_with_same_epoch_and_hash(self):
        prev_hash = hashlib.sha256(b"epoch-10").hexdigest()
        plan_a = get_epoch_challenge_plan(prev_hash, 10)
        plan_b = get_epoch_challenge_plan(prev_hash, 10)
        self.assertEqual(plan_a, plan_b)

    def test_challenge_plan_varies_across_epochs(self):
        prev_hash_a = hashlib.sha256(b"epoch-10").hexdigest()
        prev_hash_b = hashlib.sha256(b"epoch-11").hexdigest()
        plan_a = get_epoch_challenge_plan(prev_hash_a, 10)
        plan_b = get_epoch_challenge_plan(prev_hash_b, 11)
        self.assertNotEqual(plan_a["nonce"], plan_b["nonce"])
        self.assertNotEqual(plan_a["active_challenges"], plan_b["active_challenges"])

    def test_all_three_challenge_types_are_present_each_epoch(self):
        prev_hash = hashlib.sha256(b"epoch-21").hexdigest()
        plan = get_epoch_challenge_plan(prev_hash, 21)
        observed = {entry["challenge_type"] for entry in plan["active_challenges"]}
        self.assertEqual(observed, set(CHALLENGE_TYPES))

    def test_measurement_config_embeds_challenge_rotation(self):
        prev_hash = hashlib.sha256(b"epoch-99").hexdigest()
        config = get_epoch_measurement_config(prev_hash, 99)
        self.assertIn("challenge_rotation", config)
        self.assertEqual(config["challenge_rotation"]["epoch"], 99)
        self.assertEqual(len(config["challenge_rotation"]["active_challenges"]), 3)

    def test_each_challenge_has_stable_required_fields(self):
        prev_hash = hashlib.sha256(b"epoch-55").hexdigest()
        plan = get_epoch_challenge_plan(prev_hash, 55)
        for challenge in plan["active_challenges"]:
            self.assertIn("challenge_type", challenge)
            self.assertIn("layer", challenge)
            self.assertIn("seed", challenge)
            self.assertIn("interval_slots", challenge)
            self.assertIn("offset_slots", challenge)
            self.assertIn("timeout_seconds", challenge)
            self.assertIn("parameters", challenge)
            self.assertGreater(challenge["interval_slots"], 0)
            self.assertGreaterEqual(challenge["offset_slots"], 0)
            self.assertGreater(challenge["timeout_seconds"], 0)
            self.assertIsInstance(challenge["parameters"], dict)


if __name__ == "__main__":
    unittest.main()
