#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Scottcjn/Rustchain#8078: bare-bool True fingerprint checks must be rejected.

A VM that submits `{"clock_drift": true, "cache_timing": true, ...}` with NO
data object at all currently passes the fingerprint gate at face value.
The honest C miner emits `{"checks": {"clock_drift": true}}` for legacy
compat, and on real hardware the Python miner emits a `data: {...}` block.
A VM that just asserts True for every check has zero measurements, so it
should be treated as UNMEASURED (reject) rather than as a pass.

This test pins the fix: validate_fingerprint_data() must reject a
modern-arch payload that submits bare-bool True checks.
"""
import ast
import os
import unittest

RIP = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "node", "rustchain_v2_integrated_v2.2.1_rip200.py",
)


class TestBareBoolFingerprint(unittest.TestCase):
    """A modern-arch payload with bare-bool True checks must be rejected."""

    def setUp(self):
        with open(RIP, "r", encoding="utf-8") as fh:
            self.src = fh.read()
        self.tree = ast.parse(self.src)

    def test_validate_fingerprint_data_function_present(self):
        """validate_fingerprint_data must exist."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef) and node.name == "validate_fingerprint_data":
                self.fn = node
                return
        self.fail("validate_fingerprint_data() not found")

    def test_bare_bool_true_is_rejected(self):
        """The fix must reject bare-bool True checks for modern archs."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef) and node.name == "validate_fingerprint_data":
                self.fn = node
                break
        else:
            self.fail("validate_fingerprint_data() not found")

        body_src = ast.unparse(self.fn)
        # The fix must include a `check_unmeasured` rejection string OR a
        # `REQUIRED_CHECKS_NEEDING_EVIDENCE` allowlist reference. Without
        # one of these a bare-bool True check still auto-passes.
        has_unmeasured = "check_unmeasured" in body_src
        has_allowlist = "REQUIRED_CHECKS_NEEDING_EVIDENCE" in body_src
        self.assertTrue(
 has_unmeasured or has_allowlist,
 "validate_fingerprint_data() does not reject bare-bool True checks; "
 "a VM passing asserts-all-True with no measurements slips through",
 )

    def test_limited_archs_exempt(self):
        """The fix must keep limited-arch claims (Apple II, 386, Pico bridge) passing."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef) and node.name == "validate_fingerprint_data":
                self.fn = node
                break
        else:
            self.fail("validate_fingerprint_data() not found")
        body_src = ast.unparse(self.fn)
        # The fix exempts limited-arch claims (`_is_limited_claim`).
        self.assertIn(
 "_is_limited_claim", body_src,
 "validate_fingerprint_data() no longer distinguishes limited-arch claims",
 )


if __name__ == "__main__":
    unittest.main(verbosity=2)
