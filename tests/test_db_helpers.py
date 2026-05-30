"""Tests for node.db_helpers — bounded-query helpers (issue #6627).

These tests use in-memory SQLite so no DB file fixture is needed. They
cover the contract surface exhaustively because this helper sits on the
hot path for every public/semi-public route conversion that's being done
to eliminate the UTXO-OOM bug class.
"""
from __future__ import annotations

import os
import sqlite3
import sys

import pytest

# Make `node/` importable when pytest is invoked from the repo root.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from node.db_helpers import count_estimate, fetch_one_or_none, fetch_page


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def conn():
    """In-memory SQLite connection seeded with a `widgets` table."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute(
        "CREATE TABLE widgets (id INTEGER PRIMARY KEY, name TEXT, owner TEXT)"
    )
    for i in range(50):
        c.execute(
            "INSERT INTO widgets (id, name, owner) VALUES (?, ?, ?)",
            (i, f"widget-{i}", "alice" if i % 2 == 0 else "bob"),
        )
    c.commit()
    return c


# ---------------------------------------------------------------------------
# fetch_page
# ---------------------------------------------------------------------------


def test_fetch_page_returns_rows_up_to_limit(conn):
    rows = fetch_page(conn, "SELECT id FROM widgets ORDER BY id", limit=10)
    assert len(rows) == 10
    assert [r["id"] for r in rows] == list(range(10))


def test_fetch_page_returns_fewer_rows_when_query_underflows_limit(conn):
    rows = fetch_page(
        conn,
        "SELECT id FROM widgets WHERE owner = ? ORDER BY id",
        ("alice",),
        limit=5,
    )
    assert len(rows) == 5  # 5 of 25 alice rows


def test_fetch_page_empty_when_no_matching_rows(conn):
    rows = fetch_page(
        conn,
        "SELECT id FROM widgets WHERE owner = ?",
        ("nobody",),
        limit=10,
    )
    assert rows == []


def test_fetch_page_offset_skips_correct_rows(conn):
    rows = fetch_page(
        conn,
        "SELECT id FROM widgets ORDER BY id",
        limit=5,
        offset=10,
    )
    assert [r["id"] for r in rows] == [10, 11, 12, 13, 14]


def test_fetch_page_offset_past_end_returns_empty(conn):
    rows = fetch_page(
        conn, "SELECT id FROM widgets ORDER BY id", limit=10, offset=999
    )
    assert rows == []


def test_fetch_page_rejects_limit_above_max_limit(conn):
    with pytest.raises(ValueError, match="exceeds max_limit"):
        fetch_page(
            conn,
            "SELECT id FROM widgets",
            limit=1001,
            max_limit=1000,
        )


def test_fetch_page_respects_custom_max_limit(conn):
    # Tighter max_limit should reject what would have passed under the default.
    with pytest.raises(ValueError, match="exceeds max_limit"):
        fetch_page(conn, "SELECT id FROM widgets", limit=11, max_limit=10)


def test_fetch_page_rejects_negative_limit(conn):
    with pytest.raises(ValueError, match="limit must be >= 0"):
        fetch_page(conn, "SELECT id FROM widgets", limit=-1)


def test_fetch_page_rejects_negative_offset(conn):
    with pytest.raises(ValueError, match="offset must be >= 0"):
        fetch_page(conn, "SELECT id FROM widgets", limit=10, offset=-5)


def test_fetch_page_rejects_sql_with_uppercase_limit(conn):
    with pytest.raises(ValueError, match="already contains a LIMIT"):
        fetch_page(conn, "SELECT id FROM widgets LIMIT 5", limit=10)


def test_fetch_page_rejects_sql_with_lowercase_limit(conn):
    with pytest.raises(ValueError, match="already contains a LIMIT"):
        fetch_page(conn, "select id from widgets limit 5", limit=10)


def test_fetch_page_rejects_sql_with_mixed_case_limit(conn):
    with pytest.raises(ValueError, match="already contains a LIMIT"):
        fetch_page(conn, "SELECT id FROM widgets LiMiT ?", limit=10)


def test_fetch_page_strips_trailing_semicolon(conn):
    # SQLite tolerates trailing semicolons but the LIMIT/OFFSET append needs
    # to land before any semicolon — verify the helper handles that.
    rows = fetch_page(conn, "SELECT id FROM widgets ORDER BY id;", limit=3)
    assert len(rows) == 3


def test_fetch_page_limit_zero_returns_empty(conn):
    rows = fetch_page(conn, "SELECT id FROM widgets", limit=0)
    assert rows == []


# ---------------------------------------------------------------------------
# fetch_one_or_none
# ---------------------------------------------------------------------------


def test_fetch_one_or_none_returns_none_for_zero_rows(conn):
    result = fetch_one_or_none(
        conn, "SELECT id FROM widgets WHERE owner = ?", ("nobody",)
    )
    assert result is None


def test_fetch_one_or_none_returns_row_for_one_match(conn):
    result = fetch_one_or_none(
        conn, "SELECT id, name FROM widgets WHERE id = ?", (7,)
    )
    assert result is not None
    assert result["id"] == 7
    assert result["name"] == "widget-7"


def test_fetch_one_or_none_raises_when_multiple_rows_match(conn):
    with pytest.raises(ValueError, match="more than one row"):
        fetch_one_or_none(
            conn, "SELECT id FROM widgets WHERE owner = ?", ("alice",)
        )


def test_fetch_one_or_none_rejects_sql_with_limit(conn):
    with pytest.raises(ValueError, match="already contains a LIMIT"):
        fetch_one_or_none(conn, "SELECT id FROM widgets LIMIT 1")


# ---------------------------------------------------------------------------
# count_estimate
# ---------------------------------------------------------------------------


def test_count_estimate_returns_int(conn):
    assert count_estimate(conn, "widgets") == 50


def test_count_estimate_with_where_clause(conn):
    assert (
        count_estimate(conn, "widgets", where="owner = ?", params=("alice",))
        == 25
    )


def test_count_estimate_returns_zero_for_empty_table(conn):
    conn.execute("CREATE TABLE empty_table (id INTEGER)")
    assert count_estimate(conn, "empty_table") == 0


def test_count_estimate_rejects_invalid_table_name(conn):
    with pytest.raises(ValueError, match="invalid table identifier"):
        count_estimate(conn, "widgets; DROP TABLE widgets")


def test_count_estimate_rejects_table_with_spaces(conn):
    with pytest.raises(ValueError, match="invalid table identifier"):
        count_estimate(conn, "widgets OR 1=1")
