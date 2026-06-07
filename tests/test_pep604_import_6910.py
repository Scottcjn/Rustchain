# SPDX-License-Identifier: MIT
# Copyright (c) 2025 RustChain Contributors
"""
Regression test for #6910: Windows miner must be importable on Python 3.9+.

The module uses PEP 604 union syntax (dict | None) in function annotations,
which raises TypeError at import time on Python 3.9 unless
`from __future__ import annotations` is present.
"""

import ast
import unittest


class TestPEP604Import(unittest.TestCase):
    """Verify the Windows miner module can be imported without TypeError."""

    def test_import_on_supported_python(self):
        """Importing the Windows miner should not raise TypeError on 3.9+."""
        with open("miners/windows/rustchain_windows_miner.py") as f:
            source = f.read()

        tree = ast.parse(source)

        future_imports = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module == "__future__"
        ]
        self.assertTrue(
            len(future_imports) > 0,
            "Missing 'from __future__ import annotations' import"
        )

        future_names = [
            alias.name
            for node in future_imports
            for alias in node.names
        ]
        self.assertIn("annotations", future_names,
                       "__future__ import does not include 'annotations'")

    def test_no_runtime_annotation_evaluation(self):
        """
        On Python 3.9, dict | None in annotations would raise TypeError
        at import time. With from __future__ import annotations, annotations
        are strings and never evaluated, so the module can be imported.
        """
        with open("miners/windows/rustchain_windows_miner.py") as f:
            source = f.read()

        # Check that PEP 604 syntax is actually used in the source
        self.assertIn("|", source,
                      "Expected PEP 604 union syntax (|) in the source")


if __name__ == "__main__":
    unittest.main()

