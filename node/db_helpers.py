"""Bounded-query helpers to eliminate the UTXO-OOM bug class.

This module exists because the project shipped four `[UTXO-BUG]` fixes in a
single week (#6526, #6535, #6537, #6562, #6563, #6571) — all the same shape:
an unbounded ``.fetchall()`` on an attacker-influenced query path, materializing
arbitrary row counts into a Python list, exhausting node memory.

Each individual finding was Medium severity. The class is High because
the same shape keeps surfacing on different endpoints. The fix is
architectural, not per-route: a single helper that **always** appends an
explicit ``LIMIT`` (validated against ``max_limit``) before issuing the
``SELECT``, paired with a CI guard (``scripts/check_fetchall.sh``) that
refuses to land new raw ``.fetchall()`` calls in route/UTXO/sync/bridge
code without an opt-in annotation explaining why bounded materialization
is safe at that site.

See: https://github.com/Scottcjn/Rustchain/issues/6627

Usage::

    from node.db_helpers import fetch_page

    rows = fetch_page(
        conn,
        "SELECT id, miner, ts FROM ledger WHERE miner = ?",
        (miner_id,),
        limit=100,
        offset=0,
    )

For "this must return 0 or 1 row" lookups (settlement state, unique
configuration rows, single-row PRAGMA-equivalents), use
``fetch_one_or_none`` — it raises ``ValueError`` if more than one row
materializes, which catches schema-violation bugs early instead of
silently using ``LIMIT 1``.
"""
from __future__ import annotations

import re
import sqlite3
from typing import Optional, Sequence, Union

# Reject only an outer LIMIT. Subqueries may legitimately use LIMIT 1 while
# the outer result still needs fetch_page's bound.
_SQL_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[()]")

ParamsType = Union[Sequence, tuple]


def _strip_sql_literals_and_comments(sql: str) -> str:
    """Remove SQL string literals and comments before lightweight token scans."""
    out = []
    quote = None
    index = 0
    while index < len(sql):
        char = sql[index]

        if quote:
            if char == quote:
                if index + 1 < len(sql) and sql[index + 1] == quote:
                    index += 2
                    continue
                quote = None
            index += 1
            continue

        if char in {"'", '"'}:
            quote = char
            index += 1
            continue
        if char == "-" and index + 1 < len(sql) and sql[index + 1] == "-":
            index += 2
            while index < len(sql) and sql[index] not in "\r\n":
                index += 1
            continue
        if char == "/" and index + 1 < len(sql) and sql[index + 1] == "*":
            index += 2
            while index + 1 < len(sql) and sql[index : index + 2] != "*/":
                index += 1
            index += 2
            continue

        out.append(char)
        index += 1
    return "".join(out)


def _has_outer_limit(sql: str) -> bool:
    depth = 0
    for token in _SQL_TOKEN_RE.findall(_strip_sql_literals_and_comments(sql)):
        if token == "(":
            depth += 1
        elif token == ")":
            depth = max(0, depth - 1)
        elif depth == 0 and token.upper() == "LIMIT":
            return True
    return False


def fetch_page(
    conn: sqlite3.Connection,
    sql: str,
    params: ParamsType = (),
    *,
    limit: int,
    offset: int = 0,
    max_limit: int = 1000,
) -> list:
    """Bounded ``SELECT`` against ``conn`` with an explicit, capped limit.

    Appends ``LIMIT ? OFFSET ?`` to ``sql`` after validating that ``sql``
    does not already encode a ``LIMIT`` clause. This is the foundation for
    eliminating the UTXO-OOM bug class (issue #6627): every public/semi-public
    query path goes through this helper so that the worst case is
    bounded by ``max_limit`` regardless of the caller's ``limit`` argument.

    Args:
        conn: SQLite connection. Caller manages ``row_factory``.
        sql: ``SELECT`` statement WITHOUT a trailing ``LIMIT`` clause.
        params: Positional parameters for ``sql``.
        limit: Maximum number of rows to return (must be >= 0).
        offset: Number of rows to skip (must be >= 0).
        max_limit: Hard upper bound on ``limit``. Defaults to 1000.

    Returns:
        list: Rows produced by ``conn.execute(...).fetchall()`` (after
        ``LIMIT``/``OFFSET`` have been appended). Element type depends on
        ``conn.row_factory`` — typically ``tuple`` or ``sqlite3.Row``.

    Raises:
        ValueError: If ``limit > max_limit``, if ``limit < 0`` or
            ``offset < 0``, or if ``sql`` already contains a ``LIMIT``
            clause (case-insensitive).
    """
    if limit < 0:
        raise ValueError(f"limit must be >= 0, got {limit}")
    if offset < 0:
        raise ValueError(f"offset must be >= 0, got {offset}")
    if limit > max_limit:
        raise ValueError(
            f"limit {limit} exceeds max_limit {max_limit} "
            f"(see issue #6627 — bounded-query helper guards against "
            f"unbounded materialization)"
        )
    if _has_outer_limit(sql):
        raise ValueError(
            "sql already contains a LIMIT clause at the outer query level; "
            "fetch_page is the single source of truth for bounds — strip "
            "the existing LIMIT and pass it via the limit kwarg instead"
        )

    bounded_sql = f"{sql.rstrip().rstrip(';')} LIMIT ? OFFSET ?"
    bound_params = tuple(params) + (int(limit), int(offset))
    return conn.execute(bounded_sql, bound_params).fetchall()


def fetch_one_or_none(
    conn: sqlite3.Connection,
    sql: str,
    params: ParamsType = (),
):
    """Run a query that MUST return 0 or 1 rows.

    Use this for unique-key lookups, settlement state reads, single-row
    config reads, or anywhere the schema guarantees at most one matching
    row. If the query materializes more than one row, this raises
    ``ValueError`` instead of silently using ``LIMIT 1`` and hiding a
    schema bug.

    Args:
        conn: SQLite connection.
        sql: ``SELECT`` statement WITHOUT a trailing ``LIMIT`` clause.
        params: Positional parameters for ``sql``.

    Returns:
        The single row produced by the query, or ``None`` if no rows
        matched. Row type depends on ``conn.row_factory``.

    Raises:
        ValueError: If ``sql`` already contains a ``LIMIT`` clause, or if
            more than 1 row materializes.
    """
    if _has_outer_limit(sql):
        raise ValueError(
            "sql already contains a LIMIT clause at the outer query level; "
            "fetch_one_or_none appends its own bound (LIMIT 2) — remove the "
            "existing LIMIT"
        )
    # Fetch up to 2 rows so we can detect "more than one matched".
    bounded_sql = f"{sql.rstrip().rstrip(';')} LIMIT 2"
    rows = conn.execute(bounded_sql, tuple(params)).fetchall()
    if not rows:
        return None
    if len(rows) > 1:
        raise ValueError(
            "fetch_one_or_none matched more than one row; either the "
            "schema invariant was violated or this query should use "
            "fetch_page instead"
        )
    return rows[0]


def count_estimate(
    conn: sqlite3.Connection,
    table: str,
    *,
    where: Optional[str] = None,
    params: ParamsType = (),
) -> int:
    """Bounded ``COUNT(*)`` against ``table`` with an optional ``WHERE``.

    Returns an exact count (SQLite ``COUNT(*)`` is not actually an estimate,
    but the helper is named for the use case — callers want a number for
    pagination metadata or to decide whether to enable a "load more" link,
    not to drive consensus). ``table`` is validated against a simple
    identifier regex to refuse anything that would let a caller smuggle SQL.

    Args:
        conn: SQLite connection.
        table: Table name (validated against ``[A-Za-z_][A-Za-z0-9_]*``).
        where: Optional ``WHERE`` clause body (without the ``WHERE`` keyword).
            Use ``?`` placeholders for ``params``.
        params: Positional parameters for the ``where`` clause.

    Returns:
        int: Count of matching rows.

    Raises:
        ValueError: If ``table`` is not a valid identifier.
    """
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", table):
        raise ValueError(f"invalid table identifier: {table!r}")
    sql = f"SELECT COUNT(*) FROM {table}"
    if where:
        sql += f" WHERE {where}"
    row = conn.execute(sql, tuple(params)).fetchone()
    return int(row[0] if row else 0)


__all__ = ["fetch_page", "fetch_one_or_none", "count_estimate"]
