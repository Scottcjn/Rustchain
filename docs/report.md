"""
node/db_helpers.py – Bounded query utilities for SQLite access.

This module provides safe, governed ways to execute bounded SELECT queries
against a sqlite3 connection. It is intended to replace all raw .fetchall()
calls that process attacker-influenced rows, preventing unbounded memory
allocation (OOM-DoS).

All functions enforce an explicit maximum row limit and validate that the
supplied SQL does not already contain LIMIT, TOP, or OFFSET clauses.

Security notice:
    This helper is **not** a full SQL injection prevention mechanism.
    It mitigates OOM-DoS by bounding result rows. Parameterized queries
    (via `?` placeholders) are still required to prevent injection.
    Additionally, the module does not allow multiple statements in a single
    SQL string.

Usage example:
    from db_helpers import fetch_page
    rows = fetch_page(conn, "SELECT * FROM txs WHERE status = ?",
                      params=(status,), limit=100)
"""

from __future__ import annotations

import logging
import re
from typing import Any, List, Sequence, Union

import sqlite3

# ---------------------------------------------------------------------------
# Module-level logger
# ---------------------------------------------------------------------------
_logger: logging.Logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_DEFAULT_MAX_LIMIT: int = 1000
"""Default maximum number of rows that may be returned by a single query."""

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
__all__ = [
    "fetch_page",
    "validate_query",
    "is_safe_select",
    "DEFAULT_MAX_LIMIT",
]

# ---------------------------------------------------------------------------
# Validation patterns
# ---------------------------------------------------------------------------
# Pattern to detect any existing LIMIT, TOP, or OFFSET clause (case-insensitive).
# This is a heuristic; for full correctness a real SQL parser would be needed.
_EXISTING_LIMIT_PATTERN: re.Pattern = re.compile(
    r"""
    \b
    (?:
        LIMIT\s+\d+                 # `LIMIT <number>`
        | TOP\s+\d+                 # `TOP <number>` (non-SQLite)
        | OFFSET\s+\d+              # `OFFSET <number>`
    )
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Pattern to detect dangerous SQL statements (non-SELECT, DML, DDL, comments)
_DANGEROUS_SQL_PATTERN: re.Pattern = re.compile(
    r"""
    \b
    (?:
        INSERT\b
        | UPDATE\b
        | DELETE\b
        | DROP\b
        | ALTER\b
        | CREATE\b
        | EXEC\b
        | EXECUTE\b
        | --[^\n]*                  # inline comment
        | /\*.*?\*/                 # block comment (non-greedy)
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

_SELECT_START_PATTERN: re.Pattern = re.compile(r"^\s*SELECT\b", re.IGNORECASE)
_MULTI_STATEMENT_PATTERN: re.Pattern = re.compile(r";\s*\S", re.DOTALL)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_connection(conn: sqlite3.Connection) -> None:
    """Ensure `conn` is a valid sqlite3.Connection.

    Raises
    ------
    TypeError
        If `conn` is not a sqlite3.Connection.
    """
    if not isinstance(conn, sqlite3.Connection):
        raise TypeError(
            f"Expected sqlite3.Connection, got {type(conn).__name__}"
        )

def _validate_limit_params(limit: int, offset: int, max_limit: int) -> None:
    """Validate limit, offset, and max_limit values.

    Raises
    ------
    ValueError
        If any parameter is invalid.
    """
    if not isinstance(limit, int) or limit < 0:
        raise ValueError("limit must be a non-negative integer")
    if not isinstance(offset, int) or offset < 0:
        raise ValueError("offset must be a non-negative integer")
    if not isinstance(max_limit, int) or max_limit < 1:
        raise ValueError("max_limit must be a positive integer")
    if limit > max_limit:
        raise ValueError(
            f"Requested limit {limit} exceeds max_limit {max_limit}. "
            "Increase max_limit only after explicit security review."
        )

def _check_existing_limit(sql: str) -> None:
    """Check if the SQL already contains LIMIT, TOP, or OFFSET.

    Raises
    ------
    ValueError
        If any such clause is found.
    """
    if _EXISTING_LIMIT_PATTERN.search(sql):
        raise ValueError(
            "The supplied SQL must not contain LIMIT, TOP, or OFFSET. "
            "Use the 'limit' / 'offset' parameters instead."
        )

def _check_dangerous_sql(sql: str) -> None:
    """Check for dangerous constructs in the SQL.

    Raises
    ------
    ValueError
        If a dangerous construct is found.
    """
    if _DANGEROUS_SQL_PATTERN.search(sql):
        raise ValueError(
            "The supplied SQL must not contain INSERT, UPDATE, DELETE, DDL, "
            "or comments. Only SELECT is allowed."
        )

# ---------------------------------------------------------------------------
# Public validation functions
# ---------------------------------------------------------------------------

def validate_query(sql: str) -> None:
    """Validate a SQL statement for use with bounded helpers.

    Raises
    ------
    ValueError
        If SQL is empty, does not start with SELECT, contains multiple
        statements, or already contains LIMIT, TOP, OFFSET, or other
        dangerous clauses.

    Parameters
    ----------
    sql : str
        The SQL statement to validate.
    """
    if not sql or not sql.strip():
        raise ValueError("SQL statement must not be empty.")

    if not _SELECT_START_PATTERN.match(sql):
        raise ValueError("Only SELECT queries are allowed.")

    if _MULTI_STATEMENT_PATTERN.search(sql):
        raise ValueError("Multiple SQL statements are not allowed.")

    _check_existing_limit(sql)
    _check_dangerous_sql(sql)

def is_safe_select(sql: str) -> bool:
    """Return True if `sql` is a valid SELECT without existing limits or dangers.

    This is a convenience wrapper around `validate_query` that does not raise.

    Parameters
    ----------
    sql : str
        The SQL statement to validate.

    Returns
    -------
    bool
        True if the statement is safe for bounded execution.
    """
    try:
        validate_query(sql)
        return True
    except ValueError:
        return False

# ---------------------------------------------------------------------------
# Core bounded query function
# ---------------------------------------------------------------------------

def fetch_page(
    conn: sqlite3.Connection,
    sql: str,
    params: Sequence[Any] = (),
    *,
    limit: int,
    offset: int = 0,
    max_limit: int = _DEFAULT_MAX_LIMIT,
) -> List[sqlite3.Row]:
    """Execute a bounded SELECT query and return at most `max_limit` rows.

    This function is the safe replacement for raw ``.fetchall()`` calls on
    public or semi-public endpoints where the result set can be influenced
    by an attacker.  It enforces an explicit row limit and raises exceptions
    before any database call if the request is invalid.

    Parameters
    ----------
    conn : sqlite3.Connection
        An open SQLite connection.
    sql : str
        A SELECT SQL statement (case-insensitive). Must **not** already
        contain a LIMIT, TOP, or OFFSET clause; doing so raises ValueError.
    params : sequence of any, optional
        Parameters for the SQL query (``?`` placeholders). Defaults to empty
        tuple. Accepts any iterable (list, tuple, etc.).
    limit : int, keyword-only
        Desired row limit (must be 0 <= limit <= max_limit).
    offset : int, keyword-only, default 0
        Row offset (must be >= 0).
    max_limit : int, keyword-only, default 1000
        Absolute maximum number of rows that may be returned in a single
        call.  Raising this value should be the exception and requires
        explicit security review.

    Returns
    -------
    list of sqlite3.Row
        The resulting rows, never more than *max_limit*.

    Raises
    ------
    TypeError
        If `conn` is not a sqlite3.Connection.
    ValueError
        If validation fails (e.g., *limit* > *max_limit*, *offset* < 0,
        *sql* contains existing LIMIT/TOP/OFFSET, or *sql* is not SELECT).
    sqlite3.DatabaseError
        For any database-level error (e.g., syntax error, constraint failure).
    sqlite3.InterfaceError
        If the number of parameters does not match the placeholders.
    sqlite3.ProgrammingError
        If the SQL is malformed or other programming error.

    Examples
    --------
    >>> rows = fetch_page(conn, "SELECT * FROM txs WHERE status = ?",
    ...                   params=(status,), limit=100, offset=0)
    """
    # -------------------------------------------------------------------
    # Input validation (raises on failure)
    # -------------------------------------------------------------------
    _validate_connection(conn)
    _validate_limit_params(limit, offset, max_limit)

    # Validate SQL (raises on failure)
    validate_query(sql)

    # -------------------------------------------------------------------
    # Build the bounded query
    # -------------------------------------------------------------------
    bounded_sql = f"{sql.strip()} LIMIT ? OFFSET ?"
    bounded_params = list(params) + [limit, offset]

    # -------------------------------------------------------------------
    # Execute with a cursor, ensuring proper cleanup
    # -------------------------------------------------------------------
    try:
        cursor = conn.execute(bounded_sql, bounded_params)
        # Fetch results; the SQL-level LIMIT ensures ≤ limit rows, but we
        # add an additional safety cap (should never be needed).
        rows = cursor.fetchmany(limit) if limit > 0 else []
        # If limit == 0, return empty (fetchmany with 0 returns all, so special-case)
    except sqlite3.Error as exc:
        _logger.error(
            "SQLite error during fetch_page (limit=%d, offset=%d, max_limit=%d): %s",
            limit, offset, max_limit, exc,
        )
        raise
    finally:
        # Cursor is automatically closed by connection context when using `with`,
        # but here we use `conn.execute` which returns a cursor that is not
        # automatically closed in older Python versions. Force close.
        try:
            cursor.close()
        except (sqlite3.Error, AttributeError):
            pass

    # -------------------------------------------------------------------
    # Log success for auditability
    # -------------------------------------------------------------------
    _logger.debug(
        "fetch_page returned %d rows (limit=%d, offset=%d, max_limit=%d)",
        len(rows), limit, offset, max_limit,
    )

    return rows