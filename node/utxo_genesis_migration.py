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


def compute_genesis_tx_id(miner_id: str) -> str:
    """Deterministic transaction ID for a genesis box."""
    return hashlib.sha256(
        (GENESIS_TX_PREFIX + miner_id).encode('utf-8')
    ).hexdigest()


def load_account_balances(db_path: str) -> list:
    """
    Load non-zero balances from the account model.
    Returns sorted list of (miner_id, amount_i64) tuples.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT miner_id, amount_i64
               FROM balances
               WHERE amount_i64 > 0
               ORDER BY miner_id ASC"""
        ).fetchall()
        return [(r['miner_id'], r['amount_i64']) for r in rows]
    except sqlite3.OperationalError:
        # Try alternate column names
        rows = conn.execute(
            """SELECT miner_pk AS miner_id,
                      CAST(balance_rtc * 100000000 AS INTEGER) AS amount_i64
               FROM balances
               WHERE balance_rtc > 0
               ORDER BY miner_pk ASC"""
        ).fetchall()
        return [(r['miner_id'], r['amount_i64']) for r in rows]
    finally:
        conn.close()


def check_existing_genesis(utxo_db: UtxoDB) -> bool:
    """Check if genesis boxes already exist."""
    conn = utxo_db._conn()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM utxo_boxes WHERE creation_height = ?",
            (GENESIS_HEIGHT,),
        ).fetchone()
        return row['n'] > 0
    finally:
        conn.close()


def migrate(db_path: str, dry_run: bool = False) -> dict:
    """
    Run the genesis migration.

    Returns dict with:
        wallets_migrated, total_nrtc, state_root, boxes_created
    """
    utxo_db = UtxoDB(db_path)
    utxo_db.init_tables()

    # Safety check
    if check_existing_genesis(utxo_db):
        print("ERROR: Genesis boxes already exist. Aborting.")
        print("To re-run, first delete genesis boxes:")
        print(f"  DELETE FROM utxo_boxes WHERE creation_height = {GENESIS_HEIGHT};")
        return {'error': 'genesis_already_exists'}

    # Load balances
    balances = load_account_balances(db_path)
    if not balances:
        print("WARNING: No non-zero balances found.")
        return {'error': 'no_balances'}

    total_account = sum(amt for _, amt in balances)

    print(f"Found {len(balances)} wallets with non-zero balance")
    print(f"Total account balance: {total_account} nrtc ({total_account / UNIT:.6f} RTC)")
    print()

    if dry_run:
        print("=== DRY RUN — computing what would be created ===")
        print()

    # Create genesis boxes
    conn = utxo_db._conn()
    now = int(time.time())
    boxes_created = 0

    try:
        if not dry_run:
            conn.execute("BEGIN IMMEDIATE")

        for miner_id, amount_i64 in balances:
            tx_id = compute_genesis_tx_id(miner_id)
            prop = address_to_proposition(miner_id)
            box_id = compute_box_id(
                amount_i64, prop, GENESIS_HEIGHT, tx_id, 0
            )

            if dry_run:
                print(f"  {miner_id:40s} | {amount_i64 / UNIT:>14.6f} RTC | box={box_id[:16]}...")
            else:
                # Insert box
                conn.execute(
                    """INSERT INTO utxo_boxes
                       (box_id, value_nrtc, proposition, owner_address,
                        creation_height, transaction_id, output_index,
                        tokens_json, registers_json, created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (
                        box_id, amount_i64, prop, miner_id,
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
                            'value_nrtc': amount_i64,
                            'owner': miner_id,
                        }]),
                        '[]', 0, now, GENESIS_HEIGHT, 'confirmed',
                    ),
                )

            boxes_created += 1

        if not dry_run:
            conn.execute("COMMIT")

    except Exception as e:
        if not dry_run:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
        print(f"ERROR: Migration failed: {e}")
        raise
    finally:
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
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("BEGIN IMMEDIATE")

        # Prevent rollback if any genesis boxes have already been spent
        spent_count = conn.execute(
            """SELECT COUNT(b.box_id) AS n
               FROM utxo_boxes b
               JOIN utxo_transactions t ON b.transaction_id = t.tx_id
               WHERE t.tx_type = 'genesis' AND b.spent_at IS NOT NULL"""
        ).fetchone()['n']
        if spent_count > 0:
            raise ValueError("Cannot rollback genesis: some genesis boxes have already been spent.")

        # Delete genesis boxes first (child table)
        deleted = conn.execute(
            """DELETE FROM utxo_boxes
               WHERE transaction_id IN (
                   SELECT tx_id FROM utxo_transactions WHERE tx_type = 'genesis'
               )"""
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
