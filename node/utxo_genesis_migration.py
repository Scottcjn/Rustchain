"""
RustChain UTXO Genesis Migration
=================================

Converts existing account-based balances into genesis UTXO boxes.
Deterministic: running on all 4 nodes produces identical state roots.

Usage:
    python3 utxo_genesis_migration.py [--db PATH] [--dry-run]

Rules:
- Sort wallets by miner_id ASC (deterministic ordering)
- One genesis box per wallet with non-zero balance
- transaction_id = SHA256("rustchain_genesis:" + miner_id)
- creation_height = 0 (genesis)
- proposition = P2PK(miner_id)
"""

import argparse
import hashlib
import json
import sqlite3
import sys
import time

from utxo_db import (
    UtxoDB, address_to_proposition, compute_box_id, UNIT,
)

GENESIS_TX_PREFIX = "rustchain_genesis:"
GENESIS_HEIGHT = 0
ACCOUNT_UNIT = 1_000_000  # Account-model amount_i64 is micro-RTC.
ACCOUNT_TO_UTXO_SCALE = UNIT // ACCOUNT_UNIT


def _is_locked_error(exc: Exception) -> bool:
    return isinstance(exc, sqlite3.OperationalError) and "locked" in str(exc).lower()


def _retry_locked(operation, attempts: int = 50, delay_seconds: float = 0.1):
    for attempt in range(attempts):
        try:
            return operation()
        except sqlite3.OperationalError as exc:
            if not _is_locked_error(exc) or attempt == attempts - 1:
                raise
            time.sleep(delay_seconds)


def compute_genesis_tx_id(miner_id: str) -> str:
    """Deterministic transaction ID for a genesis box."""
    return hashlib.sha256(
        (GENESIS_TX_PREFIX + miner_id).encode('utf-8')
    ).hexdigest()


def load_account_balances(db_path: str, conn=None) -> list:
    """
    Load non-zero balances from the account model.
    Returns sorted list of (miner_id, amount_nrtc) tuples.
    """
    own = conn is None
    if own:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT miner_id, amount_i64
               FROM balances
               WHERE amount_i64 > 0
               ORDER BY miner_id ASC"""
        ).fetchall()
        return [
            (r['miner_id'], int(r['amount_i64']) * ACCOUNT_TO_UTXO_SCALE)
            for r in rows
        ]
    except sqlite3.OperationalError:
        # Try alternate column names
        rows = conn.execute(
            """SELECT miner_pk AS miner_id,
                      CAST(balance_rtc * ? AS INTEGER) AS amount_nrtc
               FROM balances
               WHERE balance_rtc > 0
               ORDER BY miner_pk ASC""",
            (UNIT,),
        ).fetchall()
        return [(r['miner_id'], int(r['amount_nrtc'])) for r in rows]
    finally:
        if own:
            conn.close()


def check_existing_genesis(utxo_db: UtxoDB, conn=None) -> bool:
    """Check if genesis migration transactions already exist."""
    own = conn is None
    if own:
        conn = utxo_db._conn()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM utxo_transactions WHERE tx_type = 'genesis'",
        ).fetchone()
        return row['n'] > 0
    finally:
        if own:
            conn.close()


def check_existing_non_genesis_utxo_state(utxo_db: UtxoDB, conn=None) -> bool:
    """Check whether the UTXO tables already contain non-genesis state."""
    own = conn is None
    if own:
        conn = utxo_db._conn()
    try:
        box_row = conn.execute(
            """SELECT COUNT(*) AS n
               FROM utxo_boxes AS b
               LEFT JOIN utxo_transactions AS t ON t.tx_id = b.transaction_id
               WHERE COALESCE(t.tx_type, '') <> 'genesis'"""
        ).fetchone()
        tx_row = conn.execute(
            """SELECT COUNT(*) AS n
               FROM utxo_transactions
               WHERE tx_type <> 'genesis'"""
        ).fetchone()
        return (box_row['n'] + tx_row['n']) > 0
    finally:
        if own:
            conn.close()


def migrate(db_path: str, dry_run: bool = False) -> dict:
    """
    Run the genesis migration.

    Returns dict with:
        wallets_migrated, total_nrtc, state_root, boxes_created
    """
    utxo_db = UtxoDB(db_path)

    if dry_run:
        _retry_locked(utxo_db.init_tables)
        print("=== DRY RUN — computing what would be created ===")
        print()

    # Create genesis boxes
    conn = None
    now = int(time.time())
    boxes_created = 0

    try:
        if not dry_run:
            conn = _retry_locked(utxo_db._conn)
            conn.execute("BEGIN IMMEDIATE")
            utxo_db.init_tables(conn=conn)

        # For real migrations, this check runs under the same write
        # transaction that will insert the genesis boxes.
        if check_existing_genesis(utxo_db, conn=conn):
            if not dry_run:
                conn.execute("ROLLBACK")
            print("ERROR: Genesis boxes already exist. Aborting.")
            print("To re-run, use rollback_genesis() first.")
            return {'error': 'genesis_already_exists'}

        if check_existing_non_genesis_utxo_state(utxo_db, conn=conn):
            if not dry_run:
                conn.execute("ROLLBACK")
            print("ERROR: Non-genesis UTXO state already exists. Aborting.")
            print("Run migration only on an empty UTXO set.")
            return {'error': 'utxo_state_already_exists'}

        # Non-dry-run migrations load balances on the transaction connection
        # so the migrated snapshot is consistent with the acquired lock.
        balances = load_account_balances(db_path, conn=conn)
        if not balances:
            if not dry_run:
                conn.execute("ROLLBACK")
            print("WARNING: No non-zero balances found.")
            return {'error': 'no_balances'}

        total_account = sum(amt for _, amt in balances)

        print(f"Found {len(balances)} wallets with non-zero balance")
        print(f"Total account balance: {total_account} nrtc ({total_account / UNIT:.6f} RTC)")
        print()

        for miner_id, amount_nrtc in balances:
            tx_id = compute_genesis_tx_id(miner_id)
            prop = address_to_proposition(miner_id)
            box_id = compute_box_id(
                amount_nrtc, prop, GENESIS_HEIGHT, tx_id, 0
            )

            if dry_run:
                print(f"  {miner_id:40s} | {amount_nrtc / UNIT:>14.6f} RTC | box={box_id[:16]}...")
            else:
                # Insert box
                conn.execute(
                    """INSERT INTO utxo_boxes
                       (box_id, value_nrtc, proposition, owner_address,
                        creation_height, transaction_id, output_index,
                        tokens_json, registers_json, created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (
                        box_id, amount_nrtc, prop, miner_id,
                        GENESIS_HEIGHT, tx_id, 0,
                        '[]',
                        json.dumps({'R4': 'genesis'}),
                        now,
                    ),
                )

                # Record transaction
                conn.execute(
                    """INSERT INTO utxo_transactions
                       (tx_id, tx_type, inputs_json, outputs_json,
                        data_inputs_json, fee_nrtc, timestamp,
                        block_height, status)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        tx_id, 'genesis',
                        '[]',
                        json.dumps([{
                            'box_id': box_id,
                            'value_nrtc': amount_nrtc,
                            'owner': miner_id,
                        }]),
                        '[]', 0, now, GENESIS_HEIGHT, 'confirmed',
                    ),
                )

            boxes_created += 1

        if not dry_run:
            conn.execute("COMMIT")

    except Exception as e:
        if not dry_run and conn is not None:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
        print(f"ERROR: Migration failed: {e}")
        raise
    finally:
        if conn is not None:
            conn.close()

    # Compute and verify state root
    state_root = utxo_db.compute_state_root()

    # Integrity check
    if not dry_run:
        integrity = utxo_db.integrity_check(expected_total=total_account)
    else:
        integrity = {'ok': True, 'models_agree': True}

    result = {
        'wallets_migrated': boxes_created,
        'total_nrtc': total_account,
        'total_rtc': total_account / UNIT,
        'state_root': state_root,
        'boxes_created': boxes_created,
        'integrity': integrity,
    }

    print()
    print("=" * 60)
    print("GENESIS MIGRATION RESULT")
    print("=" * 60)
    print(f"  Wallets migrated:  {result['wallets_migrated']}")
    print(f"  Total RTC:         {result['total_rtc']:.6f}")
    print(f"  Boxes created:     {result['boxes_created']}")
    print(f"  State root:        {result['state_root']}")
    if not dry_run:
        print(f"  Integrity OK:      {integrity['ok']}")
        print(f"  Models agree:      {integrity.get('models_agree', 'N/A')}")
    print("=" * 60)

    if not dry_run and not integrity['ok']:
        print()
        print("WARNING: Integrity check FAILED!")
        print(f"  UTXO total:    {integrity['total_unspent_nrtc']}")
        print(f"  Account total: {integrity.get('expected_total_nrtc', '?')}")
        print(f"  Diff:          {integrity.get('diff_nrtc', '?')}")

    return result


def rollback_genesis(db_path: str) -> int:
    """Remove all genesis boxes and their transactions atomically.

    Wrapped in a single BEGIN IMMEDIATE transaction so no partial
    deletion state is possible. Idempotent: safe to call when no
    genesis data exists (returns 0).
    """
    utxo_db = UtxoDB(db_path)
    conn = utxo_db._conn()
    try:
        conn.execute("BEGIN IMMEDIATE")

        # Delete only boxes produced by genesis transactions. A non-genesis
        # box can legitimately have creation_height=0.
        deleted = conn.execute(
            """DELETE FROM utxo_boxes
               WHERE transaction_id IN (
                   SELECT tx_id FROM utxo_transactions WHERE tx_type = 'genesis'
               )""",
        ).rowcount

        # Delete genesis transactions (parent table)
        conn.execute(
            "DELETE FROM utxo_transactions WHERE tx_type = 'genesis'"
        )

        conn.execute("COMMIT")
        return deleted

    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='RustChain UTXO Genesis Migration')
    parser.add_argument('--db', default='rustchain_v2.db',
                        help='Path to rustchain_v2.db')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview migration without writing')
    parser.add_argument('--rollback', action='store_true',
                        help='Remove genesis boxes (rollback)')
    args = parser.parse_args()

    if args.rollback:
        rollback_genesis(args.db)
    else:
        result = migrate(args.db, dry_run=args.dry_run)
        if 'error' in result:
            sys.exit(1)
