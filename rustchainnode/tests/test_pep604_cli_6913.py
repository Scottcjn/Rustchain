# SPDX-License-Identifier: MIT
# Copyright (c) 2025 RustChain Contributors
"""
Regression test for #6913: rustchainnode CLI must be importable on Python 3.9+.

The module uses PEP 604 union syntax (bytes | str) in function annotations,
which raises TypeError at import time on Python 3.9 unless
`from __future__ import annotations` is present.
"""

import ast
import unittest


class TestPEP604CLIImport(unittest.TestCase):
    """Verify the CLI module can be imported without TypeError."""

    def test_future_import_present(self):
        """The __future__ annotations import should be in the CLI module."""
        with open("rustchainnode/rustchainnode/cli.py") as f:
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

    def test_pep604_syntax_exists(self):
        """Verify that PEP 604 union syntax is actually used in the source."""
        with open("rustchainnode/rustchainnode/cli.py") as f:
            source = f.read()
        self.assertIn("|", source,
                      "Expected PEP 604 union syntax (|) in the source")


if __name__ == "__main__":
    unittest.main()

