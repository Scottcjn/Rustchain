#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Scottcjn/Rustchain#8177 (Finding 2): state-root count_bytes must be big-endian.

compute_box_id() encodes value_nrtc / creation_height / output_index via
to_bytes(N, "big"). compute_state_root() previously mixed
len(rows).to_bytes(8, "little") into the leaf hash, so the count prefix
disagreed with the leaf encoding. Two honest implementations that pick a
single endianness for everything would diverge. This test pins the fix.
"""
import ast
import os
import unittest

UTXO = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "node", "utxo_db.py",
)


def _find_function(self, name):
    for node in ast.walk(self.tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    self.fail(f"function {name!r} not found in {UTXO}")


class TestStateRootEndianness(unittest.TestCase):

    def setUp(self):
        with open(UTXO, "r", encoding="utf-8") as fh:
            self.src = fh.read()
        self.tree = ast.parse(self.src)

    def test_compute_state_root_uses_big_endian_count(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef) and node.name == "compute_state_root":
                fn = node
                break
        else:
            self.fail("compute_state_root() not found")

        for stmt in ast.walk(fn):
            if (
 isinstance(stmt, ast.Assign)
 and len(stmt.targets) == 1
 and isinstance(stmt.targets[0], ast.Name)
 and stmt.targets[0].id == "count_bytes"
 ):
                call = stmt.value
                self.assertIsInstance(call, ast.Call)
                if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant):
                    self.assertEqual(
 call.args[1].value, "big",
 "count_bytes endianness does not match compute_box_id() (uses big)",
 )
                    return
        self.fail("count_bytes = len(rows).to_bytes(...) not found in compute_state_root()")

    def test_no_little_endian_in_compute_state_root(self):
        """Defence-in-depth: forbid little anywhere inside compute_state_root."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef) and node.name == "compute_state_root":
                fn_src = ast.unparse(node)
                self.assertNotIn(
 'little', fn_src,
 "compute_state_root() still uses little-endian encoding",
 )
                return
        self.fail("compute_state_root() not found")


if __name__ == "__main__":
    unittest.main(verbosity=2)
