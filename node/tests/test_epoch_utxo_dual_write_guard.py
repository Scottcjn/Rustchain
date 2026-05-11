# SPDX-License-Identifier: MIT
"""
Regression coverage for epoch reward UTXO dual-write integration.

The integrated server is expensive to import in isolation, so these tests parse
the source and verify that finalize_epoch() keeps the UTXO reward write behind
the configured feature gate and treats failed UTXO application as fatal.
"""

import ast
from pathlib import Path
import unittest


SERVER_PATH = (
    Path(__file__).resolve().parents[1]
    / "rustchain_v2_integrated_v2.2.1_rip200.py"
)


def _finalize_epoch_node():
    source = SERVER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "finalize_epoch":
            return node, ast.get_source_segment(source, node)
    raise AssertionError("finalize_epoch() not found")


class TestEpochUtxoDualWriteGuard(unittest.TestCase):
    def test_epoch_reward_utxo_write_respects_feature_gate(self):
        _, source = _finalize_epoch_node()

        self.assertIn(
            "if UTXO_DUAL_WRITE",
            source,
            "finalize_epoch() must not write UTXOs while UTXO_DUAL_WRITE is off",
        )

    def test_epoch_reward_utxo_db_uses_configured_db_path(self):
        node, _ = _finalize_epoch_node()
        calls = []

        class Visitor(ast.NodeVisitor):
            def visit_Call(self, call):
                if isinstance(call.func, ast.Name) and call.func.id == "UtxoDB":
                    calls.append(call)
                self.generic_visit(call)

        Visitor().visit(node)

        self.assertTrue(calls, "finalize_epoch() should construct UtxoDB")
        for call in calls:
            self.assertEqual(
                len(call.args),
                1,
                "UtxoDB must be constructed with DB_PATH inside finalize_epoch()",
            )
            self.assertIsInstance(call.args[0], ast.Name)
            self.assertEqual(call.args[0].id, "DB_PATH")

    def test_epoch_reward_utxo_apply_failure_aborts_settlement(self):
        _, source = _finalize_epoch_node()

        self.assertIn(
            "utxo_ok =",
            source,
            "finalize_epoch() should store the UTXO apply result",
        )
        self.assertIn(
            "if not utxo_ok",
            source,
            "finalize_epoch() must abort instead of committing account rewards when UTXO apply fails",
        )


if __name__ == "__main__":
    unittest.main()
