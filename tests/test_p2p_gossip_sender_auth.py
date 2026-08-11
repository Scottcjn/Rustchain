#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Every /p2p/gossip sender must present X-P2P-Key.

The receiving endpoint does not require the header yet. This test exists so
that requiring it stays a one-line config change instead of a fleet-wide
outage: if a sender is added without the header and the receiver later starts
enforcing, `broadcast()` fan-out 401s and inter-node gossip stops. CI cannot
catch that, since it needs two live nodes, so the invariant is pinned here.

Context: Scottcjn/Rustchain#8190 proposed enforcement on the receiver while
`_send_to_peer()` still sent no header.
"""
import ast
import os
import unittest

GOSSIP = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "node", "rustchain_p2p_gossip.py",
)


def _posts_to_gossip(node):
    """True if this call is requests.post(...) targeting /p2p/gossip."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if not (isinstance(func, ast.Attribute) and func.attr == "post"):
        return False
    for arg in node.args:
        if isinstance(arg, ast.JoinedStr):
            for part in arg.values:
                if isinstance(part, ast.Constant) and "/p2p/gossip" in str(part.value):
                    return True
        if isinstance(arg, ast.Constant) and "/p2p/gossip" in str(arg.value):
            return True
    return False


class TestGossipSendersAuthenticate(unittest.TestCase):

    def setUp(self):
        with open(GOSSIP, "r") as fh:
            self.src = fh.read()
        self.tree = ast.parse(self.src)

    def test_every_gossip_post_sends_the_shared_key(self):
        senders = [n for n in ast.walk(self.tree) if _posts_to_gossip(n)]
        self.assertGreater(len(senders), 0, "found no /p2p/gossip senders to check")

        missing = []
        for call in senders:
            kw = {k.arg for k in call.keywords if k.arg}
            if "headers" not in kw:
                missing.append(call.lineno)
                continue
            headers = next(k.value for k in call.keywords if k.arg == "headers")
            text = ast.dump(headers)
            if "X-P2P-Key" not in text:
                missing.append(call.lineno)

        self.assertEqual(
            missing, [],
            "these /p2p/gossip senders omit the X-P2P-Key header, so gossip "
            f"from them breaks the moment the receiver enforces it: lines {missing}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
