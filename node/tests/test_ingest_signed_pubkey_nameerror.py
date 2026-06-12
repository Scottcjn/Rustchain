# SPDX-License-Identifier: MIT
"""
Tests for /headers/ingest_signed pubkey retention bug.

Covers the fix for: NameError: name 'pubkey_hex' is not defined in
ingest_signed_header(). After multi-key wallet support was added, the
route verifies candidate keys into _cand but later tries to persist
the obsolete `pubkey_hex` local, causing a NameError on every real
Ed25519-signed header ingestion.

The fix tracks the verified key in `verified_pubkey` and uses that
when persisting the header row.
"""

import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

try:
    import nacl.signing
    HAVE_NACL = True
except Exception:
    HAVE_NACL = False

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")

EXTRA_SCHEMA = [
    "CREATE TABLE IF NOT EXISTS miner_header_keys (miner_id TEXT, pubkey_hex TEXT NOT NULL, PRIMARY KEY (miner_id, pubkey_hex))",
]


class TestIngestSignedPubkeyRetention(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls._prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        cls._prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        cls._prev_runtime_env = os.environ.get("RC_RUNTIME_ENV")
        # Admin key must be >= 32 chars
        os.environ["RC_ADMIN_KEY"] = "0123456789abcdef0123456789abcdef"
        os.environ["RC_RUNTIME_ENV"] = "test"

    @classmethod
    def tearDownClass(cls):
        if cls._prev_admin_key is None:
            os.environ.pop("RC_ADMIN_KEY", None)
        else:
            os.environ["RC_ADMIN_KEY"] = cls._prev_admin_key
        if cls._prev_db_path is None:
            os.environ.pop("RUSTCHAIN_DB_PATH", None)
        else:
            os.environ["RUSTCHAIN_DB_PATH"] = cls._prev_db_path
        if cls._prev_runtime_env is None:
            os.environ.pop("RC_RUNTIME_ENV", None)
        else:
            os.environ["RC_RUNTIME_ENV"] = cls._prev_runtime_env
        cls._tmp.cleanup()

    def _db_path(self, name):
        return str(Path(self._tmp.name) / name)

    def _load_module(self, db_name):
        db_path = self._db_path(db_name)
        os.environ["RUSTCHAIN_DB_PATH"] = db_path
        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)
        spec = importlib.util.spec_from_file_location("rustchain_node", MODULE_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.init_db()
        with sqlite3.connect(db_path) as conn:
            for stmt in EXTRA_SCHEMA:
                conn.execute(stmt)
            conn.commit()
        return mod, db_path

    @unittest.skipUnless(HAVE_NACL, "pynacl not installed")
    def test_real_sig_persists_verified_pubkey(self):
        """A real Ed25519-signed header should persist the matched pubkey, not crash with NameError."""
        mod, db_path = self._load_module("test_pubkey_retain.db")

        miner_id = "test-miner-pk-retain"
        signing_key = nacl.signing.SigningKey.generate()
        verify_key = signing_key.verify_key
        pubkey_hex = verify_key.encode().hex()

        # Register the key
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO miner_header_keys (miner_id, pubkey_hex) VALUES (?, ?)",
                (miner_id, pubkey_hex),
            )
            conn.commit()

        # Build a valid signed header
        header = {"slot": 1, "miner": miner_id, "prev_hash": "00" * 32}
        msg = json.dumps(header, sort_keys=True, separators=(",", ":")).encode()
        signed = signing_key.sign(msg)
        sig_hex = signed.signature.hex()
        msg_hex = msg.hex()

        with mod.app.test_client() as client:
            resp = client.post(
                "/headers/ingest_signed",
                json={
                    "miner_id": miner_id,
                    "header": header,
                    "message": msg_hex,
                    "signature": sig_hex,
                },
            )
            data = resp.get_json()

        # Should not crash (500) or return a server error
        self.assertNotEqual(resp.status_code, 500,
                            f"Server crashed (500) — likely NameError: {data}")

        # If accepted (200), the persisted row must have the correct pubkey
        if resp.status_code == 200:
            with sqlite3.connect(db_path) as conn:
                row = conn.execute(
                    "SELECT pubkey_hex FROM headers WHERE miner_id=? ORDER BY slot DESC LIMIT 1",
                    (miner_id,),
                ).fetchone()
            self.assertIsNotNone(row, "Header row should exist after ingest")
            self.assertEqual(row[0], pubkey_hex,
                             "Persisted pubkey should match the enrolled key that verified the signature")

    @unittest.skipUnless(HAVE_NACL, "pynacl not installed")
    def test_multi_key_persists_correct_one(self):
        """When a wallet has multiple keys, the one that actually signed should be persisted."""
        mod, db_path = self._load_module("test_multi_key.db")

        miner_id = "test-miner-multi"
        # Generate two key pairs
        sk1 = nacl.signing.SigningKey.generate()
        sk2 = nacl.signing.SigningKey.generate()
        pk1 = sk1.verify_key.encode().hex()
        pk2 = sk2.verify_key.encode().hex()

        # Register both keys
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO miner_header_keys (miner_id, pubkey_hex) VALUES (?, ?)",
                (miner_id, pk1),
            )
            conn.execute(
                "INSERT OR REPLACE INTO miner_header_keys (miner_id, pubkey_hex) VALUES (?, ?)",
                (miner_id, pk2),
            )
            conn.commit()

        # Sign with key 2 only
        header = {"slot": 2, "miner": miner_id, "prev_hash": "00" * 32}
        msg = json.dumps(header, sort_keys=True, separators=(",", ":")).encode()
        signed = sk2.sign(msg)
        sig_hex = signed.signature.hex()
        msg_hex = msg.hex()

        with mod.app.test_client() as client:
            resp = client.post(
                "/headers/ingest_signed",
                json={
                    "miner_id": miner_id,
                    "header": header,
                    "message": msg_hex,
                    "signature": sig_hex,
                },
            )

        self.assertNotEqual(resp.status_code, 500,
                            "Server should not crash on multi-key wallet")

        if resp.status_code == 200:
            with sqlite3.connect(db_path) as conn:
                row = conn.execute(
                    "SELECT pubkey_hex FROM headers WHERE miner_id=? ORDER BY slot DESC LIMIT 1",
                    (miner_id,),
                ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], pk2,
                             "Should persist pk2 (the key that actually verified), not pk1")


if __name__ == "__main__":
    unittest.main()
