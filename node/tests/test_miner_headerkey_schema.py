# SPDX-License-Identifier: MIT

import importlib.util
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


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

    def _rotation_eval(self):
        return {
            "measurement_nonce": "nonce",
            "previous_epoch_block_hash": "prev",
            "active_checks": [],
            "passed_active_checks": [],
            "failed_active_checks": [],
            "active_pass_count": 0,
            "active_total": 0,
            "active_ratio": 1.0,
        }

    def test_init_db_preserves_composite_keys_and_route_creates_audit_tables(self):
        with sqlite3.connect(self.db_path) as conn:
            pk_cols = [
                row[1]
                for row in conn.execute("PRAGMA table_info(miner_header_keys)").fetchall()
                if row[5]
            ]

        self.assertEqual(pk_cols, ["miner_id", "pubkey_hex"])

        with self.mod.app.test_client() as client:
            response = client.post(
                "/miner/headerkey",
                headers={"X-API-Key": "0123456789abcdef0123456789abcdef"},
                json={"miner_id": "schema-miner", "pubkey_hex": "9" * 64},
            )

        self.assertEqual(response.status_code, 200)
        with sqlite3.connect(self.db_path) as conn:
            history_table = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='miner_header_key_history'",
            ).fetchone()
            audit_table = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='miner_header_key_audit'",
            ).fetchone()

        self.assertIsNotNone(history_table)
        self.assertIsNotNone(audit_table)

    def test_admin_register_adds_key_without_overwriting_existing_key(self):
        with self.mod.app.test_client() as client:
            first = client.post(
                "/miner/headerkey",
                headers={"X-API-Key": "0123456789abcdef0123456789abcdef"},
                json={"miner_id": "validator-1", "pubkey_hex": "a" * 64, "reason": "initial"},
            )
            second = client.post(
                "/miner/headerkey",
                headers={"X-API-Key": "0123456789abcdef0123456789abcdef"},
                json={"miner_id": "validator-1", "pubkey_hex": "b" * 64, "reason": "second device"},
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)

        with sqlite3.connect(self.db_path) as conn:
            keys = conn.execute(
                "SELECT pubkey_hex FROM miner_header_keys WHERE miner_id = ? ORDER BY pubkey_hex",
                ("validator-1",),
            ).fetchall()
            bootstrap = conn.execute(
                "SELECT pubkey_hex FROM miner_header_bootstrap WHERE miner_id = ? ORDER BY pubkey_hex",
                ("validator-1",),
            ).fetchall()
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

        self.assertEqual(keys, [("a" * 64,), ("b" * 64,)])
        self.assertEqual(bootstrap, [("a" * 64,), ("b" * 64,)])
        self.assertEqual(
            history,
            [
                ("a" * 64, None, "initial"),
                ("b" * 64, "a" * 64, "second device"),
            ],
        )
        self.assertEqual(
            audit,
            [
                ("registered", "a" * 64, None, "initial"),
                ("added", "b" * 64, "a" * 64, "second device"),
            ],
        )

    def test_admin_reregister_is_audited_without_extra_history(self):
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

    def test_admin_revoke_records_audit_and_removes_allowlist(self):
        with self.mod.app.test_client() as client:
            client.post(
                "/miner/headerkey",
                headers={"X-API-Key": "0123456789abcdef0123456789abcdef"},
                json={"miner_id": "validator-3", "pubkey_hex": "d" * 64},
            )
            revoked = client.post(
                "/miner/headerkey",
                headers={"X-API-Key": "0123456789abcdef0123456789abcdef"},
                json={
                    "miner_id": "validator-3",
                    "pubkey_hex": "d" * 64,
                    "action": "revoke",
                    "reason": "retired device",
                },
            )

        self.assertEqual(revoked.status_code, 200)
        with sqlite3.connect(self.db_path) as conn:
            key = conn.execute(
                "SELECT 1 FROM miner_header_keys WHERE miner_id = ? AND pubkey_hex = ?",
                ("validator-3", "d" * 64),
            ).fetchone()
            bootstrap = conn.execute(
                "SELECT 1 FROM miner_header_bootstrap WHERE miner_id = ? AND pubkey_hex = ?",
                ("validator-3", "d" * 64),
            ).fetchone()
            audit = conn.execute(
                """SELECT action, pubkey_hex, previous_pubkey_hex, reason
                   FROM miner_header_key_audit
                   WHERE miner_id = ?
                   ORDER BY id""",
                ("validator-3",),
            ).fetchall()

        self.assertIsNone(key)
        self.assertIsNone(bootstrap)
        self.assertEqual(audit[-1], ("revoked", "d" * 64, "d" * 64, "retired device"))

    def test_register_helper_audits_enroll_and_attest_without_autoseeding_bootstrap(self):
        with sqlite3.connect(self.db_path) as conn:
            self.mod._register_header_key(
                conn,
                "validator-4",
                "e" * 64,
                actor="attest_auto_enroll",
                reason="attestation auto-enroll",
                created_at=100,
            )
            self.mod._register_header_key(
                conn,
                "validator-4",
                "e" * 64,
                actor="epoch_enroll",
                reason="epoch enroll",
                created_at=101,
            )
            conn.execute(
                "INSERT OR IGNORE INTO miner_header_bootstrap(miner_id,pubkey_hex) VALUES(?,?)",
                ("validator-4", "f" * 64),
            )
            self.mod._register_header_key(
                conn,
                "validator-4",
                "f" * 64,
                actor="epoch_enroll",
                reason="second device",
                created_at=102,
            )

            bootstrap = conn.execute(
                "SELECT pubkey_hex FROM miner_header_bootstrap WHERE miner_id = ? ORDER BY pubkey_hex",
                ("validator-4",),
            ).fetchall()
            keys = conn.execute(
                "SELECT pubkey_hex FROM miner_header_keys WHERE miner_id = ? ORDER BY pubkey_hex",
                ("validator-4",),
            ).fetchall()
            audit = conn.execute(
                """SELECT action, pubkey_hex, previous_pubkey_hex, actor, reason
                   FROM miner_header_key_audit
                   WHERE miner_id = ?
                   ORDER BY id""",
                ("validator-4",),
            ).fetchall()

        self.assertEqual(bootstrap, [("f" * 64,)])
        self.assertEqual(keys, [("e" * 64,), ("f" * 64,)])
        self.assertEqual(
            audit,
            [
                ("registered", "e" * 64, None, "attest_auto_enroll", "attestation auto-enroll"),
                ("unchanged", "e" * 64, "e" * 64, "epoch_enroll", "epoch enroll"),
                ("added", "f" * 64, "e" * 64, "epoch_enroll", "second device"),
            ],
        )

    def test_epoch_enroll_headerkey_write_executes_end_to_end(self):
        previous_legacy = self.mod.ENROLL_ALLOW_UNSIGNED_LEGACY
        previous_ticket = self.mod.ENROLL_REQUIRE_TICKET
        previous_mac = self.mod.ENROLL_REQUIRE_MAC
        self.mod.ENROLL_ALLOW_UNSIGNED_LEGACY = True
        self.mod.ENROLL_REQUIRE_TICKET = False
        self.mod.ENROLL_REQUIRE_MAC = False
        try:
            with patch.object(self.mod, "current_slot", return_value=0), \
                 patch.object(self.mod, "evaluate_rotating_fingerprint_checks", return_value=self._rotation_eval()):
                with self.mod.app.test_client() as client:
                    response = client.post(
                        "/epoch/enroll",
                        json={
                            "miner_pubkey": "f" * 64,
                            "miner_id": "epoch-runtime-miner",
                            "device": {"family": "x86", "arch": "default"},
                        },
                    )
        finally:
            self.mod.ENROLL_ALLOW_UNSIGNED_LEGACY = previous_legacy
            self.mod.ENROLL_REQUIRE_TICKET = previous_ticket
            self.mod.ENROLL_REQUIRE_MAC = previous_mac

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        with sqlite3.connect(self.db_path) as conn:
            active = conn.execute(
                "SELECT pubkey_hex FROM miner_header_keys WHERE miner_id = ?",
                ("epoch-runtime-miner",),
            ).fetchone()
            audit = conn.execute(
                """SELECT action, actor, pubkey_hex
                   FROM miner_header_key_audit
                   WHERE miner_id = ?""",
                ("epoch-runtime-miner",),
            ).fetchone()

        self.assertEqual(active, ("f" * 64,))
        self.assertEqual(audit, ("registered", "epoch_enroll", "f" * 64))

    def test_attest_auto_enroll_headerkey_write_executes_end_to_end(self):
        payload = {
            "miner": "runtime-attest-wallet",
            "miner_id": "attest-runtime-miner",
            "public_key": "a" * 64,
            "report": {"nonce": "runtime-nonce", "commitment": "runtime-commitment"},
            "device": {"family": "x86", "arch": "default", "model": "runtime-box", "cores": 4},
            "signals": {"hostname": "runtime-host", "macs": []},
            "fingerprint": {"checks": {"cpu_brand": "Intel test CPU"}},
        }

        with patch.object(self.mod, "check_ip_rate_limit", return_value=(True, "ok")), \
             patch.object(self.mod, "attest_validate_and_store_nonce", return_value=(True, None, None)), \
             patch.object(self.mod, "_check_hardware_binding", return_value=(True, "ok", payload["miner"])), \
             patch.object(self.mod, "validate_fingerprint_data", return_value=(True, "ok")), \
             patch.object(self.mod, "check_vm_signatures_server_side", return_value=(True, "clean")), \
             patch.object(self.mod, "_check_welcome_bonus", return_value=None), \
             patch.object(self.mod, "record_macs", return_value=None), \
             patch.object(self.mod, "current_slot", return_value=0), \
             patch.object(self.mod, "evaluate_rotating_fingerprint_checks", return_value=self._rotation_eval()):
            with self.mod.app.test_client() as client:
                response = client.post("/attest/submit", json=payload)

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        with sqlite3.connect(self.db_path) as conn:
            active = conn.execute(
                "SELECT pubkey_hex FROM miner_header_keys WHERE miner_id = ?",
                ("attest-runtime-miner",),
            ).fetchone()
            audit = conn.execute(
                """SELECT action, actor, pubkey_hex
                   FROM miner_header_key_audit
                   WHERE miner_id = ?""",
                ("attest-runtime-miner",),
            ).fetchone()

        self.assertEqual(active, ("a" * 64,))
        self.assertEqual(audit, ("registered", "attest_auto_enroll", "a" * 64))


if __name__ == "__main__":
    unittest.main()
