# SPDX-License-Identifier: MIT
import importlib.util
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from nacl.signing import SigningKey


NODE_DIR = Path(__file__).resolve().parents[1]


def _load_module(name):
    spec = importlib.util.spec_from_file_location(name, NODE_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit_event_log = _load_module("audit_event_log")
beacon_anchor = _load_module("beacon_anchor")


def _make_temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return path


def _signed_beacon_envelope():
    signing_key = SigningKey.generate()
    pubkey = bytes(signing_key.verify_key)
    envelope = {
        "agent_id": beacon_anchor._agent_id_from_pubkey(pubkey),
        "kind": "heartbeat",
        "nonce": "audit-nonce-123456",
        "pubkey": pubkey.hex(),
        "status": "alive",
        "ts": 1234567890,
    }
    envelope["sig"] = signing_key.sign(
        beacon_anchor._canonical_signing_payload(envelope)
    ).signature.hex()
    return envelope


class AuditEventLogTests(unittest.TestCase):
    def test_append_audit_event_creates_hash_chained_events(self):
        db_path = _make_temp_db()
        try:
            with closing(sqlite3.connect(db_path)) as conn:
                first = audit_event_log.append_audit_event(
                    conn,
                    event_type="miner_attestation_recorded",
                    subject_type="miner",
                    subject_id="miner-a",
                    actor_id="miner-a",
                    epoch=7,
                    ts=100,
                    payload={"fingerprint_passed": True},
                )
                second = audit_event_log.append_audit_event(
                    conn,
                    event_type="miner_epoch_enrolled",
                    subject_type="miner",
                    subject_id="miner-a",
                    actor_id="miner-a",
                    epoch=7,
                    ts=101,
                    payload={"weight_units": 1000},
                )
                conn.commit()

            self.assertIsNone(first["previous_event_hash"])
            self.assertEqual(second["previous_event_hash"], first["event_hash"])
            with closing(sqlite3.connect(db_path)) as conn:
                rows = conn.execute(
                    "SELECT event_type, subject_id, payload_json FROM audit_events ORDER BY id"
                ).fetchall()
            self.assertEqual(
                [row[0] for row in rows],
                ["miner_attestation_recorded", "miner_epoch_enrolled"],
            )
            self.assertEqual(rows[0][1], "miner-a")
            self.assertEqual(json.loads(rows[1][2]), {"weight_units": 1000})
        finally:
            os.unlink(db_path)

    def test_beacon_store_envelope_records_audit_event(self):
        db_path = _make_temp_db()
        try:
            beacon_anchor.init_beacon_table(db_path)
            envelope = _signed_beacon_envelope()

            result = beacon_anchor.store_envelope(envelope, db_path)

            self.assertTrue(result["ok"])
            with closing(sqlite3.connect(db_path)) as conn:
                row = conn.execute(
                    "SELECT event_type, subject_type, subject_id, payload_json "
                    "FROM audit_events"
                ).fetchone()
            self.assertEqual(row[0], "beacon_envelope_stored")
            self.assertEqual(row[1], "beacon_agent")
            self.assertEqual(row[2], envelope["agent_id"])
            self.assertEqual(json.loads(row[3])["payload_hash"], result["payload_hash"])
        finally:
            os.unlink(db_path)


if __name__ == "__main__":
    unittest.main()
