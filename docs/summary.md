"""
node/db_helpers.py

Bounded query helper to prevent OOM-DoS from unbounded materialization
of attacker-influenced row sets. All public/semi-public SQLite endpoints
MUST use `fetch_page` instead of raw `.fetchall()`.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from typing import Any, List, Tuple, Union

__all__ = [
    "fetch_page",
    "DEFAULT_MAX_LIMIT",
]

logger = logging.getLogger(__name__)

# Maximum allowed rows per query across the entire codebase.
# Individual callers may impose a stricter limit.
DEFAULT_MAX_LIMIT: int = 1000

# Regex to detect existing LIMIT clause (case-insensitive).
# We disallow multiple LIMIT clauses to avoid ambiguity.
_HAS_LIMIT_RE: re.Pattern = re.compile(r"\bLIMIT\b", re.IGNORECASE)

# Regex to verify the SQL is a SELECT statement (whitespace‑safe).
_IS_SELECT_RE: re.Pattern = re.compile(r"^\s*SELECT\b", re.IGNORECASE)

# Regex to detect semicolons not inside string literals (simple heuristic).
# We reject any semicolons as a safety measure to prevent multi-statement injection.
_HAS_SEMICOLON_RE: re.Pattern = re.compile(r";(?!\s*(?:--|$))")


def _validate_sql(sql: str) -> None:
    """
    Validate that `sql` is a safe SELECT statement for bounded execution.

    Checks:
        - Must be a SELECT statement.
        - Must not contain a LIMIT clause.
        - Must not contain semicolons (prevents multi-statement injection).

    Raises ValueError on any violation.
    """
    if not sql.strip():
        raise ValueError("SQL must be a non-empty string.")

    if not _IS_SELECT_RE.match(sql.strip()):
        raise ValueError("Only SELECT statements are allowed; use fetch_page for reads only.")

    if _HAS_LIMIT_RE.search(sql):
        raise ValueError(
            "SQL must not contain an existing LIMIT clause; use "
            "fetch_page's limit parameter instead."
        )

    # Reject semicolons as a safety measure (cannot be fully context-aware).
    if _HAS_SEMICOLON_RE.search(sql):
        raise ValueError(
            "SQL must not contain semicolons; multi-statement queries are not allowed."
        )


def fetch_page(
    conn: sqlite3.Connection,
    sql: str,
    params: Tuple[Any, ...] = (),
    *,
    limit: int,
    offset: int = 0,
    max_limit: int = DEFAULT_MAX_LIMIT,
) -> List[sqlite3.Row]:
    """
    Execute a bounded SELECT query against `conn`.

    This is the single, mandatory helper for all user‑influenced SQL queries.
    It guarantees that the result set contains at most `max_limit` rows.

    Parameters
    ----------
    conn : sqlite3.Connection
        Active database connection. Must not be None or closed.
    sql : str
        The SELECT statement. Must not contain a LIMIT clause or semicolons.
    params : Tuple[Any, ...], optional
        Query parameters (use `?` placeholders). Defaults to ().
    limit : int
        Number of rows to fetch. Must be 0 <= limit <= max_limit.
    offset : int, optional
        Number of rows to skip before fetching. Must be >= 0.
    max_limit : int, optional
        Hard upper bound for `limit`. Must be >= 0. Defaults to 1000.

    Returns
    -------
    List[sqlite3.Row]
        A list of rows. Never None. Empty list if no rows match.

    Raises
    ------
    TypeError
        If `conn` is not a sqlite3.Connection or `params` is not a tuple.
    ValueError
        If `limit` > `max_limit`, `limit` < 0, `offset` < 0,
        `max_limit` < 0, `sql` validation fails, or `sql` contains
        semicolons.
    sqlite3.Error
        Any database error is propagated (not swallowed).

    Examples
    --------
    >>> from db_helpers import fetch_page, DEFAULT_MAX_LIMIT
    >>> conn = sqlite3.connect(':memory:')
    >>> conn.execute('CREATE TABLE t (x int)')
    >>> conn.executemany('INSERT INTO t VALUES (?)', [(i,) for i in range(10)])
    >>> rows = fetch_page(conn, 'SELECT x FROM t', limit=3, offset=2)
    >>> [row[0] for row in rows]
    [2, 3, 4]
    """
    # --- Input validation (defensive) -------------------------------------------------
    if not isinstance(conn, sqlite3.Connection):
        raise TypeError(
            f"Expected sqlite3.Connection, got {type(conn).__name__}"
        )

    # Check that connection is not closed (best-effort)
    try:
        conn.execute("SELECT 1")
    except sqlite3.ProgrammingError as e:
        raise TypeError("Connection is closed or invalid.") from e

    if not isinstance(sql, str):
        raise TypeError(f"Expected str for sql, got {type(sql).__name__}")
    if not isinstance(params, tuple):
        raise TypeError(f"Expected tuple for params, got {type(params).__name__}")

    if not isinstance(limit, int):
        raise TypeError(f"Expected int for limit, got {type(limit).__name__}")
    if not isinstance(offset, int):
        raise TypeError(f"Expected int for offset, got {type(offset).__name__}")
    if not isinstance(max_limit, int):
        raise TypeError(f"Expected int for max_limit, got {type(max_limit).__name__}")

    if limit < 0:
        raise ValueError(f"limit must be >= 0, got {limit}")
    if offset < 0:
        raise ValueError(f"offset must be >= 0, got {offset}")
    if max_limit < 0:
        raise ValueError(f"max_limit must be >= 0, got {max_limit}")
    if limit > max_limit:
        raise ValueError(f"limit ({limit}) exceeds max_limit ({max_limit})")

    # --- Validate SQL structure (security) --------------------------------------------
    _validate_sql(sql)

    # --- Append LIMIT and OFFSET --------------------------------------------------------
    # Parameterised placeholders prevent SQL injection.
    if offset > 0:
        bounded_sql = f"{sql.rstrip(';')} LIMIT ? OFFSET ?"
        bounded_params: Tuple[Any, ...] = params + (limit, offset)
    else:
        bounded_sql = f"{sql.rstrip(';')} LIMIT ?"
        bounded_params = params + (limit,)

    # --- Execute ------------------------------------------------------------------------
    logger.debug(
        "Bounded query: limit=%d, offset=%d, max_limit=%d, sql_truncated=%r",
        limit,
        offset,
        max_limit,
        sql[:200],
    )
    try:
        cursor = conn.execute(bounded_sql, bounded_params)
        rows: List[sqlite3.Row] = cursor.fetchall()
        logger.debug("Query returned %d rows", len(rows))
        return rows
    except sqlite3.Error:
        logger.exception("Database error in bounded query")
        raise