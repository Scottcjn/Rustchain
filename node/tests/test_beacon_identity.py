"""
Unit tests for beacon_identity.py — TOFU key management with TTL, rotation, and revocation.
Covers: agent_id_from_pubkey, learn_key_from_envelope, is_key_expired,
        expire_old_keys, revoke_key, rotate_key, list_keys, get_key_info.

Bounty: Scottcjn/rustchain-bounties#1589 (2 RTC per untested function)
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import time
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_path():
    """Temporary SQLite DB for each test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


@pytest.fixture
def init_db(db_path):
    """Import and initialise the beacon_identity module with the temp DB."""
    # Patch env vars before importing
    with patch.dict(os.environ, {
        "BEACON_DB_PATH": db_path,
        "BEACON_KEY_TTL": "86400",  # 1 day for predictable TTL tests
    }):
        import importlib
        import beacon_identity as bi
        importlib.reload(bi)
        bi.init_identity_tables(db_path)
        return bi


# ---------------------------------------------------------------------------
# agent_id_from_pubkey
# ---------------------------------------------------------------------------

class TestAgentIdFromPubkey:
    def test_derives_bcn_prefix(self, init_db):
        bi = init_db
        pubkey = b"\x00" * 32
        agent_id = bi.agent_id_from_pubkey(pubkey)
        assert agent_id.startswith("bcn_")

    def test_derives_12_hex_chars(self, init_db):
        bi = init_db
        pubkey = b"\x00" * 32
        agent_id = bi.agent_id_from_pubkey(pubkey)
        hex_part = agent_id[4:]  # strip "bcn_"
        assert len(hex_part) == 12
        assert all(c in "0123456789abcdef" for c in hex_part)

    def test_deterministic(self, init_db):
        bi = init_db
        pubkey = b"\xab\xcd\xef" * 11 + b"\x00"
        id1 = bi.agent_id_from_pubkey(pubkey)
        id2 = bi.agent_id_from_pubkey(pubkey)
        assert id1 == id2

    def test_different_pubkeys_different_ids(self, init_db):
        bi = init_db
        id1 = bi.agent_id_from_pubkey(b"\x00" * 32)
        id2 = bi.agent_id_from_pubkey(b"\xff" * 32)
        assert id1 != id2


# ---------------------------------------------------------------------------
# init_identity_tables
# ---------------------------------------------------------------------------

class TestInitIdentityTables:
    def test_creates_tables_without_error(self, db_path):
        import beacon_identity as bi
        bi.init_identity_tables(db_path)  # should not raise

        # Verify tables exist
        with sqlite3.connect(db_path) as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = [t[0] for t in tables]
            assert "beacon_known_keys" in table_names
            assert "beacon_key_rotation_log" in table_names

    def test_idempotent(self, db_path):
        import beacon_identity as bi
        bi.init_identity_tables(db_path)
        bi.init_identity_tables(db_path)  # should not raise


# ---------------------------------------------------------------------------
# learn_key_from_envelope — TOFU
# ---------------------------------------------------------------------------

class TestLearnKeyFromEnvelope:
    def test_learns_new_key(self, init_db, db_path):
        bi = init_db
        pubkey_bytes = b"\x01" * 32
        agent_id = bi.agent_id_from_pubkey(pubkey_bytes)

        envelope = {
            "agent_id": agent_id,
            "pubkey": pubkey_bytes.hex(),
        }
        accepted, reason = bi.learn_key_from_envelope(envelope, db_path)

        assert accepted is True
        assert reason == "key_learned"

        # Verify stored
        rec = bi.load_key(agent_id, db_path)
        assert rec is not None
        assert rec["pubkey_hex"] == pubkey_bytes.hex()
        assert rec["rotation_count"] == 0
        assert rec["revoked"] == 0

    def test_updates_last_seen_on_repeat(self, init_db, db_path):
        bi = init_db
        pubkey_bytes = b"\x02" * 32
        agent_id = bi.agent_id_from_pubkey(pubkey_bytes)

        envelope = {"agent_id": agent_id, "pubkey": pubkey_bytes.hex()}
        bi.learn_key_from_envelope(envelope, db_path)

        time.sleep(0.01)
        bi.learn_key_from_envelope(envelope, db_path)

        rec = bi.load_key(agent_id, db_path)
        assert rec["rotation_count"] == 0
        assert rec["last_seen"] >= rec["first_seen"]

    def test_rejects_missing_agent_id(self, init_db, db_path):
        bi = init_db
        envelope = {"pubkey": "00" * 32}
        accepted, reason = bi.learn_key_from_envelope(envelope, db_path)
        assert accepted is False
        assert reason == "missing_agent_id_or_pubkey"

    def test_rejects_missing_pubkey(self, init_db, db_path):
        bi = init_db
        envelope = {"agent_id": "bcn_000000000000"}
        accepted, reason = bi.learn_key_from_envelope(envelope, db_path)
        assert accepted is False
        assert reason == "missing_agent_id_or_pubkey"

    def test_rejects_invalid_pubkey_encoding(self, init_db, db_path):
        bi = init_db
        envelope = {"agent_id": "bcn_000000000000", "pubkey": "not-hex"}
        accepted, reason = bi.learn_key_from_envelope(envelope, db_path)
        assert accepted is False
        assert reason == "invalid_pubkey_encoding"

    def test_rejects_mismatched_agent_id(self, init_db, db_path):
        bi = init_db
        wrong_agent = "bcn_000000000000"
        envelope = {"agent_id": wrong_agent, "pubkey": "01" * 32}
        accepted, reason = bi.learn_key_from_envelope(envelope, db_path)
        assert accepted is False
        assert reason == "agent_id_pubkey_mismatch"

    def test_rejects_revoked_key(self, init_db, db_path):
        bi = init_db
        pubkey_bytes = b"\x03" * 32
        agent_id = bi.agent_id_from_pubkey(pubkey_bytes)

        # Learn first
        envelope = {"agent_id": agent_id, "pubkey": pubkey_bytes.hex()}
        bi.learn_key_from_envelope(envelope, db_path)

        # Revoke
        bi.revoke_key(agent_id, "test revocation", db_path)

        # Try to re-learn
        bi.learn_key_from_envelope(envelope, db_path)
        rec = bi.load_key(agent_id, db_path)
        assert rec["revoked"] == 1


# ---------------------------------------------------------------------------
# is_key_expired
# ---------------------------------------------------------------------------

class TestIsKeyExpired:
    def test_unknown_key_is_expired(self, init_db, db_path):
        bi = init_db
        assert bi.is_key_expired("bcn_neverexisted", db_path=db_path) is True

    def test_revoked_key_is_expired(self, init_db, db_path):
        bi = init_db
        pubkey_bytes = b"\x04" * 32
        agent_id = bi.agent_id_from_pubkey(pubkey_bytes)
        envelope = {"agent_id": agent_id, "pubkey": pubkey_bytes.hex()}
        bi.learn_key_from_envelope(envelope, db_path)
        bi.revoke_key(agent_id, db_path=db_path)

        assert bi.is_key_expired(agent_id, db_path=db_path) is True

    def test_fresh_key_not_expired(self, init_db, db_path):
        bi = init_db
        pubkey_bytes = b"\x05" * 32
        agent_id = bi.agent_id_from_pubkey(pubkey_bytes)
        envelope = {"agent_id": agent_id, "pubkey": pubkey_bytes.hex()}
        bi.learn_key_from_envelope(envelope, db_path)

        assert bi.is_key_expired(agent_id, ttl=86400, db_path=db_path) is False

    def test_old_key_expired(self, init_db, db_path):
        bi = init_db
        pubkey_bytes = b"\x06" * 32
        agent_id = bi.agent_id_from_pubkey(pubkey_bytes)
        envelope = {"agent_id": agent_id, "pubkey": pubkey_bytes.hex()}
        bi.learn_key_from_envelope(envelope, db_path)

        # Manually set last_seen to 2 days ago
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "UPDATE beacon_known_keys SET last_seen = ? WHERE agent_id = ?",
                (time.time() - 2 * 86400, agent_id),
            )
            conn.commit()

        assert bi.is_key_expired(agent_id, ttl=86400, db_path=db_path) is True


# ---------------------------------------------------------------------------
# expire_old_keys
# ---------------------------------------------------------------------------

class TestExpireOldKeys:
    def test_dry_run_returns_expired_ids(self, init_db, db_path):
        bi = init_db
        pubkey_bytes = b"\x07" * 32
        agent_id = bi.agent_id_from_pubkey(pubkey_bytes)
        envelope = {"agent_id": agent_id, "pubkey": pubkey_bytes.hex()}
        bi.learn_key_from_envelope(envelope, db_path)

        # Age the key
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "UPDATE beacon_known_keys SET last_seen = ? WHERE agent_id = ?",
                (time.time() - 2 * 86400, agent_id),
            )
            conn.commit()

        expired = bi.expire_old_keys(ttl=86400, dry_run=True, db_path=db_path)
        assert agent_id in expired

        # Verify not actually deleted
        rec = bi.load_key(agent_id, db_path)
        assert rec is not None

    def test_actual_delete_removes_key(self, init_db, db_path):
        bi = init_db
        pubkey_bytes = b"\x08" * 32
        agent_id = bi.agent_id_from_pubkey(pubkey_bytes)
        envelope = {"agent_id": agent_id, "pubkey": pubkey_bytes.hex()}
        bi.learn_key_from_envelope(envelope, db_path)

        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "UPDATE beacon_known_keys SET last_seen = ? WHERE agent_id = ?",
                (time.time() - 2 * 86400, agent_id),
            )
            conn.commit()

        expired = bi.expire_old_keys(ttl=86400, dry_run=False, db_path=db_path)
        assert agent_id in expired

        rec = bi.load_key(agent_id, db_path)
        assert rec is None


# ---------------------------------------------------------------------------
# revoke_key
# ---------------------------------------------------------------------------

class TestRevokeKey:
    def test_revokes_known_key(self, init_db, db_path):
        bi = init_db
        pubkey_bytes = b"\x09" * 32
        agent_id = bi.agent_id_from_pubkey(pubkey_bytes)
        envelope = {"agent_id": agent_id, "pubkey": pubkey_bytes.hex()}
        bi.learn_key_from_envelope(envelope, db_path)

        success, msg = bi.revoke_key(agent_id, "testing", db_path)

        assert success is True
        rec = bi.load_key(agent_id, db_path)
        assert rec["revoked"] == 1
        assert rec["revoked_reason"] == "testing"

    def test_rejects_unknown_agent(self, init_db, db_path):
        bi = init_db
        success, msg = bi.revoke_key("bcn_neverexisted", db_path=db_path)
        assert success is False
        assert "not found" in msg

    def test_rejects_already_revoked(self, init_db, db_path):
        bi = init_db
        pubkey_bytes = b"\x0a" * 32
        agent_id = bi.agent_id_from_pubkey(pubkey_bytes)
        envelope = {"agent_id": agent_id, "pubkey": pubkey_bytes.hex()}
        bi.learn_key_from_envelope(envelope, db_path)
        bi.revoke_key(agent_id, db_path=db_path)

        success, msg = bi.revoke_key(agent_id, db_path=db_path)
        assert success is False
        assert "already revoked" in msg


# ---------------------------------------------------------------------------
# rotate_key (without Ed25519 — mocked)
# ---------------------------------------------------------------------------

class TestRotateKey:
    def test_rejects_unknown_agent(self, init_db, db_path):
        bi = init_db
        success, msg = bi.rotate_key(
            "bcn_neverexisted", new_pubkey_hex="ff" * 32,
            signature_hex="00" * 64, db_path=db_path
        )
        assert success is False
        assert "not found" in msg

    def test_rejects_revoked_key(self, init_db, db_path):
        bi = init_db
        pubkey_bytes = b"\x0b" * 32
        agent_id = bi.agent_id_from_pubkey(pubkey_bytes)
        envelope = {"agent_id": agent_id, "pubkey": pubkey_bytes.hex()}
        bi.learn_key_from_envelope(envelope, db_path)
        bi.revoke_key(agent_id, db_path=db_path)

        success, msg = bi.rotate_key(
            agent_id, new_pubkey_hex="ff" * 32,
            signature_hex="00" * 64, db_path=db_path
        )
        assert success is False
        assert "revoked" in msg

    def test_invalid_signature_rejected(self, init_db, db_path):
        bi = init_db
        pubkey_bytes = b"\x0c" * 32
        agent_id = bi.agent_id_from_pubkey(pubkey_bytes)
        envelope = {"agent_id": agent_id, "pubkey": pubkey_bytes.hex()}
        bi.learn_key_from_envelope(envelope, db_path)

        # Without valid Ed25519, any signature fails
        success, msg = bi.rotate_key(
            agent_id, new_pubkey_hex="ff" * 32,
            signature_hex="00" * 64, db_path=db_path
        )
        assert success is False
        assert "signature" in msg.lower()


# ---------------------------------------------------------------------------
# list_keys
# ---------------------------------------------------------------------------

class TestListKeys:
    def test_empty_when_no_keys(self, init_db, db_path):
        bi = init_db
        keys = bi.list_keys(db_path=db_path)
        assert keys == []

    def test_includes_learned_key(self, init_db, db_path):
        bi = init_db
        pubkey_bytes = b"\x0d" * 32
        agent_id = bi.agent_id_from_pubkey(pubkey_bytes)
        envelope = {"agent_id": agent_id, "pubkey": pubkey_bytes.hex()}
        bi.learn_key_from_envelope(envelope, db_path)

        keys = bi.list_keys(db_path=db_path)
        assert any(k["agent_id"] == agent_id for k in keys)

    def test_excludes_revoked_when_flag_false(self, init_db, db_path):
        bi = init_db
        pubkey_bytes = b"\x0e" * 32
        agent_id = bi.agent_id_from_pubkey(pubkey_bytes)
        envelope = {"agent_id": agent_id, "pubkey": pubkey_bytes.hex()}
        bi.learn_key_from_envelope(envelope, db_path)
        bi.revoke_key(agent_id, db_path=db_path)

        all_keys = bi.list_keys(include_revoked=True, db_path=db_path)
        filtered = bi.list_keys(include_revoked=False, db_path=db_path)
        assert any(k["agent_id"] == agent_id for k in all_keys)
        assert not any(k["agent_id"] == agent_id for k in filtered)

    def test_enriched_fields_present(self, init_db, db_path):
        bi = init_db
        pubkey_bytes = b"\x0f" * 32
        agent_id = bi.agent_id_from_pubkey(pubkey_bytes)
        envelope = {"agent_id": agent_id, "pubkey": pubkey_bytes.hex()}
        bi.learn_key_from_envelope(envelope, db_path)

        keys = bi.list_keys(db_path=db_path)
        key = next(k for k in keys if k["agent_id"] == agent_id)
        assert "is_revoked" in key
        assert "is_expired" in key
        assert "age_days" in key
        assert "rotation_count" in key


# ---------------------------------------------------------------------------
# get_key_info
# ---------------------------------------------------------------------------

class TestGetKeyInfo:
    def test_returns_none_for_unknown(self, init_db, db_path):
        bi = init_db
        info = bi.get_key_info("bcn_neverexisted", db_path=db_path)
        assert info is None

    def test_returns_enriched_info(self, init_db, db_path):
        bi = init_db
        pubkey_bytes = b"\x10" * 32
        agent_id = bi.agent_id_from_pubkey(pubkey_bytes)
        envelope = {"agent_id": agent_id, "pubkey": pubkey_bytes.hex()}
        bi.learn_key_from_envelope(envelope, db_path)

        info = bi.get_key_info(agent_id, db_path=db_path)
        assert info is not None
        assert info["agent_id"] == agent_id
        assert info["pubkey_hex"] == pubkey_bytes.hex()
        assert info["is_revoked"] is False
        assert info["is_expired"] is False
        assert "first_seen" in info
        assert "last_seen" in info
        assert "age_days" in info
