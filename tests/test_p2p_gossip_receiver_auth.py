#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Scottcjn/Rustchain#8177 (Finding 1): /p2p/gossip POST must require X-P2P-Key.

The gossip POST endpoint is the WRITE side of the CRDT merge path; without
an auth gate, any network-reachable attacker can inject fake attestation /
epoch state within the per-IP rate limit. This test pins the fix so a
regression that drops the call surfaces immediately in CI.
"""
import ast
import os
import unittest

GOSSIP = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "node", "rustchain_p2p_gossip.py",
)


def _find_function(self, name):
    for node in ast.walk(self.tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    self.fail(f"function {name!r} not found in {GOSSIP}")


class TestGossipReceiverAuth(unittest.TestCase):

    def setUp(self):
        with open(GOSSIP, "r", encoding="utf-8") as fh:
            self.src = fh.read()
        self.tree = ast.parse(self.src)

    def test_receive_gossip_calls_p2p_auth_first(self):
        """receive_gossip() must invoke _require_p2p_read_auth before parsing the body."""
        fn = _find_function(self, "receive_gossip")
        body = fn.body[:8]
        saw_auth = False
        for stmt in body:
            for sub in ast.walk(stmt):
                if isinstance(sub, ast.Call):
                    f = sub.func
                    if isinstance(f, ast.Name) and f.id == "_require_p2p_read_auth":
                        saw_auth = True
        self.assertTrue(
 saw_auth,
 "/p2p/gossip POST no longer calls _require_p2p_read_auth(); "
 "any network-reachable attacker can inject CRDT gossip",
 )

    def test_gossip_auth_precedes_payload_validation(self):
        """Auth gate must run before payload validation."""
        fn = _find_function(self, "receive_gossip")
        body_src = ast.unparse(fn)
        auth_idx = body_src.find("_require_p2p_read_auth")
        validate_idx = body_src.find("validate_gossip_payload(")
        self.assertNotEqual(auth_idx, -1, "no auth call in receive_gossip()")
        self.assertNotEqual(validate_idx, -1, "no payload validation in receive_gossip()")
        self.assertLess(
 auth_idx, validate_idx,
 "auth gate must precede payload validation",
 )


if __name__ == "__main__":
    unittest.main(verbosity=2)
