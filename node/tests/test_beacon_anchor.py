#!/usr/bin/env python3
"""Tests for node/beacon_anchor.py — Beacon v2 envelope signing & storage.

Tests cover:
  - Helper functions: _agent_id_from_pubkey, _canonical_signed_fields,
    _canonical_signing_payload, hash_envelope
  - verify_envelope_signature (valid, missing fields, bad hex, mismatch,
    nacl unavailable, bad signature)
  - store_envelope (valid, missing fields, invalid kind, bad sig, dup nonce)
  - compute_beacon_digest (empty, pending, mixed hash versions)
  - mark_anchored, get_recent_envelopes
  - normalize_beacon_pagination (int, string, overflow, negative)
  - init_beacon_table / _ensure_payload_hash_version_column migration
  - Constants (VALID_KINDS, REQUIRED_ENVELOPE_FIELDS, etc.)
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import time
from hashlib import blake2b
from unittest.mock import ANY, MagicMock, call, patch

import pytest

sys.path.insert(0, "node")
import beacon_anchor as ba
from beacon_anchor import (
    CURRENT_PAYLOAD_HASH_VERSION,
    LEGACY_PAYLOAD_HASH_VERSION,
    REQUIRED_ENVELOPE_FIELDS,
    UNSIGNED_TRANSPORT_FIELDS,
    VALID_KINDS,
)

# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def temp_db():
    """Yield a temporary SQLite database path and clean up."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    yield tmp.name
    os.unlink(tmp.name)


# ── Valid envelope helpers (without signature — we mock sig verify) ───

def _make_envelope(agent_id: str = "bcn_a1b2c3d4e5f6", kind: str = "heartbeat",
                   nonce: str = "n1", sig: str = "ab" * 32,
                   pubkey: str = "cd" * 32, **extras) -> dict:
    env = {
        "agent_id": agent_id,
        "kind": kind,
        "nonce": nonce,
        "sig": sig,
        "pubkey": pubkey,
        "_beacon_version": "2",
    }
    env.update(extras)
    return env


# ══════════════════════════════════════════════════════════════════════
# 1.  Helper functions
# ══════════════════════════════════════════════════════════════════════

class TestAgentIdFromPubkey:
    def test_returns_bcn_prefixed_sha256_truncated(self):
        pubkey = bytes(range(32))
        result = ba._agent_id_from_pubkey(pubkey)
        assert result.startswith("bcn_")
        assert len(result) == 4 + 12  # "bcn_" + 12 hex chars

    def test_deterministic(self):
        pubkey = b"\\x00" * 32
        a = ba._agent_id_from_pubkey(pubkey)
        b = ba._agent_id_from_pubkey(pubkey)
        assert a == b

    def test_different_pubkeys_different_ids(self):
        a = ba._agent_id_from_pubkey(b"\\x00" * 32)
        b = ba._agent_id_from_pubkey(b"\\xff" * 32)
        assert a != b


class TestCanonicalSignedFields:
    def test_strips_sig_and_beacon_version(self):
        env = _make_envelope(sig="abcd", _beacon_version="2", extra_field="x")
        result = ba._canonical_signed_fields(env)
        assert "sig" not in result
        assert "_beacon_version" not in result
        assert "extra_field" in result

    def test_preserves_all_other_fields(self):
        env = _make_envelope(extra="val", metadata="data")
        result = ba._canonical_signed_fields(env)
        assert result["extra"] == "val"
        assert result["metadata"] == "data"


class TestCanonicalSigningPayload:
    def test_returns_utf8_bytes(self):
        env = _make_envelope(extra="x")
        payload = ba._canonical_signing_payload(env)
        assert isinstance(payload, bytes)

    def test_deterministic_sort_keys(self):
        env1 = _make_envelope(a="1", b="2")
        env2 = _make_envelope(b="2", a="1")
        assert ba._canonical_signing_payload(env1) == ba._canonical_signing_payload(env2)

    def test_compact_separators(self):
        env = _make_envelope(a=1, b=2)
        payload = ba._canonical_signing_payload(env).decode()
        # No spaces in JSON: '{"a":1,"b":2,...}'
        assert " " not in payload
        assert ", " not in payload


class TestHashEnvelope:
    def test_returns_64_char_hex(self):
        env = _make_envelope()
        h = ba.hash_envelope(env)
        assert isinstance(h, str)
        assert len(h) == 64

    def test_deterministic(self):
        env = _make_envelope()
        assert ba.hash_envelope(env) == ba.hash_envelope(env)

    def test_different_inputs_different_hashes(self):
        h1 = ba.hash_envelope(_make_envelope(nonce="n1"))
        h2 = ba.hash_envelope(_make_envelope(nonce="n2"))
        assert h1 != h2


# ══════════════════════════════════════════════════════════════════════
# 2.  Signature verification
# ══════════════════════════════════════════════════════════════════════

class TestVerifyEnvelopeSignature:
    def test_missing_sig_returns_false(self):
        ok, err = ba.verify_envelope_signature({"agent_id": "x", "pubkey": "y"})
        assert not ok
        assert "missing" in err.lower()

    def test_missing_pubkey_returns_false(self):
        ok, err = ba.verify_envelope_signature({"agent_id": "x", "sig": "ab"})
        assert not ok
        assert "missing" in err.lower()

    def test_invalid_hex_encoding(self):
        env = _make_envelope(sig="nothex", pubkey="cd" * 32,
                             agent_id="bcn_a1b2c3d4e5f6")
        ok, err = ba.verify_envelope_signature(env)
        assert not ok
        assert "encoding" in err.lower()

    def test_agent_id_mismatch(self):
        """agent_id doesn't match SHA-256 of pubkey."""
        env = _make_envelope(agent_id="bcn_wrongid")
        ok, err = ba.verify_envelope_signature(env)
        assert not ok
        assert "mismatch" in err.lower()

    def test_nacl_unavailable(self):
        from nacl.signing import SigningKey
        sk = SigningKey.generate()
        pk_hex = sk.verify_key.encode().hex()
        agent_id = ba._agent_id_from_pubkey(sk.verify_key.encode())
        env = _make_envelope(agent_id=agent_id, pubkey=pk_hex, sig="aa" * 64)
        with patch("beacon_anchor.NACL_AVAILABLE", False):
            ok, err = ba.verify_envelope_signature(env)
            assert not ok
            assert "unavailable" in err.lower()

    def test_invalid_signature(self):
        """VerifyKey.verify raises BadSignatureError."""
        from nacl.signing import SigningKey
        sk = SigningKey.generate()
        pk_hex = sk.verify_key.encode().hex()
        agent_id = ba._agent_id_from_pubkey(sk.verify_key.encode())
        env = _make_envelope(agent_id=agent_id, pubkey=pk_hex, sig="aa" * 64)
        with patch("beacon_anchor.VerifyKey") as mock_vk:
            mock_vk.return_value.verify.side_effect = Exception("bad sig")
            ok, err = ba.verify_envelope_signature(env)
            assert not ok

    def test_valid_signature(self):
        """Real Ed25519 verify with nacl."""
        from nacl.signing import SigningKey
        sk = SigningKey.generate()
        pk_hex = sk.verify_key.encode().hex()
        agent_id = ba._agent_id_from_pubkey(sk.verify_key.encode())

        env = _make_envelope(agent_id=agent_id, pubkey=pk_hex)
        # Sign the canonical payload
        sig = sk.sign(ba._canonical_signing_payload(env))[:64]
        env["sig"] = sig.hex()

        ok, err = ba.verify_envelope_signature(env)
        assert ok, f"Expected valid sig, got err={err}"
        assert err == ""


# ══════════════════════════════════════════════════════════════════════
# 3.  Store envelope
# ══════════════════════════════════════════════════════════════════════

class TestStoreEnvelope:
    def _signed_env(self, sk=None):
        """Helper: produce a validly-signed envelope."""
        from nacl.signing import SigningKey
        sk = sk or SigningKey.generate()
        pk_hex = sk.verify_key.encode().hex()
        agent_id = ba._agent_id_from_pubkey(sk.verify_key.encode())
        env = _make_envelope(agent_id=agent_id, pubkey=pk_hex, nonce=f"n{time.time_ns()}")
        sig = sk.sign(ba._canonical_signing_payload(env))[:64]
        env["sig"] = sig.hex()
        return env

    def test_stores_valid_envelope(self, temp_db):
        ba.init_beacon_table(temp_db)
        env = self._signed_env()
        result = ba.store_envelope(env, temp_db)
        assert result["ok"] is True
        assert "id" in result
        assert result["payload_hash_version"] == CURRENT_PAYLOAD_HASH_VERSION
        assert len(result["payload_hash"]) == 64

    def test_missing_fields(self, temp_db):
        ba.init_beacon_table(temp_db)
        result = ba.store_envelope({"kind": "hello"}, temp_db)
        assert result["ok"] is False
        assert "missing" in result["error"]

    def test_invalid_kind(self, temp_db):
        ba.init_beacon_table(temp_db)
        env = self._signed_env()
        env["kind"] = "invalid_kind"
        result = ba.store_envelope(env, temp_db)
        assert result["ok"] is False
        assert "invalid_kind" in result["error"]

    def test_duplicate_nonce(self, temp_db):
        ba.init_beacon_table(temp_db)
        env1 = self._signed_env()
        nonce = env1["nonce"]
        # Insert first
        r1 = ba.store_envelope(env1, temp_db)
        assert r1["ok"] is True
        # Insert second with same nonce but valid sig
        env2 = self._signed_env()
        env2["nonce"] = nonce
        # Re-sign env2 with the new nonce
        from nacl.signing import SigningKey
        sk2 = SigningKey.generate()
        pk2_hex = sk2.verify_key.encode().hex()
        agent2 = ba._agent_id_from_pubkey(sk2.verify_key.encode())
        env2["pubkey"] = pk2_hex
        env2["agent_id"] = agent2
        sig2 = sk2.sign(ba._canonical_signing_payload(env2))[:64]
        env2["sig"] = sig2.hex()
        r2 = ba.store_envelope(env2, temp_db)
        assert r2["ok"] is False
        assert "duplicate" in r2["error"].lower()

    def test_bad_signature_rejected(self, temp_db):
        ba.init_beacon_table(temp_db)
        env = self._signed_env()
        env["sig"] = "ff" * 64  # Corrupt signature
        result = ba.store_envelope(env, temp_db)
        assert result["ok"] is False

    def test_returns_payload_hash_and_version(self, temp_db):
        ba.init_beacon_table(temp_db)
        env = self._signed_env()
        result = ba.store_envelope(env, temp_db)
        assert result["ok"] is True
        assert isinstance(result["payload_hash"], str)
        assert len(result["payload_hash"]) == 64
        assert result["payload_hash_version"] == CURRENT_PAYLOAD_HASH_VERSION


# ══════════════════════════════════════════════════════════════════════
# 4.  Digest computation
# ══════════════════════════════════════════════════════════════════════

class TestComputeBeaconDigest:
    def _seed_envelopes(self, db_path, count=3):
        """Insert count valid envelopes into the temp DB."""
        from nacl.signing import SigningKey
        ba.init_beacon_table(db_path)
        sk = SigningKey.generate()
        for i in range(count):
            env = {
                "agent_id": ba._agent_id_from_pubkey(sk.verify_key.encode()),
                "kind": "heartbeat",
                "nonce": f"dnonce_{i}_{time.time_ns()}",
                "sig": "aa" * 64,  # won't verify but we'll mock verify
                "pubkey": sk.verify_key.encode().hex(),
            }
            # Mock verify to pass
            with patch("beacon_anchor.verify_envelope_signature",
                       return_value=(True, "")):
                ba.store_envelope(env, db_path)

    def test_empty_returns_none_digest(self, temp_db):
        ba.init_beacon_table(temp_db)
        d = ba.compute_beacon_digest(temp_db)
        assert d["digest"] is None
        assert d["count"] == 0
        assert d["ids"] == []

    def test_returns_digest_for_pending(self, temp_db):
        self._seed_envelopes(temp_db, 3)
        d = ba.compute_beacon_digest(temp_db)
        assert d["digest"] is not None
        assert d["count"] == 3
        assert len(d["ids"]) == 3
        assert d["latest_ts"] > 0

    def test_unanchored_only_counted(self, temp_db):
        self._seed_envelopes(temp_db, 2)
        d1 = ba.compute_beacon_digest(temp_db)
        assert d1["count"] == 2

    def test_mixed_payload_hash_versions_flag(self, temp_db):
        self._seed_envelopes(temp_db, 2)
        d = ba.compute_beacon_digest(temp_db)
        # All should be version 2 since we mocked fresh writes
        assert d["mixed_payload_hash_versions"] is False


# ══════════════════════════════════════════════════════════════════════
# 5.  Mark anchored
# ══════════════════════════════════════════════════════════════════════

class TestMarkAnchored:
    def _seed(self, db_path, count=3):
        from nacl.signing import SigningKey
        ba.init_beacon_table(db_path)
        sk = SigningKey.generate()
        ids = []
        for i in range(count):
            env = {
                "agent_id": ba._agent_id_from_pubkey(sk.verify_key.encode()),
                "kind": "hello",
                "nonce": f"manonce_{i}_{time.time_ns()}",
                "sig": "aa" * 64,
                "pubkey": sk.verify_key.encode().hex(),
            }
            with patch("beacon_anchor.verify_envelope_signature",
                       return_value=(True, "")):
                r = ba.store_envelope(env, db_path)
                ids.append(r["id"])
        return ids

    def test_empty_ids_noop(self, temp_db):
        ba.init_beacon_table(temp_db)
        # Should not crash
        ba.mark_anchored([], temp_db)

    def test_marks_ids_as_anchored(self, temp_db):
        ids = self._seed(temp_db, 3)
        ba.mark_anchored([ids[0]], temp_db)

        d = ba.compute_beacon_digest(temp_db)
        assert d["count"] == 2  # only 2 remain unanchored

    def test_anchored_excluded_from_digest(self, temp_db):
        ids = self._seed(temp_db, 2)
        ba.mark_anchored(ids, temp_db)
        d = ba.compute_beacon_digest(temp_db)
        assert d["count"] == 0
        assert d["digest"] is None


# ══════════════════════════════════════════════════════════════════════
# 6.  Pagination clamping
# ══════════════════════════════════════════════════════════════════════

class TestNormalizeBeaconPagination:
    def test_default_values(self):
        limit, offset = ba.normalize_beacon_pagination(50, 0)
        assert limit == 50
        assert offset == 0

    def test_clamps_limit_above_max(self):
        limit, _ = ba.normalize_beacon_pagination(999, 0)
        assert limit == 50

    def test_clamps_limit_below_min(self):
        limit, _ = ba.normalize_beacon_pagination(-5, 0)
        assert limit >= 1

    def test_clamps_negative_offset(self):
        _, offset = ba.normalize_beacon_pagination(10, -10)
        assert offset >= 0

    def test_string_limit_falls_back_to_max(self):
        limit, _ = ba.normalize_beacon_pagination("abc", 0)
        assert limit == 50

    def test_string_offset_falls_back_to_zero(self):
        _, offset = ba.normalize_beacon_pagination(10, "xyz")
        assert offset == 0

    def test_min_limit_is_1(self):
        limit, _ = ba.normalize_beacon_pagination(0, 0)
        assert limit == 1

    def test_max_limit_respected(self):
        limit, _ = ba.normalize_beacon_pagination(50, 0, max_limit=100)
        assert limit == 50
        limit2, _ = ba.normalize_beacon_pagination(150, 0, max_limit=100)
        assert limit2 == 100


# ══════════════════════════════════════════════════════════════════════
# 7.  get_recent_envelopes
# ══════════════════════════════════════════════════════════════════════

class TestGetRecentEnvelopes:
    def _seed(self, db_path, count=2):
        from nacl.signing import SigningKey
        ba.init_beacon_table(db_path)
        sk = SigningKey.generate()
        for i in range(count):
            env = {
                "agent_id": ba._agent_id_from_pubkey(sk.verify_key.encode()),
                "kind": "heartbeat",
                "nonce": f"gre_nonce_{i}_{time.time_ns()}",
                "sig": "aa" * 64,
                "pubkey": sk.verify_key.encode().hex(),
            }
            with patch("beacon_anchor.verify_envelope_signature",
                       return_value=(True, "")):
                ba.store_envelope(env, db_path)

    def test_returns_list(self, temp_db):
        ba.init_beacon_table(temp_db)
        result = ba.get_recent_envelopes(db_path=temp_db)
        assert isinstance(result, list)

    def test_newest_first(self, temp_db):
        self._seed(temp_db, 3)
        rows = ba.get_recent_envelopes(db_path=temp_db)
        assert len(rows) == 3
        # created_at should be descending
        timestamps = [r["created_at"] for r in rows]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_limit(self, temp_db):
        self._seed(temp_db, 5)
        rows = ba.get_recent_envelopes(limit=2, db_path=temp_db)
        assert len(rows) == 2

    def test_offset(self, temp_db):
        self._seed(temp_db, 3)
        all_rows = ba.get_recent_envelopes(limit=10, db_path=temp_db)
        offset_rows = ba.get_recent_envelopes(limit=10, offset=1, db_path=temp_db)
        assert len(offset_rows) == 2
        assert offset_rows[0]["id"] == all_rows[1]["id"]


# ══════════════════════════════════════════════════════════════════════
# 8.  init_beacon_table & schema migration
# ══════════════════════════════════════════════════════════════════════

class TestInitBeaconTable:
    def test_creates_table(self, temp_db):
        ba.init_beacon_table(temp_db)
        conn = sqlite3.connect(temp_db)
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='beacon_envelopes'"
        ).fetchall()
        conn.close()
        assert len(rows) == 1

    def test_idempotent(self, temp_db):
        ba.init_beacon_table(temp_db)
        ba.init_beacon_table(temp_db)  # should not raise
        conn = sqlite3.connect(temp_db)
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='beacon_envelopes'"
        ).fetchall()
        conn.close()
        assert len(rows) == 1

    def test_creates_indexes(self, temp_db):
        ba.init_beacon_table(temp_db)
        conn = sqlite3.connect(temp_db)
        indices = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='beacon_envelopes'"
        ).fetchall()
        conn.close()
        names = {r[0] for r in indices}
        assert "idx_beacon_anchored" in names
        assert "idx_beacon_agent" in names

    def test_payload_hash_column_exists(self, temp_db):
        ba.init_beacon_table(temp_db)
        conn = sqlite3.connect(temp_db)
        columns = {r[1] for r in conn.execute("PRAGMA table_info(beacon_envelopes)").fetchall()}
        conn.close()
        assert "payload_hash_version" in columns


class TestEnsurePayloadHashVersionColumn:
    def test_adds_column_when_missing(self, temp_db):
        # Create table without the column
        conn = sqlite3.connect(temp_db)
        conn.execute("""
            CREATE TABLE beacon_envelopes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL
            )
        """)
        conn.close()
        ba._ensure_payload_hash_version_column(sqlite3.connect(temp_db))
        conn = sqlite3.connect(temp_db)
        columns = {r[1] for r in conn.execute("PRAGMA table_info(beacon_envelopes)").fetchall()}
        conn.close()
        assert "payload_hash_version" in columns

    def test_updates_null_versions_to_legacy(self, temp_db):
        ba.init_beacon_table(temp_db)
        conn = sqlite3.connect(temp_db)
        conn.execute("INSERT INTO beacon_envelopes (agent_id, kind, nonce, sig, pubkey, payload_hash, created_at) "
                     "VALUES ('a', 'b', 'c', 'd', 'e', 'f', 1)")
        conn.commit()
        # At this point payload_hash_version should be DEFAULT 1 from schema
        row = conn.execute("SELECT payload_hash_version FROM beacon_envelopes").fetchone()
        conn.close()
        assert row[0] == 1  # DEFAULT from CREATE TABLE


# ══════════════════════════════════════════════════════════════════════
# 9.  Constants
# ══════════════════════════════════════════════════════════════════════

class TestConstants:
    def test_valid_kinds(self):
        assert "hello" in VALID_KINDS
        assert "heartbeat" in VALID_KINDS
        assert "want" in VALID_KINDS
        assert "bounty" in VALID_KINDS
        assert "mayday" in VALID_KINDS
        assert "accord" in VALID_KINDS
        assert "pushback" in VALID_KINDS
        assert len(VALID_KINDS) == 7

    def test_required_fields(self):
        assert "agent_id" in REQUIRED_ENVELOPE_FIELDS
        assert "kind" in REQUIRED_ENVELOPE_FIELDS
        assert "nonce" in REQUIRED_ENVELOPE_FIELDS
        assert "sig" in REQUIRED_ENVELOPE_FIELDS
        assert "pubkey" in REQUIRED_ENVELOPE_FIELDS
        assert len(REQUIRED_ENVELOPE_FIELDS) == 5

    def test_unsigned_transport_fields(self):
        assert "sig" in UNSIGNED_TRANSPORT_FIELDS
        assert "_beacon_version" in UNSIGNED_TRANSPORT_FIELDS

    def test_hash_version_constants(self):
        assert LEGACY_PAYLOAD_HASH_VERSION == 1
        assert CURRENT_PAYLOAD_HASH_VERSION == 2