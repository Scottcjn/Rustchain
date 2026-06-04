# SPDX-License-Identifier: MIT

import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")


class TestMinerHeaderKeySchema(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        self._prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        self._prev_disable_p2p = os.environ.get("RUSTCHAIN_DISABLE_P2P_AUTO_START")
        os.environ["RC_ADMIN_KEY"] = "0123456789abcdef0123456789abcdef"
        os.environ["RUSTCHAIN_DISABLE_P2P_AUTO_START"] = "1"
        self.db_path = str(Path(self._tmp.name) / "fresh-node.db")
        os.environ["RUSTCHAIN_DB_PATH"] = self.db_path

        if NODE_DIR not in sys.path:
            sys.path.insert(0, NODE_DIR)

        spec = importlib.util.spec_from_file_location(
            "rustchain_headerkey_schema_node",
            MODULE_PATH,
        )
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.mod.DB_PATH = self.db_path
        self.mod.init_db()
        self.mod.app.config["TESTING"] = True

    def tearDown(self):
        if self._prev_admin_key is None:
            os.environ.pop("RC_ADMIN_KEY", None)
        else:
            os.environ["RC_ADMIN_KEY"] = self._prev_admin_key
        if self._prev_db_path is None:
            os.environ.pop("RUSTCHAIN_DB_PATH", None)
        else:
            os.environ["RUSTCHAIN_DB_PATH"] = self._prev_db_path
        if self._prev_disable_p2p is None:
            os.environ.pop("RUSTCHAIN_DISABLE_P2P_AUTO_START", None)
        else:
            os.environ["RUSTCHAIN_DISABLE_P2P_AUTO_START"] = self._prev_disable_p2p
        self._tmp.cleanup()

    def test_init_db_creates_miner_header_keys_for_headerkey_route(self):
        with sqlite3.connect(self.db_path) as conn:
            table = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='miner_header_keys'",
            ).fetchone()
            history_table = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='miner_header_key_history'",
            ).fetchone()
            audit_table = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='miner_header_key_audit'",
            ).fetchone()

        self.assertIsNotNone(table)
        self.assertIsNotNone(history_table)
        self.assertIsNotNone(audit_table)

        with self.mod.app.test_client() as client:
            response = client.post(
                "/miner/headerkey",
                headers={"X-API-Key": "0123456789abcdef0123456789abcdef"},
                json={"miner_id": "miner-1", "pubkey_hex": "a" * 64, "reason": "initial key"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body, {"ok": True, "miner_id": "miner-1", "pubkey_hex": "a" * 64})

        with sqlite3.connect(self.db_path) as conn:
            stored = conn.execute(
                "SELECT pubkey_hex FROM miner_header_keys WHERE miner_id = ?",
                ("miner-1",),
            ).fetchone()
            history = conn.execute(
                """SELECT pubkey_hex, previous_pubkey_hex, reason
                   FROM miner_header_key_history WHERE miner_id = ?""",
                ("miner-1",),
            ).fetchall()
            audit = conn.execute(
                """SELECT action, pubkey_hex, previous_pubkey_hex, reason
                   FROM miner_header_key_audit WHERE miner_id = ?""",
                ("miner-1",),
            ).fetchall()

        self.assertEqual(stored, ("a" * 64,))
        self.assertEqual(history, [("a" * 64, None, "initial key")])
        self.assertEqual(audit, [("registered", "a" * 64, None, "initial key")])

    def test_headerkey_rotation_preserves_identity_and_records_history(self):
        with self.mod.app.test_client() as client:
            first = client.post(
                "/miner/headerkey",
                headers={"X-API-Key": "0123456789abcdef0123456789abcdef"},
                json={"miner_id": "validator-1", "pubkey_hex": "a" * 64, "reason": "initial"},
            )
            second = client.post(
                "/miner/headerkey",
                headers={"X-API-Key": "0123456789abcdef0123456789abcdef"},
                json={"miner_id": "validator-1", "pubkey_hex": "b" * 64, "reason": "rotation"},
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(
            second.get_json(),
            {"ok": True, "miner_id": "validator-1", "pubkey_hex": "b" * 64},
        )

        with sqlite3.connect(self.db_path) as conn:
            active = conn.execute(
                "SELECT miner_id, pubkey_hex FROM miner_header_keys WHERE miner_id = ?",
                ("validator-1",),
            ).fetchone()
            history = conn.execute(
                """SELECT pubkey_hex, previous_pubkey_hex, reason
                   FROM miner_header_key_history
                   WHERE miner_id = ?
                   ORDER BY id""",
                ("validator-1",),
            ).fetchall()
            audit = conn.execute(
                """SELECT action, pubkey_hex, previous_pubkey_hex, reason
                   FROM miner_header_key_audit
                   WHERE miner_id = ?
                   ORDER BY id""",
                ("validator-1",),
            ).fetchall()

        self.assertEqual(active, ("validator-1", "b" * 64))
        self.assertEqual(
            history,
            [
                ("a" * 64, None, "initial"),
                ("b" * 64, "a" * 64, "rotation"),
            ],
        )
        self.assertEqual(
            audit,
            [
                ("registered", "a" * 64, None, "initial"),
                ("rotated", "b" * 64, "a" * 64, "rotation"),
            ],
        )

    def test_headerkey_same_key_is_audited_without_extra_history(self):
        with self.mod.app.test_client() as client:
            client.post(
                "/miner/headerkey",
                headers={"X-API-Key": "0123456789abcdef0123456789abcdef"},
                json={"miner_id": "validator-2", "pubkey_hex": "c" * 64},
            )
            duplicate = client.post(
                "/miner/headerkey",
                headers={"X-API-Key": "0123456789abcdef0123456789abcdef"},
                json={"miner_id": "validator-2", "pubkey_hex": "c" * 64, "reason": "repeat"},
            )

        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(
            duplicate.get_json(),
            {"ok": True, "miner_id": "validator-2", "pubkey_hex": "c" * 64},
        )

        with sqlite3.connect(self.db_path) as conn:
            history_count = conn.execute(
                "SELECT COUNT(*) FROM miner_header_key_history WHERE miner_id = ?",
                ("validator-2",),
            ).fetchone()[0]
            audit = conn.execute(
                """SELECT action, pubkey_hex, previous_pubkey_hex, reason
                   FROM miner_header_key_audit
                   WHERE miner_id = ?
                   ORDER BY id""",
                ("validator-2",),
            ).fetchall()

        self.assertEqual(history_count, 1)
        self.assertEqual(
            audit,
            [
                ("registered", "c" * 64, None, ""),
                ("unchanged", "c" * 64, "c" * 64, "repeat"),
            ],
        )

    def test_headerkey_record_helper_audits_enroll_and_attest_paths(self):
        with sqlite3.connect(self.db_path) as conn:
            self.mod._record_miner_header_key(
                conn,
                "validator-3",
                "d" * 64,
                actor="attest_auto_enroll",
                reason="attestation auto-enroll",
                rotated_at=100,
            )
            self.mod._record_miner_header_key(
                conn,
                "validator-3",
                "d" * 64,
                actor="epoch_enroll",
                reason="epoch enroll",
                rotated_at=101,
            )
            self.mod._record_miner_header_key(
                conn,
                "validator-3",
                "e" * 64,
                actor="epoch_enroll",
                reason="epoch enroll",
                rotated_at=102,
            )

            history = conn.execute(
                """SELECT pubkey_hex, previous_pubkey_hex, rotated_by, reason
                   FROM miner_header_key_history
                   WHERE miner_id = ?
                   ORDER BY id""",
                ("validator-3",),
            ).fetchall()
            audit = conn.execute(
                """SELECT action, pubkey_hex, previous_pubkey_hex, actor, reason
                   FROM miner_header_key_audit
                   WHERE miner_id = ?
                   ORDER BY id""",
                ("validator-3",),
            ).fetchall()

        self.assertEqual(
            history,
            [
                ("d" * 64, None, "attest_auto_enroll", "attestation auto-enroll"),
                ("e" * 64, "d" * 64, "epoch_enroll", "epoch enroll"),
            ],
        )
        self.assertEqual(
            audit,
            [
                ("registered", "d" * 64, None, "attest_auto_enroll", "attestation auto-enroll"),
                ("unchanged", "d" * 64, "d" * 64, "epoch_enroll", "epoch enroll"),
                ("rotated", "e" * 64, "d" * 64, "epoch_enroll", "epoch enroll"),
            ],
        )

    def test_headerkey_route_uses_immediate_transaction_for_rotation(self):
        source = Path(MODULE_PATH).read_text(encoding="utf-8")
        route_source = source[
            source.index("@app.route('/miner/headerkey'"):
            source.index("@app.route('/headers/ingest_signed'")
        ]

        self.assertIn('db.execute("BEGIN IMMEDIATE")', route_source)
        self.assertIn("_record_miner_header_key(", route_source)

    def test_enroll_and_attest_headerkey_writes_use_immediate_transaction(self):
        source = Path(MODULE_PATH).read_text(encoding="utf-8")
        attest_auto_enroll_source = source[
            source.index('with closing(sqlite3.connect(DB_PATH)) as enroll_conn:'):
            source.index('actor="attest_auto_enroll"')
        ]
        epoch_enroll_source = source[
            source.index('with sqlite3.connect(DB_PATH) as c:', source.index("def enroll_epoch()")):
            source.index('actor="epoch_enroll"')
        ]

        self.assertIn('enroll_conn.execute("BEGIN IMMEDIATE")', attest_auto_enroll_source)
        self.assertIn("_record_miner_header_key(", attest_auto_enroll_source)
        self.assertLess(
            attest_auto_enroll_source.index('enroll_conn.execute("BEGIN IMMEDIATE")'),
            attest_auto_enroll_source.index("_record_miner_header_key("),
        )
        self.assertIn('c.execute("BEGIN IMMEDIATE")', epoch_enroll_source)
        self.assertIn("_record_miner_header_key(", epoch_enroll_source)
        self.assertLess(
            epoch_enroll_source.index('c.execute("BEGIN IMMEDIATE")'),
            epoch_enroll_source.index("_record_miner_header_key("),
        )


if __name__ == "__main__":
    unittest.main()
