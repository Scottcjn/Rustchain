"""Canonical epoch-settlement claim (Rustchain#6749).

``finalize_epoch`` (node/rustchain_v2_integrated_v2.2.1_rip200.py),
``settle_epoch_rip200`` (node/rewards_implementation_rip200.py) and
``settle_epoch_with_anti_double_mining`` (node/anti_double_mining.py) are three
independent settlement paths that can each credit the same epoch. Each one had
already, independently, arrived at the same fix for its own internal race
(concurrent calls to *itself*) — an atomic ``INSERT ... ON CONFLICT DO NOTHING``
followed by ``UPDATE epoch_state SET settled = 1 ... WHERE settled = 0``, whose
``rowcount`` tells the caller whether it won the claim. Because all three read
and write the *same* ``epoch_state.settled`` row for a given epoch under a
``BEGIN IMMEDIATE`` write lock, that duplicated pattern already closes the
CROSS-path race too (SQLite serializes writers on the same DB file) — but
having it hand-copied three times (plus a fourth copy in
``node/tests/test_epoch_settlement_atomic.py``) is exactly the "no canonical
entrypoint" gap Rustchain#6749 flagged: any future settlement path that
doesn't know to copy the same two statements reintroduces the race.

This module exists so there is exactly one implementation to import, not one
to copy. It intentionally does NOT open a connection, does NOT call
``BEGIN``/``COMMIT``/``ROLLBACK``, and does NOT decide what "already settled"
means for the caller (that stays local -- some callers roll back cleanly on a
lost claim, ``settle_epoch_with_anti_double_mining`` falls through to a
``SELECT`` to confirm *why* rowcount was 0). All three existing call sites
already run inside their own ``BEGIN IMMEDIATE``; this function just is the
one place the two SQL statements live.
"""

import sqlite3
import time
from typing import Optional


def claim_epoch(conn: sqlite3.Connection, epoch: int, *, now: Optional[int] = None) -> bool:
    """Atomically claim settlement rights for ``epoch`` on ``conn``.

    MUST be called from inside a transaction that already holds a write lock
    on the database (``BEGIN IMMEDIATE`` or equivalent) -- this function does
    not manage the transaction itself, matching how every existing call site
    already wraps its own ``BEGIN``/``COMMIT``/``ROLLBACK`` around it.

    Returns ``True`` if this call won the claim (the caller must proceed to
    credit rewards and is responsible for committing). Returns ``False`` if
    the epoch was already settled by a prior winner (own-path or cross-path)
    -- the caller must NOT credit anything.
    """
    if now is None:
        now = int(time.time())
    conn.execute(
        "INSERT INTO epoch_state (epoch, settled) VALUES (?, 0) "
        "ON CONFLICT(epoch) DO NOTHING",
        (epoch,),
    )
    claim = conn.execute(
        "UPDATE epoch_state SET settled = 1, settled_ts = ? WHERE epoch = ? AND settled = 0",
        (now, epoch),
    )
    return claim.rowcount == 1
