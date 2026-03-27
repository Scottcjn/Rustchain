"""
Tests for Beacon TOFU key revocation, rotation, and TTL expiration.

Covers:
  - Key learning (TOFU)
  - TTL-based expiration
  - Key revocation
  - Key rotation with old-key signature
  - Rotation log
  - CLI dispatch

Closes: Scottcjn/rustchain-bounties#392
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Optional

# ── path setup ──────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from node.beacon_identity import (
    DEFAULT_KEY_TTL,
    agent_id_from_pubkey,
    expire_old_keys,
    get_key_info,
    init_identity_tables,
    is_key_expired,
    learn_key_from_envelope,
    list_keys,
    revoke_key,
    rotate_key,
)
from node.beacon_keys_cli import build_parser, dispatch

# Optional: real Ed25519 crypto for signature-verification tests
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    _CRYPTO = True
except ImportError:
    _CRYPTO = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _agent_id(pubkey_bytes: bytes) -> str:
    return "bcn_" + hashlib.sha256(pubkey_bytes).hexdigest()[:12]


def _make_pubkey_bytes(seed: int) -> bytes:
    """Deterministic 32-byte fake public key from an integer seed."""
    return hashlib.sha256(seed.to_bytes(4, "big")).digest()


def _make_envelope(seed: int) -> dict:
    pk = _make_pubkey_bytes(seed)
    agent_id = _agent_id(pk)
    return {
        "agent_id": agent_id,
        "pubkey": pk.hex(),
        "kind": "heartbeat",
        "nonce": f"test-{seed}-{time.time()}",
        "ts": time.time(),
    }


class _TempDB:
    """Context manager that gives a fresh temp SQLite DB path."""

    def __enter__(self) -> str:
        self._tf = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tf.close()
        self.path = self._tf.name
        init_identity_tables(self.path)
        return self.path

    def __exit__(self, *_):
        try:
            os.unlink(self.path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# TOFU learning tests
# ---------------------------------------------------------------------------

class TestTOFULearning(unittest.TestCase):

    def test_learn_new_key(self):
        with _TempDB() as db:
            env = _make_envelope(1)
            ok, reason = learn_key_from_envelope(env, db_path=db)
            self.assertTrue(ok)
            self.assertEqual(reason, "key_learned")

            info = get_key_info(env["agent_id"], db_path=db)
            self.assertIsNotNone(info)
            self.assertEqual(info["pubkey_hex"], env["pubkey"])
            self.assertEqual(info["rotation_count"], 0)
            self.assertFalse(info["is_revoked"])

    def test_learn_same_key_updates_last_seen(self):
        with _TempDB() as db:
            env = _make_envelope(2)
            learn_key_from_envelope(env, db_path=db)
            first = get_key_info(env["agent_id"], db_path=db)["last_seen"]

            time.sleep(0.05)
            ok, reason = learn_key_from_envelope(env, db_path=db)
            self.assertTrue(ok)
            self.assertEqual(reason, "key_updated")

            second = get_key_info(env["agent_id"], db_path=db)["last_seen"]
            self.assertGreater(second, first)

    def test_reject_mismatched_agent_id(self):
        with _TempDB() as db:
            env = _make_envelope(3)
            env["agent_id"] = "bcn_wrongid0000"  # doesn't match pubkey
            ok, reason = learn_key_from_envelope(env, db_path=db)
            self.assertFalse(ok)
            self.assertEqual(reason, "agent_id_pubkey_mismatch")

    def test_reject_missing_fields(self):
        with _TempDB() as db:
            ok, reason = learn_key_from_envelope({}, db_path=db)
            self.assertFalse(ok)
            self.assertIn("missing", reason)

    def test_reject_revoked_key_in_tofu(self):
        with _TempDB() as db:
            env = _make_envelope(4)
            learn_key_from_envelope(env, db_path=db)
            revoke_key(env["agent_id"], reason="test", db_path=db)

            ok, reason = learn_key_from_envelope(env, db_path=db)
            self.assertFalse(ok)
            self.assertEqual(reason, "key_revoked")


# ---------------------------------------------------------------------------
# TTL / expiration tests
# ---------------------------------------------------------------------------

class TestKeyExpiration(unittest.TestCase):

    def test_fresh_key_not_expired(self):
        with _TempDB() as db:
            env = _make_envelope(10)
            learn_key_from_envelope(env, db_path=db)
            self.assertFalse(is_key_expired(env["agent_id"], ttl=DEFAULT_KEY_TTL, db_path=db))

    def test_old_key_is_expired(self):
        with _TempDB() as db:
            env = _make_envelope(11)
            learn_key_from_envelope(env, db_path=db)

            # Backdating last_seen past TTL
            cutoff = time.time() - DEFAULT_KEY_TTL - 100
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "UPDATE beacon_known_keys SET last_seen = ? WHERE agent_id = ?",
                    (cutoff, env["agent_id"]),
                )
                conn.commit()

            self.assertTrue(is_key_expired(env["agent_id"], ttl=DEFAULT_KEY_TTL, db_path=db))

    def test_revoked_key_counts_as_expired(self):
        with _TempDB() as db:
            env = _make_envelope(12)
            learn_key_from_envelope(env, db_path=db)
            revoke_key(env["agent_id"], db_path=db)
            self.assertTrue(is_key_expired(env["agent_id"], db_path=db))

    def test_expire_old_keys_dry_run(self):
        with _TempDB() as db:
            env = _make_envelope(13)
            learn_key_from_envelope(env, db_path=db)
            cutoff = time.time() - DEFAULT_KEY_TTL - 100
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "UPDATE beacon_known_keys SET last_seen = ? WHERE agent_id = ?",
                    (cutoff, env["agent_id"]),
                )
                conn.commit()

            removed = expire_old_keys(dry_run=True, db_path=db)
            self.assertIn(env["agent_id"], removed)

            # Key should still be present (dry run)
            info = get_key_info(env["agent_id"], db_path=db)
            self.assertIsNotNone(info)

    def test_expire_old_keys_removes(self):
        with _TempDB() as db:
            env = _make_envelope(14)
            learn_key_from_envelope(env, db_path=db)
            cutoff = time.time() - DEFAULT_KEY_TTL - 100
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "UPDATE beacon_known_keys SET last_seen = ? WHERE agent_id = ?",
                    (cutoff, env["agent_id"]),
                )
                conn.commit()

            removed = expire_old_keys(dry_run=False, db_path=db)
            self.assertIn(env["agent_id"], removed)
            self.assertIsNone(get_key_info(env["agent_id"], db_path=db))

    def test_fresh_key_not_removed_by_expire(self):
        with _TempDB() as db:
            env = _make_envelope(15)
            learn_key_from_envelope(env, db_path=db)

            removed = expire_old_keys(dry_run=False, db_path=db)
            self.assertNotIn(env["agent_id"], removed)
            self.assertIsNotNone(get_key_info(env["agent_id"], db_path=db))


# ---------------------------------------------------------------------------
# Revocation tests
# ---------------------------------------------------------------------------

class TestRevocation(unittest.TestCase):

    def test_revoke_known_key(self):
        with _TempDB() as db:
            env = _make_envelope(20)
            learn_key_from_envelope(env, db_path=db)

            ok, msg = revoke_key(env["agent_id"], reason="compromised", db_path=db)
            self.assertTrue(ok)
            self.assertIn("revoked", msg)

            info = get_key_info(env["agent_id"], db_path=db)
            self.assertTrue(info["is_revoked"])
            self.assertIsNotNone(info["revoked_at"])
            self.assertEqual(info["revoked_reason"], "compromised")

    def test_revoke_unknown_key(self):
        with _TempDB() as db:
            ok, msg = revoke_key("bcn_doesnotexist", db_path=db)
            self.assertFalse(ok)
            self.assertIn("not found", msg)

    def test_revoke_already_revoked(self):
        with _TempDB() as db:
            env = _make_envelope(21)
            learn_key_from_envelope(env, db_path=db)
            revoke_key(env["agent_id"], db_path=db)
            ok, msg = revoke_key(env["agent_id"], db_path=db)
            self.assertFalse(ok)
            self.assertIn("already revoked", msg)

    def test_revoked_key_excluded_from_list(self):
        with _TempDB() as db:
            env = _make_envelope(22)
            learn_key_from_envelope(env, db_path=db)
            revoke_key(env["agent_id"], db_path=db)

            active = list_keys(include_revoked=False, db_path=db)
            agent_ids = [k["agent_id"] for k in active]
            self.assertNotIn(env["agent_id"], agent_ids)

    def test_revoked_key_included_when_requested(self):
        with _TempDB() as db:
            env = _make_envelope(23)
            learn_key_from_envelope(env, db_path=db)
            revoke_key(env["agent_id"], db_path=db)

            all_keys = list_keys(include_revoked=True, db_path=db)
            agent_ids = [k["agent_id"] for k in all_keys]
            self.assertIn(env["agent_id"], agent_ids)


# ---------------------------------------------------------------------------
# Rotation tests (with real Ed25519 crypto)
# ---------------------------------------------------------------------------

@unittest.skipUnless(_CRYPTO, "cryptography package not installed")
class TestKeyRotation(unittest.TestCase):

    def _gen_key(self):
        sk = Ed25519PrivateKey.generate()
        pk_bytes = sk.public_key().public_bytes_raw() if hasattr(
            sk.public_key(), "public_bytes_raw"
        ) else sk.public_key().public_bytes(
            encoding=__import__("cryptography.hazmat.primitives.serialization", fromlist=["Encoding"]).Encoding.Raw,
            format=__import__("cryptography.hazmat.primitives.serialization", fromlist=["PublicFormat"]).PublicFormat.Raw,
        )
        return sk, pk_bytes

    def test_rotate_key_success(self):
        with _TempDB() as db:
            old_sk, old_pk = self._gen_key()
            agent_id = _agent_id(old_pk)

            # Learn old key via TOFU
            env = {"agent_id": agent_id, "pubkey": old_pk.hex(), "kind": "hello",
                   "nonce": "n1", "ts": time.time()}
            learn_key_from_envelope(env, db_path=db)

            # Generate new key
            _, new_pk = self._gen_key()
            new_pubkey_hex = new_pk.hex()

            # Sign rotation payload with old key
            payload = f"rotate:{agent_id}:{new_pubkey_hex}".encode()
            sig_bytes = old_sk.sign(payload)
            sig_hex = sig_bytes.hex()

            ok, msg = rotate_key(agent_id, new_pubkey_hex, sig_hex, db_path=db)
            self.assertTrue(ok, msg)
            self.assertIn("rotated", msg)

            info = get_key_info(agent_id, db_path=db)
            self.assertEqual(info["pubkey_hex"], new_pubkey_hex)
            self.assertEqual(info["rotation_count"], 1)
            self.assertEqual(info["previous_key"], old_pk.hex())
            self.assertFalse(info["is_revoked"])

    def test_rotate_key_invalid_signature(self):
        with _TempDB() as db:
            old_sk, old_pk = self._gen_key()
            agent_id = _agent_id(old_pk)

            env = {"agent_id": agent_id, "pubkey": old_pk.hex(), "kind": "hello",
                   "nonce": "n2", "ts": time.time()}
            learn_key_from_envelope(env, db_path=db)

            _, new_pk = self._gen_key()
            new_pubkey_hex = new_pk.hex()

            # Sign with WRONG key
            wrong_sk, _ = self._gen_key()
            payload = f"rotate:{agent_id}:{new_pubkey_hex}".encode()
            bad_sig = wrong_sk.sign(payload).hex()

            ok, msg = rotate_key(agent_id, new_pubkey_hex, bad_sig, db_path=db)
            self.assertFalse(ok)
            self.assertIn("invalid signature", msg)

    def test_rotate_revoked_key_rejected(self):
        with _TempDB() as db:
            old_sk, old_pk = self._gen_key()
            agent_id = _agent_id(old_pk)

            env = {"agent_id": agent_id, "pubkey": old_pk.hex(), "kind": "hello",
                   "nonce": "n3", "ts": time.time()}
            learn_key_from_envelope(env, db_path=db)
            revoke_key(agent_id, reason="test revoke", db_path=db)

            _, new_pk = self._gen_key()
            new_pubkey_hex = new_pk.hex()
            payload = f"rotate:{agent_id}:{new_pubkey_hex}".encode()
            sig_hex = old_sk.sign(payload).hex()

            ok, msg = rotate_key(agent_id, new_pubkey_hex, sig_hex, db_path=db)
            self.assertFalse(ok)
            self.assertIn("revoked", msg)

    def test_rotate_unknown_agent_rejected(self):
        with _TempDB() as db:
            ok, msg = rotate_key("bcn_unknown000", "ab" * 32, "cd" * 32, db_path=db)
            self.assertFalse(ok)
            self.assertIn("not found", msg)

    def test_rotation_log_written(self):
        with _TempDB() as db:
            old_sk, old_pk = self._gen_key()
            agent_id = _agent_id(old_pk)

            env = {"agent_id": agent_id, "pubkey": old_pk.hex(), "kind": "hello",
                   "nonce": "n4", "ts": time.time()}
            learn_key_from_envelope(env, db_path=db)

            _, new_pk = self._gen_key()
            new_pubkey_hex = new_pk.hex()
            payload = f"rotate:{agent_id}:{new_pubkey_hex}".encode()
            sig_hex = old_sk.sign(payload).hex()
            rotate_key(agent_id, new_pubkey_hex, sig_hex, db_path=db)

            with sqlite3.connect(db) as conn:
                conn.row_factory = sqlite3.Row
                log = conn.execute(
                    "SELECT * FROM beacon_key_rotation_log WHERE agent_id = ?", (agent_id,)
                ).fetchone()
            self.assertIsNotNone(log)
            self.assertEqual(log["old_pubkey_hex"], old_pk.hex())
            self.assertEqual(log["new_pubkey_hex"], new_pubkey_hex)
            self.assertEqual(log["rotation_num"], 1)

    def test_multiple_rotations(self):
        with _TempDB() as db:
            sk, pk = self._gen_key()
            agent_id = _agent_id(pk)

            env = {"agent_id": agent_id, "pubkey": pk.hex(), "kind": "hello",
                   "nonce": "nr0", "ts": time.time()}
            learn_key_from_envelope(env, db_path=db)

            for i in range(3):
                new_sk, new_pk = self._gen_key()
                payload = f"rotate:{agent_id}:{new_pk.hex()}".encode()
                sig = sk.sign(payload).hex()
                ok, _ = rotate_key(agent_id, new_pk.hex(), sig, db_path=db)
                self.assertTrue(ok)
                sk, pk = new_sk, new_pk  # advance key chain

            info = get_key_info(agent_id, db_path=db)
            self.assertEqual(info["rotation_count"], 3)


# ---------------------------------------------------------------------------
# CLI dispatch tests
# ---------------------------------------------------------------------------

class TestCLIDispatch(unittest.TestCase):

    def test_list_empty(self):
        with _TempDB() as db:
            rc = dispatch(["--db", db, "list"])
            self.assertEqual(rc, 0)

    def test_list_with_key(self):
        with _TempDB() as db:
            env = _make_envelope(50)
            learn_key_from_envelope(env, db_path=db)
            rc = dispatch(["--db", db, "list"])
            self.assertEqual(rc, 0)

    def test_list_json(self):
        with _TempDB() as db:
            env = _make_envelope(51)
            learn_key_from_envelope(env, db_path=db)
            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = dispatch(["--db", db, "list", "--json"])
            self.assertEqual(rc, 0)
            data = __import__("json").loads(buf.getvalue())
            self.assertIsInstance(data, list)

    def test_show_known(self):
        with _TempDB() as db:
            env = _make_envelope(52)
            learn_key_from_envelope(env, db_path=db)
            rc = dispatch(["--db", db, "show", env["agent_id"]])
            self.assertEqual(rc, 0)

    def test_show_unknown(self):
        with _TempDB() as db:
            rc = dispatch(["--db", db, "show", "bcn_missing000"])
            self.assertEqual(rc, 1)

    def test_revoke_cli(self):
        with _TempDB() as db:
            env = _make_envelope(53)
            learn_key_from_envelope(env, db_path=db)
            rc = dispatch(["--db", db, "revoke", env["agent_id"], "--reason", "cli-test"])
            self.assertEqual(rc, 0)
            info = get_key_info(env["agent_id"], db_path=db)
            self.assertTrue(info["is_revoked"])

    def test_revoke_unknown_cli(self):
        with _TempDB() as db:
            rc = dispatch(["--db", db, "revoke", "bcn_nobody0000"])
            self.assertEqual(rc, 1)

    def test_expire_dry_run_cli(self):
        with _TempDB() as db:
            env = _make_envelope(54)
            learn_key_from_envelope(env, db_path=db)
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "UPDATE beacon_known_keys SET last_seen = ? WHERE agent_id = ?",
                    (time.time() - DEFAULT_KEY_TTL - 100, env["agent_id"]),
                )
                conn.commit()
            rc = dispatch(["--db", db, "expire", "--dry-run"])
            self.assertEqual(rc, 0)
            # Not actually deleted
            self.assertIsNotNone(get_key_info(env["agent_id"], db_path=db))

    def test_expire_removes_cli(self):
        with _TempDB() as db:
            env = _make_envelope(55)
            learn_key_from_envelope(env, db_path=db)
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "UPDATE beacon_known_keys SET last_seen = ? WHERE agent_id = ?",
                    (time.time() - DEFAULT_KEY_TTL - 100, env["agent_id"]),
                )
                conn.commit()
            rc = dispatch(["--db", db, "expire"])
            self.assertEqual(rc, 0)
            self.assertIsNone(get_key_info(env["agent_id"], db_path=db))


if __name__ == "__main__":
    unittest.main()
