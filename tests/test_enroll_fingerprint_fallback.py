"""Tests for resolve_enroll_fingerprint (PR #7509, node-side half of #7489).

The enroll path's rotating fingerprint check used to read ONLY the enroll-body
fingerprint. Deployed miners (clawrtc / rustchain_linux) send the fingerprint
at attestation, not at enroll, so they enrolled at active_ratio=0 and collapsed
to zero weight. resolve_enroll_fingerprint falls back to the stored attestation
fingerprint. These tests pin the format round-trip and the fallback triggers.
"""
import json
import sqlite3

import pytest

# Pre-loaded by tests/conftest.py via importlib (module name has dots).
integrated_node = pytest.importorskip("integrated_node")
resolve_enroll_fingerprint = integrated_node.resolve_enroll_fingerprint


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.execute(
        "CREATE TABLE miner_attest_recent ("
        "  miner TEXT PRIMARY KEY,"
        "  fingerprint_checks_json TEXT DEFAULT '{}'"
        ")"
    )
    yield c
    c.close()


def _store(conn, miner, checks_json):
    conn.execute(
        "INSERT INTO miner_attest_recent (miner, fingerprint_checks_json) VALUES (?, ?)",
        (miner, checks_json),
    )


# Bare check map is how the attestation path persists it (see fp_checks_map write).
_STORED_BARE = {"clock_drift": True, "cache_timing": True, "anti_emulation": True}


def test_body_fingerprint_wins(conn):
    """A real (non-empty) body fingerprint is authoritative; no DB read needed."""
    _store(conn, "minerA", json.dumps(_STORED_BARE))
    body = {"fingerprint": {"checks": {"clock_drift": {"passed": True}}}}
    out = resolve_enroll_fingerprint(conn, "minerA", body)
    assert out == {"checks": {"clock_drift": {"passed": True}}}


def test_omitted_body_falls_back_to_attestation(conn):
    """Field omitted -> stored bare map, rewrapped under 'checks' for the consumer."""
    _store(conn, "minerB", json.dumps(_STORED_BARE))
    out = resolve_enroll_fingerprint(conn, "minerB", {})
    assert out == {"checks": _STORED_BARE}


def test_empty_dict_body_falls_back(conn):
    """{"fingerprint": {}} carries no data -> treat as omitted, use the fallback."""
    _store(conn, "minerC", json.dumps(_STORED_BARE))
    out = resolve_enroll_fingerprint(conn, "minerC", {"fingerprint": {}})
    assert out == {"checks": _STORED_BARE}


def test_no_attestation_row_returns_empty(conn):
    """No stored attestation and no body -> empty dict (caller handles zero)."""
    out = resolve_enroll_fingerprint(conn, "unknown-miner", {})
    assert out == {}


def test_malformed_stored_json_returns_empty(conn):
    """Corrupt fingerprint_checks_json must not raise; collapses to {}."""
    _store(conn, "minerD", "{not valid json")
    out = resolve_enroll_fingerprint(conn, "minerD", {})
    assert out == {}


def test_non_dict_body_fingerprint_falls_back(conn):
    """A non-dict body value (e.g. a string) is ignored in favour of the fallback."""
    _store(conn, "minerE", json.dumps(_STORED_BARE))
    out = resolve_enroll_fingerprint(conn, "minerE", {"fingerprint": "garbage"})
    assert out == {"checks": _STORED_BARE}


def test_roundtrip_through_rotating_check(conn):
    """End-to-end: fallback output feeds the real rotating consumer as bare bools.

    Guards the format contract Brain-4 flagged: stored bare bools must survive
    _fingerprint_checks_map -> _fingerprint_check_passed without raising.
    """
    _store(conn, "minerF", json.dumps(_STORED_BARE))
    fp = resolve_enroll_fingerprint(conn, "minerF", {})
    checks_map = integrated_node._fingerprint_checks_map(fp)
    # bare bool entries must read as passed via the bool branch
    assert integrated_node._fingerprint_check_passed(checks_map["clock_drift"]) is True
