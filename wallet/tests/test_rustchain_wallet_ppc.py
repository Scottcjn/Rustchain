"""
Tests for rustchain_wallet_ppc.py Python 3 compatibility.

Verifies that the module:
1. Does not use Python 2-only top-level imports (urllib2, Tkinter, tkMessageBox, tkSimpleDialog)
2. Uses Python 3 urllib.request and tkinter equivalents in try/except guards
3. Encodes strings to bytes before hashlib.sha256()
4. Decodes response bytes to str before json.loads()
"""
import ast
import hashlib
import json
import sys
import unittest
from pathlib import Path

WALLET_PPC_PATH = Path(__file__).parent.parent / "rustchain_wallet_ppc.py"


def _top_level_import_names(source: str) -> list:
    """Return import names that appear at module top level (not inside try/except)."""
    tree = ast.parse(source)
    names = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.append(node.module)
    return names


def _all_import_names(source: str) -> list:
    """Return ALL import names anywhere in the source (including inside try/except)."""
    tree = ast.parse(source)
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.append(node.module)
    return names


class TestImportCompatibility(unittest.TestCase):
    """Verify module imports are compatible with Python 3."""

    def setUp(self):
        with open(WALLET_PPC_PATH) as f:
            self.source = f.read()
        self.top_level = _top_level_import_names(self.source)
        self.all_imports = _all_import_names(self.source)

    def test_no_top_level_urllib2(self):
        """urllib2 must not be a top-level import — it does not exist in Python 3."""
        self.assertNotIn(
            "urllib2",
            self.top_level,
            "Top-level 'import urllib2' crashes Python 3 immediately. "
            "Wrap in try/except and use 'from urllib.request import urlopen, Request'.",
        )

    def test_no_top_level_python2_tkinter_names(self):
        """Python 2 Tkinter module names must not appear at top level."""
        for name in ("Tkinter", "tkMessageBox", "tkSimpleDialog"):
            self.assertNotIn(
                name,
                self.top_level,
                f"Top-level 'import {name}' crashes Python 3. "
                f"Wrap in try/except: try tkinter (Py3), fallback {name} (Py2).",
            )

    def test_urllib_request_present(self):
        """urllib.request must appear somewhere as the Python 3 HTTP import path."""
        self.assertIn(
            "urllib.request",
            self.all_imports,
            "Python 3 path 'from urllib.request import ...' not found. "
            "Add it in a try block so Python 3 users can run the wallet.",
        )

    def test_tkinter_lowercase_present(self):
        """tkinter (lowercase) must appear somewhere as the Python 3 Tkinter path."""
        self.assertIn(
            "tkinter",
            self.all_imports,
            "Python 3 path 'import tkinter' not found. "
            "Add 'import tkinter as tk' in a try block.",
        )


class TestHashlibEncoding(unittest.TestCase):
    """Verify wallet address generation encodes strings before sha256."""

    def test_source_encodes_before_sha256(self):
        """Source uses isinstance(miner_id, bytes) guard before sha256 (correct on Py2+Py3)."""
        with open(WALLET_PPC_PATH) as f:
            source = f.read()
        self.assertIn(
            "isinstance(miner_id, bytes)",
            source,
            "Source must check 'isinstance(miner_id, bytes)' before sha256. "
            "On Python 2, str IS bytes so no double-encode; on Python 3, str gets encoded.",
        )
        self.assertIn(
            ".encode(",
            source,
            "Source must call .encode() to convert str to bytes for sha256 on Python 3.",
        )

    def test_sha256_with_encoded_bytes(self):
        """sha256 of an encoded hostname string produces a valid 40-char hex digest."""
        hostname = "test-ppc-mac"
        miner_id = "ppc-wallet-%s" % hostname
        miner_id_bytes = miner_id.encode("utf-8")
        wallet_hash = hashlib.sha256(miner_id_bytes).hexdigest()[:40]
        self.assertEqual(len(wallet_hash), 40)
        self.assertTrue(all(c in "0123456789abcdef" for c in wallet_hash))

    def test_wallet_address_format(self):
        """Generated wallet address is 43 chars: 40 hex + 'RTC'."""
        miner_id_bytes = b"ppc-wallet-test-host"
        wallet_hash = hashlib.sha256(miner_id_bytes).hexdigest()[:40]
        wallet_addr = "%sRTC" % wallet_hash
        self.assertTrue(wallet_addr.endswith("RTC"))
        self.assertEqual(len(wallet_addr), 43)

    def test_sha256_with_bare_str_raises_on_python3(self):
        """Confirm that bare str raises TypeError in Python 3 (documents the bug)."""
        if sys.version_info[0] < 3:
            self.skipTest("Python 2 allows str in sha256")
        with self.assertRaises(TypeError):
            hashlib.sha256("ppc-wallet-test")  # type: ignore[arg-type]


class TestSimpleJSONStringTypes(unittest.TestCase):
    """Verify SimpleJSON fallback handles both str and unicode (Python 2 basestring)."""

    def test_source_uses_str_types_not_bare_str(self):
        """SimpleJSON.dumps() must use _str_types, not bare isinstance(obj, str)."""
        with open(WALLET_PPC_PATH) as f:
            source = f.read()
        self.assertIn(
            "_str_types",
            source,
            "Source must define _str_types (basestring on Py2, str on Py3) and use it "
            "in SimpleJSON.dumps() so Python 2 unicode values are serialized correctly.",
        )
        self.assertIn(
            "isinstance(obj, _str_types)",
            source,
            "SimpleJSON.dumps() must use isinstance(obj, _str_types), not isinstance(obj, str).",
        )


class TestResponseDecoding(unittest.TestCase):
    """Verify HTTP response bytes are decoded before json.loads()."""

    def test_source_decodes_response(self):
        """Source must call .decode() on response data (Python 3 returns bytes)."""
        with open(WALLET_PPC_PATH) as f:
            source = f.read()
        self.assertIn(
            "decode",
            source,
            "Source must decode response.read() bytes to str before json.loads(). "
            "Python 3's urllib returns bytes; json.loads() needs str (or bytes in Py3.6+, "
            "but explicit decode ensures Py2 compatibility too).",
        )

    def test_json_loads_decoded_bytes_balance(self):
        """json.loads works correctly on a decoded balance response."""
        raw = b'{"balance_rtc": 42.5}'
        decoded = raw.decode("utf-8")
        data = json.loads(decoded)
        self.assertEqual(data["balance_rtc"], 42.5)

    def test_json_loads_decoded_bytes_transfer(self):
        """json.loads works correctly on a decoded transfer response."""
        raw = b'{"ok": true, "txid": "abc123"}'
        decoded = raw.decode("utf-8")
        data = json.loads(decoded)
        self.assertTrue(data["ok"])
        self.assertEqual(data["txid"], "abc123")


if __name__ == "__main__":
    unittest.main()
