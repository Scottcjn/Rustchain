# SPDX-License-Identifier: MIT
"""
Regression guard for automatic epoch settlement reward scale.

PER_EPOCH_RTC is already the whole epoch pot. finalize_epoch() accepts a
per-block reward and multiplies it by EPOCH_SLOTS internally, so the automatic
settlement path must pass PER_BLOCK_RTC. Passing PER_EPOCH_RTC pays the epoch
pot once per slot and inflates both account rewards and UTXO dual-write mints.
"""

import ast
from pathlib import Path
import unittest


SERVER_PATH = (
    Path(__file__).resolve().parents[1]
    / "rustchain_v2_integrated_v2.2.1_rip200.py"
)


def _integrated_source_tree():
    source = SERVER_PATH.read_text(encoding="utf-8")
    return source, ast.parse(source)


class TestEpochRewardSettlementParameter(unittest.TestCase):
    def test_auto_settlement_passes_per_block_reward_to_finalize_epoch(self):
        source, tree = _integrated_source_tree()
        calls = []

        class Visitor(ast.NodeVisitor):
            def visit_Call(self, call):
                if isinstance(call.func, ast.Name) and call.func.id == "finalize_epoch":
                    calls.append(call)
                self.generic_visit(call)

        Visitor().visit(tree)

        self.assertEqual(
            len(calls),
            1,
            "expected one automatic finalize_epoch() call in the integrated node",
        )
        call = calls[0]
        rendered_call = ast.get_source_segment(source, call)
        self.assertGreaterEqual(len(call.args), 2, rendered_call)
        reward_arg = call.args[1]

        self.assertIsInstance(reward_arg, ast.Name, rendered_call)
        self.assertEqual(
            reward_arg.id,
            "PER_BLOCK_RTC",
            "auto-settlement must pass PER_BLOCK_RTC because finalize_epoch() "
            f"multiplies its reward argument by EPOCH_SLOTS; found {rendered_call}",
        )


if __name__ == "__main__":
    unittest.main()
