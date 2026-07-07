# SPDX-License-Identifier: MIT
"""Canonical "encumbered funds" reader.

Spendable balance for any debit gate is:

    available = balances.amount_i64  -  encumbered_i64(cursor, wallet)

`encumbered_i64` is the single source of truth for funds that are committed to
an in-flight operation but have NOT yet left `balances.amount_i64`:

  * pending_ledger transfers awaiting confirmation — the 2-phase payout window
    is a reservation: the sender is only debited at CONFIRM, so until then the
    funds must be treated as unavailable to every other debit path.
  * bridge deposits that have not yet been hard-debited (source_debited = 0) —
    i.e. a legacy/in-flight deposit the debit-on-lock migration could not yet
    settle. Bridge deposits under debit-on-lock (source_debited = 1) have
    ALREADY left amount_i64 and must NOT be counted again (double-count).

The live RTC-debiting gate that reads raw amount_i64 is the withdrawal path; it
subtracts this so reserved funds cannot be drained out from under a pending
operation. (The transfer-create paths already self-limit on pending_ledger; the
live governance propose check is a non-debiting minimum-balance gate, so it does
not move funds and is not a drain vector.) Any future raw-balance debit gate
should subtract this too.

The balances table itself is schema-variant (miner_id vs miner_pk); callers keep
their own balance read and only share this stable encumbrance computation. The
encumbrance tables have fixed column names.
"""

import sqlite3


def encumbered_i64(cursor, wallet_id) -> int:
    """Return total **micro-RTC (int)** reserved by in-flight ops not yet debited.

    Callers must subtract this in the SAME unit as their balance read (i64 for
    the withdrawal path; divide by 1e6 for an RTC-float caller), and must read
    it inside the SAME transaction (e.g. BEGIN IMMEDIATE) as the balance read
    and the debit, so the check-then-debit is atomic (no TOCTOU). Raises
    sqlite3.OperationalError on a real DB error (locked/busy/IO) — i.e. fails
    closed; the caller must treat that as "do not debit", not "zero encumbered".
    """
    total = 0

    try:
        row = cursor.execute(
            "SELECT COALESCE(SUM(amount_i64), 0) FROM pending_ledger "
            "WHERE from_miner = ? AND status IN ('pending', 'confirming')",
            (wallet_id,),
        ).fetchone()
        total += int(row[0]) if row and row[0] else 0
    except sqlite3.OperationalError as exc:
        # Fail CLOSED: only the missing-table compatibility case is benign. A
        # real error (locked/busy/I/O) must propagate so the debit gate aborts
        # rather than treating reserved funds as spendable.
        if "no such table" not in str(exc).lower():
            raise

    # Bridge deposits not yet hard-debited. Prefer the source_debited filter
    # (debit-on-lock); count NULL as un-debited too. If the column is absent
    # (bridge still on the legacy reservation model) NONE are debited yet, so
    # count ALL active deposits rather than treating them as spendable.
    try:
        row = cursor.execute(
            "SELECT COALESCE(SUM(amount_i64), 0) FROM bridge_transfers "
            "WHERE source_address = ? AND direction = 'deposit' "
            "AND status IN ('pending', 'locked', 'confirming') "
            "AND (source_debited = 0 OR source_debited IS NULL)",
            (wallet_id,),
        ).fetchone()
        total += int(row[0]) if row and row[0] else 0
    except sqlite3.OperationalError as exc:
        msg = str(exc).lower()
        if "no such column" in msg:
            # Legacy bridge schema (no source_debited): nothing is hard-debited,
            # so all active deposits are encumbered.
            try:
                row = cursor.execute(
                    "SELECT COALESCE(SUM(amount_i64), 0) FROM bridge_transfers "
                    "WHERE source_address = ? AND direction = 'deposit' "
                    "AND status IN ('pending', 'locked', 'confirming')",
                    (wallet_id,),
                ).fetchone()
                total += int(row[0]) if row and row[0] else 0
            except sqlite3.OperationalError as exc2:
                if "no such table" not in str(exc2).lower():
                    raise
        elif "no such table" not in msg:
            raise  # real error -> fail closed

    return total
