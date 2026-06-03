# SPDX-License-Identifier: MIT
import importlib.util
import os
import sqlite3
import tempfile
import unittest
from hashlib import blake2b
from pathlib import Path
from copy import deepcopy
from typing import Optional

from nacl.signing import SigningKey


MODULE_PATH = Path(__file__).resolve().parents[1] / "beacon_anchor.py"
SPEC = importlib.util.spec_from_file_location("beacon_anchor", MODULE_PATH)
beacon_anchor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(beacon_anchor)


def _make_temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return path


def _build_signed_envelope(
    agent_id: Optional[str] = None,
    signing_key: Optional[SigningKey] = None,
    health: Optional[dict] = None,
    extra_fields: Optional[dict] = None,
):
    signing_key = signing_key or SigningKey.generate()
    pubkey_bytes = bytes(signing_key.verify_key)
    derived_agent_id = beacon_anchor._agent_id_from_pubkey(pubkey_bytes)
    envelope = {
        "agent_id": agent_id or derived_agent_id,
        "kind": "heartbeat",
        "v": 2,
        "nonce": "beacon-nonce-123456",
        "pubkey": pubkey_bytes.hex(),
        "name": "agent-alpha",
        "status": "alive",
        "beat_count": 1,
        "uptime_s": 60,
        "ts": 1234567890,
    }
    if health:
        envelope["health"] = health
    if extra_fields:
        envelope.update(extra_fields)
    message = beacon_anchor._canonical_signing_payload(envelope)
    envelope["sig"] = signing_key.sign(message).signature.hex()
    return envelope, derived_agent_id


class BeaconAnchorSignatureTests(unittest.TestCase):
    def test_store_envelope_rejects_invalid_signature(self):
        db_path = _make_temp_db()
        try:
            beacon_anchor.init_beacon_table(db_path)
            envelope, _ = _build_signed_envelope()
            envelope["sig"] = "00" * 64

            result = beacon_anchor.store_envelope(envelope, db_path)

            self.assertEqual(result, {"ok": False, "error": "invalid_signature"})
            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM beacon_envelopes").fetchone()[0]
            self.assertEqual(count, 0)
        finally:
            os.unlink(db_path)

    def test_store_envelope_rejects_agent_id_pubkey_mismatch(self):
        db_path = _make_temp_db()
        try:
            beacon_anchor.init_beacon_table(db_path)
            envelope, _ = _build_signed_envelope(agent_id="bcn_deadbeefcafe")

            result = beacon_anchor.store_envelope(envelope, db_path)

            self.assertEqual(result, {"ok": False, "error": "agent_id_pubkey_mismatch"})
        finally:
            os.unlink(db_path)

    def test_store_envelope_accepts_valid_signature_and_affects_digest(self):
        db_path = _make_temp_db()
        try:
            beacon_anchor.init_beacon_table(db_path)
            envelope, agent_id = _build_signed_envelope()

            result = beacon_anchor.store_envelope(envelope, db_path)
            digest = beacon_anchor.compute_beacon_digest(db_path)

            self.assertTrue(result["ok"])
            self.assertEqual(digest["count"], 1)
            with sqlite3.connect(db_path) as conn:
                row = conn.execute(
                    "SELECT agent_id, kind, nonce, payload_hash FROM beacon_envelopes"
                ).fetchone()
            self.assertEqual(row[0], agent_id)
            self.assertEqual(row[1], "heartbeat")
            self.assertEqual(row[2], "beacon-nonce-123456")
            self.assertEqual(row[3], beacon_anchor.hash_envelope(envelope))
            self.assertEqual(result["payload_hash_version"], beacon_anchor.CURRENT_PAYLOAD_HASH_VERSION)
        finally:
            os.unlink(db_path)

    def test_hash_ignores_extra_unsigned_metadata(self):
        envelope, _ = _build_signed_envelope()
        envelope_with_metadata = deepcopy(envelope)
        envelope_with_metadata["_beacon_version"] = 999

        self.assertEqual(
            beacon_anchor.hash_envelope(envelope),
            beacon_anchor.hash_envelope(envelope_with_metadata),
        )
        sig_ok, sig_err = beacon_anchor.verify_envelope_signature(envelope_with_metadata)
        self.assertTrue(sig_ok, sig_err)

    def test_hash_changes_when_signed_field_changes(self):
        signing_key = SigningKey.generate()
        envelope, _ = _build_signed_envelope(signing_key=signing_key)
        changed_envelope, _ = _build_signed_envelope(
            signing_key=signing_key,
            extra_fields={"status": "degraded"},
        )

        self.assertNotEqual(
            beacon_anchor.hash_envelope(envelope),
            beacon_anchor.hash_envelope(changed_envelope),
        )

    def test_init_beacon_table_preserves_legacy_payload_hashes_as_version_one(self):
        db_path = _make_temp_db()
        try:
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE beacon_envelopes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        agent_id TEXT NOT NULL,
                        kind TEXT NOT NULL,
                        nonce TEXT UNIQUE NOT NULL,
                        sig TEXT NOT NULL,
                        pubkey TEXT NOT NULL,
                        payload_hash TEXT NOT NULL,
                        anchored INTEGER DEFAULT 0,
                        created_at INTEGER NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO beacon_envelopes
                    (agent_id, kind, nonce, sig, pubkey, payload_hash, anchored, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 0, ?)
                    """,
                    (
                        "bcn_legacy123456",
                        "heartbeat",
                        "legacy-nonce",
                        "ab" * 64,
                        "cd" * 32,
                        "legacy-hash",
                        1234567890,
                    ),
                )
                conn.commit()

            beacon_anchor.init_beacon_table(db_path)

            with sqlite3.connect(db_path) as conn:
                version = conn.execute(
                    "SELECT payload_hash_version FROM beacon_envelopes WHERE nonce = ?",
                    ("legacy-nonce",),
                ).fetchone()[0]
            self.assertEqual(version, beacon_anchor.LEGACY_PAYLOAD_HASH_VERSION)
        finally:
            os.unlink(db_path)

    def test_compute_beacon_digest_preserves_legacy_digest_for_legacy_only_rows(self):
        db_path = _make_temp_db()
        try:
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE beacon_envelopes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        agent_id TEXT NOT NULL,
                        kind TEXT NOT NULL,
                        nonce TEXT UNIQUE NOT NULL,
                        sig TEXT NOT NULL,
                        pubkey TEXT NOT NULL,
                        payload_hash TEXT NOT NULL,
                        anchored INTEGER DEFAULT 0,
                        created_at INTEGER NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO beacon_envelopes
                    (agent_id, kind, nonce, sig, pubkey, payload_hash, anchored, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 0, ?)
                    """,
                    (
                        "bcn_legacy123456",
                        "heartbeat",
                        "legacy-nonce",
                        "ab" * 64,
                        "cd" * 32,
                        "legacy-hash",
                        1234567890,
                    ),
                )
                conn.commit()

            beacon_anchor.init_beacon_table(db_path)
            digest = beacon_anchor.compute_beacon_digest(db_path)

            self.assertEqual(
                digest["digest"],
                blake2b(b"legacy-hash", digest_size=32).hexdigest(),
            )
            self.assertEqual(digest["payload_hash_versions"], [1])
            self.assertFalse(digest["mixed_payload_hash_versions"])
        finally:
            os.unlink(db_path)

    def test_compute_beacon_digest_reports_mixed_hash_versions(self):
        db_path = _make_temp_db()
        try:
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE beacon_envelopes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        agent_id TEXT NOT NULL,
                        kind TEXT NOT NULL,
                        nonce TEXT UNIQUE NOT NULL,
                        sig TEXT NOT NULL,
                        pubkey TEXT NOT NULL,
                        payload_hash TEXT NOT NULL,
                        anchored INTEGER DEFAULT 0,
                        created_at INTEGER NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO beacon_envelopes
                    (agent_id, kind, nonce, sig, pubkey, payload_hash, anchored, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 0, ?)
                    """,
                    (
                        "bcn_legacy123456",
                        "heartbeat",
                        "legacy-nonce",
                        "ab" * 64,
                        "cd" * 32,
                        "legacy-hash",
                        1234567890,
                    ),
                )
                conn.commit()

            beacon_anchor.init_beacon_table(db_path)
            envelope, _ = _build_signed_envelope(extra_fields={"nonce": "fresh-nonce"})
            result = beacon_anchor.store_envelope(envelope, db_path)
            self.assertTrue(result["ok"])

            digest = beacon_anchor.compute_beacon_digest(db_path)

            self.assertEqual(digest["payload_hash_versions"], [1, 2])
            self.assertTrue(digest["mixed_payload_hash_versions"])
            self.assertEqual(digest["count"], 2)
        finally:
            os.unlink(db_path)

    def test_mark_anchored_handles_empty_and_partial_id_lists(self):
        db_path = _make_temp_db()
        try:
            beacon_anchor.init_beacon_table(db_path)
            target_envelope, _ = _build_signed_envelope(extra_fields={"nonce": "target-nonce"})
            pending_envelope, _ = _build_signed_envelope(extra_fields={"nonce": "pending-nonce"})

            target = beacon_anchor.store_envelope(target_envelope, db_path)
            pending = beacon_anchor.store_envelope(pending_envelope, db_path)
            self.assertTrue(target["ok"])
            self.assertTrue(pending["ok"])

            beacon_anchor.mark_anchored([], db_path)
            with sqlite3.connect(db_path) as conn:
                rows = dict(
                    conn.execute(
                        "SELECT id, anchored FROM beacon_envelopes ORDER BY id ASC"
                    ).fetchall()
                )
            self.assertEqual(rows[target["id"]], 0)
            self.assertEqual(rows[pending["id"]], 0)

            beacon_anchor.mark_anchored([target["id"], pending["id"] + 999], db_path)
            with sqlite3.connect(db_path) as conn:
                rows = dict(
                    conn.execute(
                        "SELECT id, anchored FROM beacon_envelopes ORDER BY id ASC"
                    ).fetchall()
                )

            self.assertEqual(rows[target["id"]], 1)
            self.assertEqual(rows[pending["id"]], 0)
            digest = beacon_anchor.compute_beacon_digest(db_path)
            self.assertEqual(digest["ids"], [pending["id"]])
            self.assertEqual(digest["count"], 1)
        finally:
            os.unlink(db_path)


if __name__ == "__main__":
    unittest.main()
