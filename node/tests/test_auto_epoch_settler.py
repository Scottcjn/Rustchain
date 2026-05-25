# SPDX-License-Identifier: MIT
"""Tests for auto_epoch_settler.py — epoch settlement daemon."""

import json
import os
import sys
import sqlite3
import tempfile
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_epoch_settler import (
    get_current_slot,
    get_current_epoch_from_db,
    get_unsettled_epochs,
    settle_epoch_via_api,
    SLOTS_PER_EPOCH,
)

import auto_epoch_settler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db():
    """Create an in-memory DB with headers and epoch_state tables."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE headers (slot INTEGER PRIMARY KEY, hash TEXT)")
    conn.execute("CREATE TABLE epoch_state (epoch INTEGER PRIMARY KEY, settled INTEGER DEFAULT 0)")
    return conn


def _seed_headers(conn, start_slot, end_slot, step=1):
    for slot in range(start_slot, end_slot + 1, step):
        conn.execute("INSERT OR IGNORE INTO headers (slot, hash) VALUES (?, ?)",
                     (slot, f"hash_{slot}"))
    conn.commit()


def _seed_epoch_state(conn, epoch, settled=0):
    conn.execute(
        "INSERT OR REPLACE INTO epoch_state (epoch, settled) VALUES (?, ?)",
        (epoch, settled),
    )
    conn.commit()


def _patch_connect(real_conn):
    """Monkey-patch auto_epoch_settler.sqlite3.connect to return real_conn."""
    original = auto_epoch_settler.sqlite3.connect
    auto_epoch_settler.sqlite3.connect = lambda path: real_conn
    return original


def _restore_connect(original):
    auto_epoch_settler.sqlite3.connect = original


# ---------------------------------------------------------------------------
# Tests for get_current_slot
# ---------------------------------------------------------------------------


@patch("auto_epoch_settler.requests.get")
def test_get_current_slot_from_api(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"epoch": 5}
    mock_get.return_value = mock_resp

    slot = get_current_slot()
    assert slot == 5 * SLOTS_PER_EPOCH
    mock_get.assert_called_once_with("http://localhost:8088/api/stats", timeout=10)


@patch("auto_epoch_settler.requests.get")
def test_get_current_slot_api_error(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_get.return_value = mock_resp
    assert get_current_slot() is None


@patch("auto_epoch_settler.requests.get")
def test_get_current_slot_request_exception(mock_get):
    mock_get.side_effect = Exception("Connection refused")
    assert get_current_slot() is None


@patch("auto_epoch_settler.requests.get")
def test_get_current_slot_missing_epoch_key(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"slot": 999}
    mock_get.return_value = mock_resp
    assert get_current_slot() == 0


# ---------------------------------------------------------------------------
# Tests for get_current_epoch_from_db
# ---------------------------------------------------------------------------


def test_get_current_epoch_from_db_happy():
    real_conn = _make_db()
    _seed_headers(real_conn, 0, 300)
    orig = _patch_connect(real_conn)
    try:
        epoch = get_current_epoch_from_db()
        assert epoch == 2  # 300 // 144
    finally:
        _restore_connect(orig)


def test_get_current_epoch_from_db_empty():
    real_conn = _make_db()
    orig = _patch_connect(real_conn)
    try:
        assert get_current_epoch_from_db() is None
    finally:
        _restore_connect(orig)


def test_get_current_epoch_from_db_exception():
    """DB query raises → return None."""
    orig = _patch_connect(object())  # object() has no execute method
    try:
        assert get_current_epoch_from_db() is None
    finally:
        _restore_connect(orig)


def test_get_current_epoch_from_db_result_is_none():
    """MAX(slot) returns NULL → return None."""
    real_conn = _make_db()
    # Insert a row with NULL slot (or just no rows)
    orig = _patch_connect(real_conn)
    try:
        assert get_current_epoch_from_db() is None
    finally:
        _restore_connect(orig)


# ---------------------------------------------------------------------------
# Tests for get_unsettled_epochs
# ---------------------------------------------------------------------------


def test_get_unsettled_epochs_some_unsettled():
    real_conn = _make_db()
    _seed_headers(real_conn, 0, 4 * SLOTS_PER_EPOCH + 10)
    _seed_epoch_state(real_conn, 1, settled=1)
    orig = _patch_connect(real_conn)

    try:
        # Override get_current_epoch_from_db to return 5
        orig_epoch_fn = auto_epoch_settler.get_current_epoch_from_db
        auto_epoch_settler.get_current_epoch_from_db = lambda: 5
        try:
            unsettled = get_unsettled_epochs()
            assert 1 not in unsettled  # settled
            assert 2 in unsettled
            assert 3 in unsettled
            assert 4 in unsettled
            assert 5 not in unsettled  # current epoch
        finally:
            auto_epoch_settler.get_current_epoch_from_db = orig_epoch_fn
    finally:
        _restore_connect(orig)


def test_get_unsettled_epochs_fallback_to_api():
    real_conn = _make_db()
    _seed_headers(real_conn, 0, SLOTS_PER_EPOCH)
    orig = _patch_connect(real_conn)

    try:
        # get_current_epoch_from_db returns None, get_current_slot returns slot for epoch 3
        orig_epoch_fn = auto_epoch_settler.get_current_epoch_from_db
        auto_epoch_settler.get_current_epoch_from_db = lambda: None

        orig_slot_fn = auto_epoch_settler.get_current_slot
        auto_epoch_settler.get_current_slot = lambda: 3 * SLOTS_PER_EPOCH
        try:
            unsettled = get_unsettled_epochs()
            assert len(unsettled) >= 1
            assert 0 in unsettled
        finally:
            auto_epoch_settler.get_current_epoch_from_db = orig_epoch_fn
            auto_epoch_settler.get_current_slot = orig_slot_fn
    finally:
        _restore_connect(orig)


def test_get_unsettled_epochs_no_slot_no_epoch():
    real_conn = _make_db()
    orig = _patch_connect(real_conn)

    try:
        orig_epoch_fn = auto_epoch_settler.get_current_epoch_from_db
        auto_epoch_settler.get_current_epoch_from_db = lambda: None
        orig_slot_fn = auto_epoch_settler.get_current_slot
        auto_epoch_settler.get_current_slot = lambda: None
        try:
            assert get_unsettled_epochs() == []
        finally:
            auto_epoch_settler.get_current_epoch_from_db = orig_epoch_fn
            auto_epoch_settler.get_current_slot = orig_slot_fn
    finally:
        _restore_connect(orig)


def test_get_unsettled_epochs_all_settled():
    real_conn = _make_db()
    _seed_headers(real_conn, 0, 2 * SLOTS_PER_EPOCH)
    _seed_epoch_state(real_conn, 0, settled=1)
    _seed_epoch_state(real_conn, 1, settled=1)
    _seed_epoch_state(real_conn, 2, settled=1)
    orig = _patch_connect(real_conn)

    try:
        orig_epoch_fn = auto_epoch_settler.get_current_epoch_from_db
        auto_epoch_settler.get_current_epoch_from_db = lambda: 3
        try:
            assert get_unsettled_epochs() == []
        finally:
            auto_epoch_settler.get_current_epoch_from_db = orig_epoch_fn
    finally:
        _restore_connect(orig)


def test_get_unsettled_epochs_db_exception():
    orig = _patch_connect(object())
    try:
        orig_epoch_fn = auto_epoch_settler.get_current_epoch_from_db
        auto_epoch_settler.get_current_epoch_from_db = lambda: 5
        try:
            assert get_unsettled_epochs() == []
        finally:
            auto_epoch_settler.get_current_epoch_from_db = orig_epoch_fn
    finally:
        _restore_connect(orig)


# ---------------------------------------------------------------------------
# Tests for settle_epoch_via_api
# ---------------------------------------------------------------------------


@patch("auto_epoch_settler.requests.post")
def test_settle_epoch_api_success(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True, "epoch": 7, "eligible": 12, "distributed_rtc": 45.6}
    mock_post.return_value = mock_resp

    assert settle_epoch_via_api(7) is True
    mock_post.assert_called_once_with(
        "http://localhost:8088/rewards/settle", json={"epoch": 7}, timeout=30
    )


@patch("auto_epoch_settler.requests.post")
def test_settle_epoch_api_rejected(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": False, "error": "epoch_already_settled"}
    mock_post.return_value = mock_resp
    assert settle_epoch_via_api(7) is False


@patch("auto_epoch_settler.requests.post")
def test_settle_epoch_api_http_error(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_post.return_value = mock_resp
    assert settle_epoch_via_api(7) is False


@patch("auto_epoch_settler.requests.post")
def test_settle_epoch_api_network_error(mock_post):
    mock_post.side_effect = Exception("Timeout")
    assert settle_epoch_via_api(7) is False


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------


def test_get_unsettled_epochs_ignores_current_epoch():
    """Current epoch is never included in unsettled list."""
    real_conn = _make_db()
    _seed_headers(real_conn, 0, 5 * SLOTS_PER_EPOCH + 10)
    orig = _patch_connect(real_conn)

    try:
        # Override get_current_epoch_from_db to return 5
        orig_epoch_fn = auto_epoch_settler.get_current_epoch_from_db
        auto_epoch_settler.get_current_epoch_from_db = lambda: 5
        try:
            unsettled = get_unsettled_epochs()
            assert 5 not in unsettled
            assert len(unsettled) > 0
            assert all(e < 5 for e in unsettled)
        finally:
            auto_epoch_settler.get_current_epoch_from_db = orig_epoch_fn
    finally:
        _restore_connect(orig)
