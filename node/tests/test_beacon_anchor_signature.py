import importlib.util
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
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


def _build_signed_envelope(agent_id: Optional[str] = None):
    signing_key = SigningKey.generate()
    pubkey_bytes = bytes(signing_key.verify_key)
    derived_agent_id = beacon_anchor._agent_id_from_pubkey(pubkey_bytes)
    envelope = {
        "agent_id": agent_id or derived_agent_id,
        "kind": "heartbeat",
        "nonce": "beacon-nonce-123456",
        "pubkey": pubkey_bytes.hex(),
        "payload": {"status": "alive", "ts": 1234567890},
    }
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
        finally:
            os.unlink(db_path)


if __name__ == "__main__":
    unittest.main()
