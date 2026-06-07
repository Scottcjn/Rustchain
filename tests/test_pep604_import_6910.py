# SPDX-License-Identifier: MIT
# Copyright (c) 2025 RustChain Contributors
"""
Regression test for #6910: Windows miner must be importable on Python 3.9+.

The module uses PEP 604 union syntax (dict | None) in function annotations,
which raises TypeError at import time on Python 3.9 unless
`from __future__ import annotations` is present.
"""

import sys
import importlib
import unittest


class TestPEP604Import(unittest.TestCase):
    """Verify the Windows miner module can be imported without TypeError."""

    def test_import_on_supported_python(self):
        """Importing the Windows miner should not raise TypeError on 3.9+."""
        # The module has external dependencies that may not be installed,
        # so we only verify that annotation evaluation does not fail.
        # We do this by checking that `from __future__ import annotations`
        # is present in the source, and that parsing succeeds.
        import ast
        with open("miners/windows/rustchain_windows_miner.py") as f:
            source = f.read()

        tree = ast.parse(source)

        # Verify the __future__ import is present
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
        On Python 3.9, `dict | None` in annotations would raise TypeError
        at import time. With `from __future__ import annotations`, annotations
        are strings and never evaluated, so the module can be imported.
        """
        # Check that the problematic annotations exist in source
        with open("miners/windows/rustchain_windows_miner.py") as f:
            source = f.read()

        self.assertIn("dict | None", source,
                       "Expected PEP 604 annotation not found in source")

        # Verify the module can be parsed (covers annotation syntax)
        import ast
        try:
            ast.parse(source)
        except SyntaxError:
            self.fail("Module source has syntax errors")


if __name__ == "__main__":
    unittest.main()
