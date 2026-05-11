"""
RustChain UTXO Database Layer
=============================

SQLite-backed UTXO set for RustChain's Ergo-compatible extended UTXO model.
Adapted from the design in rips/rustchain-core/ledger/utxo_ledger.py.

Phase 1 of the account-to-UTXO migration: runs alongside the existing
account-based balance system in dual-write mode.

Security properties:
- Atomic transaction application (all inputs spent + all outputs created, or nothing)
- Double-spend prevention via spent_at tracking
- Deterministic Merkle state root for cross-node consensus
- Mempool-level double-spend detection via utxo_mempool_inputs

Architectural boundary -- spending_proof validation:
  The ``spending_proof`` field on transaction inputs is stored but **not
  verified** by this module.  Signature verification (Ed25519 over the
  canonical input box ID + output commitments) is performed at the
  endpoint layer (``utxo_endpoints.py``) before any call to
  ``UtxoDB.apply_transaction()``.  This separation is intentional:
  the UTXO layer is a pure state-transition engine; authentication
  belongs to the caller.  See issue #2085 for the rationale.
"""

import hashlib
import json
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

UNIT = 100_000_000          # 1 RTC = 100,000,000 nanoRTC (8 decimals)
DUST_THRESHOLD = 1_000      # nanoRTC below which change is absorbed into fee
MAX_COINBASE_OUTPUT_NRTC = 150 * 144 * UNIT  # Max minting output per block (1.5 RTC)
MAX_POOL_SIZE = 10_000
MAX_TX_AGE_SECONDS = 3_600  # 1 hour mempool expiry
P2PK_PREFIX = b'\x00\x08'   # Pay-to-Public-Key proposition prefix


# ---------------------------------------------------------------------------
# Box / Transaction helpers (dict-based, not dataclass — keeps it simple)
# ---------------------------------------------------------------------------

def compute_box_id(value_nrtc: int, proposition: str, creation_height: int,
                   transaction_id: str, output_index: int) -> str:
    """Deterministic box ID from contents. Returns hex string."""
    h = hashlib.sha256()
    h.update(value_nrtc.to_bytes(8, 'little'))
    h.update(bytes.fromhex(proposition))
    h.update(creation_height.to_bytes(8, 'little'))
    h.update(bytes.fromhex(transaction_id) if transaction_id else b'\x00' * 32)
    h.update(output_index.to_bytes(2, 'little'))
    return h.hexdigest()


def compute_tx_id(inputs: List[dict], outputs: List[dict],
                  timestamp: int) -> str:
    """Deterministic transaction ID. Returns hex string."""
    h = hashlib.sha256()
    for inp in inputs:
        h.update(bytes.fromhex(inp['box_id']))
    for out in outputs:
        h.update(bytes.fromhex(out['box_id']))
    h.update(timestamp.to_bytes(8, 'little'))
    return h.hexdigest()


def address_to_proposition(address: str) -> str:
    """Convert RustChain wallet address to hex proposition bytes."""
    prop = P2PK_PREFIX + address.encode('utf-8')
    return prop.hex()


def proposition_to_address(prop_hex: str) -> str:
    """Convert hex proposition back to wallet address."""
    raw = bytes.fromhex(prop_hex)
    if raw[:2] == P2PK_PREFIX:
        return raw[2:].decode('utf-8', errors='ignore')
    return f"RTC_UNKNOWN_{prop_hex[:16]}"


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS utxo_boxes (
    box_id TEXT PRIMARY KEY,
    value_nrtc INTEGER NOT NULL,
    proposition TEXT NOT NULL,
    owner_address TEXT NOT NULL,
    creation_height INTEGER NOT NULL,
    transaction_id TEXT NOT NULL,
    output_index INTEGER NOT NULL,
    tokens_json TEXT DEFAULT '[]',
    registers_json TEXT DEFAULT '{}',
    created_at INTEGER NOT NULL,
    spent_at INTEGER,
    spent_by_tx TEXT,
    UNIQUE(transaction_id, output_index)
);

CREATE INDEX IF NOT EXISTS idx_utxo_owner
    ON utxo_boxes(owner_address) WHERE spent_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_utxo_unspent
    ON utxo_boxes(spent_at) WHERE spent_at IS NULL;

CREATE TABLE IF NOT EXISTS utxo_transactions (
    tx_id TEXT PRIMARY KEY,
    tx_type TEXT NOT NULL,
    inputs_json TEXT NOT NULL,
    outputs_json TEXT NOT NULL,
    data_inputs_json TEXT DEFAULT '[]',
    fee_nrtc INTEGER DEFAULT 0,
    timestamp INTEGER NOT NULL,
    block_height INTEGER,
    block_hash TEXT,
    status TEXT DEFAULT 'confirmed'
);

CREATE TABLE IF NOT EXISTS utxo_mempool (
    tx_id TEXT PRIMARY KEY,
    tx_data_json TEXT NOT NULL,
    fee_nrtc INTEGER DEFAULT 0,
    submitted_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS utxo_mempool_inputs (
    box_id TEXT NOT NULL PRIMARY KEY,
    tx_id TEXT NOT NULL,
    FOREIGN KEY (tx_id) REFERENCES utxo_mempool(tx_id)
);
"""


# ---------------------------------------------------------------------------
# UtxoDB
# ---------------------------------------------------------------------------

class UtxoDB:
    """
    SQLite-backed UTXO set with dual-write support.

    All public methods accept an optional ``conn`` parameter.  When provided
    the caller owns the transaction; otherwise a fresh connection is created.

    **Spending-proof boundary:** This module handles UTXO state transitions
    only.  Signature verification is the caller's responsibility.
    ``apply_transaction()`` accepts ``spending_proof`` on inputs for
    storage/recording but never validates it cryptographically.  The endpoint
    layer (see ``utxo_endpoints.py``) performs Ed25519 verification *before*
    calling into this module.  Future maintainers: do not add proof
    verification here -- it would violate the layer separation and create
    redundant checks.  See issue #2085.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path

    # -- connection helpers --------------------------------------------------

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.db_path, timeout=30)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
        return c

    def init_tables(self, conn: Optional[sqlite3.Connection] = None):
        """Create UTXO tables if they don't exist."""
        own = conn is None
        if own:
            conn = self._conn()
        conn.executescript(SCHEMA_SQL)
        if own:
            conn.close()

    # -- box operations ------------------------------------------------------

    def add_box(self, box: dict, conn: Optional[sqlite3.Connection] = None):
        """
        Insert a new unspent box.

        ``box`` keys: box_id, value_nrtc, proposition, owner_address,
        creation_height, transaction_id, output_index,
        tokens_json (opt), registers_json (opt)
        """
        own = conn is None
        if own:
            conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO utxo_boxes
                   (box_id, value_nrtc, proposition, owner_address,
                    creation_height, transaction_id, output_index,
                    tokens_json, registers_json, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    box['box_id'],
                    box['value_nrtc'],
                    box['proposition'],
                    box['owner_address'],
                    box['creation_height'],
                    box['transaction_id'],
                    box['output_index'],
                    box.get('tokens_json', '[]'),
                    box.get('registers_json', '{}'),
                    int(time.time()),
                ),
            )
            if own:
                conn.commit()
        finally:
            if own:
                conn.close()

    def spend_box(self, box_id: str, spent_by_tx: str,
                  conn: Optional[sqlite3.Connection] = None) -> Optional[dict]:
        """
        Mark a box as spent.  Returns the box dict or None if not found.
        Raises ValueError on double-spend attempt.

        When called without an external ``conn``, acquires BEGIN IMMEDIATE
        to prevent TOCTOU races between the SELECT and UPDATE.
        """
        own = conn is None
        if own:
            conn = self._conn()
        try:
            if own:
                conn.execute("BEGIN IMMEDIATE")

            row = conn.execute(
                "SELECT * FROM utxo_boxes WHERE box_id = ?", (box_id,)
            ).fetchone()
            if not row:
                if own:
                    conn.execute("ROLLBACK")
                return None
            if row['spent_at'] is not None:
                if own:
                    conn.execute("ROLLBACK")
                raise ValueError(
                    f"Double-spend attempt: box {box_id[:16]} already spent "
                    f"by tx {row['spent_by_tx'][:16]}"
                )
            updated = conn.execute(
                """UPDATE utxo_boxes
                   SET spent_at = ?, spent_by_tx = ?
                   WHERE box_id = ? AND spent_at IS NULL""",
                (int(time.time()), spent_by_tx, box_id),
            ).rowcount
            if updated != 1:
                # Another connection spent this box between our SELECT
                # and UPDATE — treat as double-spend.
                if own:
                    conn.execute("ROLLBACK")
                raise ValueError(
                    f"Double-spend race: box {box_id[:16]} was spent "
                    f"concurrently"
                )
            if own:
                conn.commit()
            return dict(row)
        except ValueError:
            raise
        except Exception:
            if own:
                try:
                    conn.execute("ROLLBACK")
                except Exception:
                    pass
            raise
        finally:
            if own:
                conn.close()


    def get_box(self, box_id: str) -> Optional[dict]:
        """Get a box by ID (spent or unspent)."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM utxo_boxes WHERE box_id = ?", (box_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_unspent_for_address(self, address: str) -> List[dict]:
        """Get all unspent boxes for an address, ordered by value ASC."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT * FROM utxo_boxes
                   WHERE owner_address = ? AND spent_at IS NULL
                   ORDER BY value_nrtc ASC""",
                (address,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_balance(self, address: str) -> int:
        """Sum of all unspent box values for an address (nanoRTC)."""
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT COALESCE(SUM(value_nrtc), 0) AS total
                   FROM utxo_boxes
                   WHERE owner_address = ? AND spent_at IS NULL""",
                (address,),
            ).fetchone()
            return row['total']
        finally:
            conn.close()

    def count_unspent(self) -> int:
        """Total number of unspent boxes."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM utxo_boxes WHERE spent_at IS NULL"
            ).fetchone()
            return row['n']
        finally:
            conn.close()

    # -- transaction application ---------------------------------------------

    def apply_transaction(self, tx: dict, block_height: int,
                          conn: Optional[sqlite3.Connection] = None) -> bool:
        """
        Atomically apply a transaction: spend inputs, create outputs.

        .. warning::
            This method does **not** verify ``spending_proof``.  Callers
            MUST authenticate the spender (e.g. Ed25519 signature check)
            before calling this method.  See ``utxo_endpoints.py`` for
            the endpoint-level verification.

        ``tx`` keys:
            tx_type: str
            inputs: list of {box_id: str, spending_proof: str}
            outputs: list of {address: str, value_nrtc: int,
                              tokens_json?, registers_json?}
            data_inputs: list of str (box_ids, read-only)
            fee_nrtc: int (default 0)
            timestamp: int (default now)

        Returns True on success, False on validation failure.
        """
        own = conn is None
        if own:
            conn = self._conn()

        manage_tx = own or not conn.in_transaction

        ts = tx.get('timestamp', int(time.time()))
        # NOTE(issue #2085): spending_proof is present on each input dict but
        # is intentionally ignored by this layer.  It is stored for
        # on-chain auditability, but cryptographic verification is the sole
        # responsibility of the caller (utxo_endpoints.py).
        inputs = tx.get('inputs', [])
        outputs = tx.get('outputs', [])
        fee = tx.get('fee_nrtc', 0)
        tx_type = tx.get('tx_type', 'transfer')

        # FIX(#2207): Defense-in-depth guard against mining_reward type confusion.
        # The endpoint layer hardcodes tx_type='transfer', but if any code path
        # passes user-controlled tx_type, an attacker could mint unlimited coins.
        # Only the epoch settlement system should create mining_reward transactions.
        # Require _allow_minting=True (internal flag) to permit mining_reward.
        MINTING_TX_TYPES = {'mining_reward'}
        if tx_type in MINTING_TX_TYPES and not tx.get('_allow_minting'):
            return False

        try:
            if manage_tx:
                conn.execute("BEGIN IMMEDIATE")

            def abort() -> bool:
                if manage_tx:
                    conn.execute("ROLLBACK")
                return False

            # -- reject duplicate input box_ids --------------------------------
            # Keyed on box_id alone (the PK of the UTXO being consumed).
            # Different spending_proof values for the same box_id are still
            # a duplicate — the proof content is irrelevant to dedup.
            # Without this, the same box_id counted twice inflates
            # input_total.  The spend-phase rowcount check catches it
            # today, but only accidentally.  Defense in depth.
            input_box_ids = [i['box_id'] for i in inputs]
            if len(input_box_ids) != len(set(input_box_ids)):
                return abort()

            # -- validate inputs exist and are unspent -----------------------
            input_total = 0
            for inp in inputs:
                row = conn.execute(
                    """SELECT value_nrtc, spent_at FROM utxo_boxes
                       WHERE box_id = ?""",
                    (inp['box_id'],),
                ).fetchone()
                if not row:
                    return abort()
                if row['spent_at'] is not None:
                    return abort()
                input_total += row['value_nrtc']

            # -- conservation check ------------------------------------------
            # Only authorized minting transaction types may have empty inputs.
            # All other transactions must consume at least one input box.
            MINTING_TX_TYPES = {'mining_reward'}
            if not inputs and tx_type not in MINTING_TX_TYPES:
                return abort()

            # CRITICAL FIX: Reject empty outputs to prevent fund destruction
            # Without this check, outputs=[] bypasses conservation law:
            # output_total=0, fee=0 → (0+0) > input_total → False (bypassed)
            # Result: inputs spent, no outputs created → funds destroyed
            if not outputs and tx_type not in MINTING_TX_TYPES:
                return abort()

            output_total = sum(o['value_nrtc'] for o in outputs)

            # Every output must carry a strictly positive value.
            # Without this, a negative-value output lowers output_total,
            # letting an attacker create more value than the inputs hold.
            for o in outputs:
                if not isinstance(o['value_nrtc'], int) or o['value_nrtc'] <= 0:
                    return abort()

            # Cap minting (coinbase) output to prevent unbounded fund creation.
            # Without this, any caller that passes tx_type='mining_reward'
            # can mint arbitrary amounts.
            if tx_type in MINTING_TX_TYPES and output_total > MAX_COINBASE_OUTPUT_NRTC:
                return abort()

            if fee < 0:
                return abort()
            if inputs and (output_total + fee) != input_total:
                return abort()

            # -- compute output box IDs and build tx_id ----------------------
            # We need a preliminary tx_id for box_id computation.
            # Use SHA256(sorted input box_ids + timestamp) as tx seed.
            tx_seed_h = hashlib.sha256()
            for inp in sorted(inputs, key=lambda i: i['box_id']):
                tx_seed_h.update(bytes.fromhex(inp['box_id']))
            tx_seed_h.update(ts.to_bytes(8, 'little'))
            # For coinbase, include tx_type + outputs to differentiate
            if not inputs:
                tx_seed_h.update(tx_type.encode())
                tx_seed_h.update(block_height.to_bytes(8, 'little'))
                for out in outputs:
                    tx_seed_h.update(out['address'].encode())
                    tx_seed_h.update(out['value_nrtc'].to_bytes(8, 'little'))
            tx_id_hex = tx_seed_h.hexdigest()

            # -- assign box_ids to outputs -----------------------------------
            output_records = []
            for idx, out in enumerate(outputs):
                prop = address_to_proposition(out['address'])
                bid = compute_box_id(
                    out['value_nrtc'], prop, block_height, tx_id_hex, idx
                )
                output_records.append({
                    'box_id': bid,
                    'value_nrtc': out['value_nrtc'],
                    'proposition': prop,
                    'owner_address': out['address'],
                    'creation_height': block_height,
                    'transaction_id': tx_id_hex,
                    'output_index': idx,
                    'tokens_json': out.get('tokens_json', '[]'),
                    'registers_json': out.get('registers_json', '{}'),
                })

            # -- spend inputs ------------------------------------------------
            now = int(time.time())
            for inp in inputs:
                updated = conn.execute(
                    """UPDATE utxo_boxes
                       SET spent_at = ?, spent_by_tx = ?
                       WHERE box_id = ? AND spent_at IS NULL""",
                    (now, tx_id_hex, inp['box_id']),
                ).rowcount
                if updated != 1:
                    return abort()

            # -- create outputs ----------------------------------------------
            for rec in output_records:
                conn.execute(
                    """INSERT INTO utxo_boxes
                       (box_id, value_nrtc, proposition, owner_address,
                        creation_height, transaction_id, output_index,
                        tokens_json, registers_json, created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (
                        rec['box_id'], rec['value_nrtc'], rec['proposition'],
                        rec['owner_address'], rec['creation_height'],
                        rec['transaction_id'], rec['output_index'],
                        rec['tokens_json'], rec['registers_json'], now,
                    ),
                )

            # -- record transaction ------------------------------------------
            conn.execute(
                """INSERT INTO utxo_transactions
                   (tx_id, tx_type, inputs_json, outputs_json,
                    data_inputs_json, fee_nrtc, timestamp,
                    block_height, status)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    tx_id_hex,
                    tx_type,
                    json.dumps([{'box_id': i['box_id']} for i in inputs]),
                    json.dumps([{'box_id': r['box_id'],
                                 'value_nrtc': r['value_nrtc'],
                                 'owner': r['owner_address']}
                                for r in output_records]),
                    json.dumps(tx.get('data_inputs', [])),
                    fee,
                    ts,
                    block_height,
                    'confirmed',
                ),
            )

            if manage_tx:
                conn.execute("COMMIT")
            return True

        except Exception:
            try:
                if manage_tx:
                    conn.execute("ROLLBACK")
            except Exception:
                pass
            raise
        finally:
            if own:
                conn.close()

    # -- state root ----------------------------------------------------------

    def compute_state_root(self) -> str:
        """
        Merkle root of all unspent box IDs (hex).

        Deterministic: sorted by box_id, pairwise SHA256.
        All nodes with the same UTXO set produce the same root.

        Odd-layer padding uses a domain-separated sentinel
        (``SHA256(0x01 || last_hash)``) instead of duplicating the last
        element.  This prevents second-preimage ambiguity where sets
        ``[A, B, C]`` and ``[A, B, C, C]`` would otherwise produce
        identical roots.

        The leaf count is also mixed into each leaf hash so the tree
        is bound to a specific UTXO-set cardinality.
        """
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT box_id FROM utxo_boxes
                   WHERE spent_at IS NULL
                   ORDER BY box_id ASC"""
            ).fetchall()

            if not rows:
                return hashlib.sha256(b"empty").hexdigest()

            # Mix element count into leaf hashes to bind tree to cardinality
            count_bytes = len(rows).to_bytes(8, 'little')
            hashes = [
                hashlib.sha256(count_bytes + bytes.fromhex(r['box_id'])).digest()
                for r in rows
            ]

            while len(hashes) > 1:
                if len(hashes) % 2 == 1:
                    # Domain-separated padding — distinguishable from a
                    # real duplicate leaf.
                    hashes.append(
                        hashlib.sha256(b'\x01' + hashes[-1]).digest()
                    )
                hashes = [
                    hashlib.sha256(hashes[i] + hashes[i + 1]).digest()
                    for i in range(0, len(hashes), 2)
                ]

            return hashes[0].hex()
        finally:
            conn.close()

    # -- integrity -----------------------------------------------------------

    def integrity_check(self, expected_total: Optional[int] = None) -> dict:
        """
        Verify UTXO set integrity.

        Returns dict with ok, total_unspent_nrtc, total_unspent_boxes,
        state_root, and optional comparison with expected_total.
        """
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT COALESCE(SUM(value_nrtc), 0) AS total,
                          COUNT(*) AS cnt
                   FROM utxo_boxes WHERE spent_at IS NULL"""
            ).fetchone()
            total = row['total']
            cnt = row['cnt']
            root = self.compute_state_root()

            result = {
                'ok': True,
                'total_unspent_nrtc': total,
                'total_unspent_rtc': total / UNIT,
                'total_unspent_boxes': cnt,
                'state_root': root,
            }

            if expected_total is not None:
                match = total == expected_total
                result['expected_total_nrtc'] = expected_total
                result['models_agree'] = match
                if not match:
                    result['ok'] = False
                    result['diff_nrtc'] = total - expected_total

            return result
        finally:
            conn.close()

    # -- mempool -------------------------------------------------------------

    def mempool_add(self, tx: dict) -> bool:
        """
        Add a transaction to the mempool.
        Validates inputs exist and aren't claimed by another pending TX.
        Returns False if double-spend detected or pool full.
        """
        conn = self._conn()
        # FIX(#2867 C1): mempool_add() always opens its own connection and
        # begins its own BEGIN IMMEDIATE transaction below. The 7 ROLLBACK
        # paths reference manage_tx, which was previously undefined — every
        # ROLLBACK raised NameError, swallowed by the bare-except at the
        # bottom, causing ALL mempool admissions to silently fail in error
        # paths and leak the transaction-in-progress lock.
        manage_tx = True
        try:
            # Check pool size
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM utxo_mempool"
            ).fetchone()
            if row['n'] >= MAX_POOL_SIZE:
                return False

            tx_id = tx.get('tx_id', '')
            # FIX(#2179): Reject empty/whitespace-only tx_id to prevent
            # INSERT OR IGNORE collisions that create orphan input claims.
            if not tx_id or not tx_id.strip():
                return False

            inputs = tx.get('inputs', [])
            tx_type = tx.get('tx_type', 'transfer')
            now = int(time.time())

            # Public mempool admission must never accept minting transactions.
            # Coinbase/mining rewards are internally constructed during block
            # production and guarded by apply_transaction(_allow_minting=True).
            # Admitting user-supplied mining_reward txs here lets invalid mint
            # candidates occupy mempool slots and reach block candidate selection.
            MINTING_TX_TYPES = {'mining_reward'}
            if tx_type in MINTING_TX_TYPES:
                return False

            if not inputs:
                return False

            conn.execute("BEGIN IMMEDIATE")

            # Check for double-spend in mempool
            for inp in inputs:
                existing = conn.execute(
                    "SELECT tx_id FROM utxo_mempool_inputs WHERE box_id = ?",
                    (inp['box_id'],),
                ).fetchone()
                if existing:
                    if manage_tx:
                        conn.execute("ROLLBACK")
                    return False

                # Check box exists and is unspent
                box = conn.execute(
                    """SELECT spent_at FROM utxo_boxes
                       WHERE box_id = ? AND spent_at IS NULL""",
                    (inp['box_id'],),
                ).fetchone()
                if not box:
                    if manage_tx:
                        conn.execute("ROLLBACK")
                    return False

            # -- conservation-of-value check ---------------------------------
            # Prevent mempool admission of transactions that would fail
            # apply_transaction(), locking UTXOs until expiry (DoS vector).
            fee = tx.get('fee_nrtc', 0)
            if fee < 0:
                if manage_tx:
                        conn.execute("ROLLBACK")
                return False

            # MEDIUM FIX: Reject empty outputs to prevent DoS
            outputs = tx.get('outputs', [])
            if not outputs and tx_type not in MINTING_TX_TYPES:
                if manage_tx:
                        conn.execute("ROLLBACK")
                return False

            input_total = 0
            for inp in inputs:
                row = conn.execute(
                    "SELECT value_nrtc FROM utxo_boxes WHERE box_id = ?",
                    (inp['box_id'],),
                ).fetchone()
                if row:
                    input_total += row['value_nrtc']

            outputs = tx.get('outputs', [])

            # FIX(#2179): Mirror apply_transaction() output validation.
            # Reject outputs with missing, non-int, zero, or negative value_nrtc.
            # Without this, unmineable transactions enter the mempool and lock
            # UTXOs until expiry (DoS vector).
            for o in outputs:
                val = o.get('value_nrtc')
                if not isinstance(val, int) or val <= 0:
                    if manage_tx:
                        conn.execute("ROLLBACK")
                    return False

            output_total = sum(o['value_nrtc'] for o in outputs)
            if input_total > 0 and (output_total + fee) != input_total:
                if manage_tx:
                        conn.execute("ROLLBACK")
                return False

            # Insert into mempool
            # FIX(#2179): Use INSERT OR ABORT instead of INSERT OR IGNORE.
            # With IGNORE, a duplicate tx_id silently skips the insert but
            # execution continues to claim inputs — creating orphan entries
            # that lock UTXOs with no corresponding mempool transaction.
            cursor = conn.execute(
                """INSERT OR ABORT INTO utxo_mempool
                   (tx_id, tx_data_json, fee_nrtc, submitted_at, expires_at)
                   VALUES (?,?,?,?,?)""",
                (
                    tx_id,
                    json.dumps(tx),
                    tx.get('fee_nrtc', 0),
                    now,
                    now + MAX_TX_AGE_SECONDS,
                ),
            )

            # Claim inputs
            for inp in inputs:
                conn.execute(
                    "INSERT INTO utxo_mempool_inputs (box_id, tx_id) VALUES (?,?)",
                    (inp['box_id'], tx_id),
                )

            conn.execute("COMMIT")
            return True
        except Exception:
            try:
                if manage_tx:
                        conn.execute("ROLLBACK")
            except Exception:
                pass
            return False
        finally:
            conn.close()

    def mempool_remove(self, tx_id: str):
        """Remove a transaction from the mempool."""
        conn = self._conn()
        try:
            conn.execute(
                "DELETE FROM utxo_mempool_inputs WHERE tx_id = ?", (tx_id,)
            )
            conn.execute(
                "DELETE FROM utxo_mempool WHERE tx_id = ?", (tx_id,)
            )
            conn.commit()
        finally:
            conn.close()

    def mempool_get_block_candidates(self, max_count: int = 100) -> List[dict]:
        """Get highest-fee transactions from mempool for block inclusion."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT tx_data_json FROM utxo_mempool
                   ORDER BY fee_nrtc DESC
                   LIMIT ?""",
                (max_count,),
            ).fetchall()
            return [json.loads(r['tx_data_json']) for r in rows]
        finally:
            conn.close()

    def mempool_clear_expired(self) -> int:
        """Remove expired transactions from mempool. Returns count removed."""
        conn = self._conn()
        try:
            now = int(time.time())
            expired = conn.execute(
                "SELECT tx_id FROM utxo_mempool WHERE expires_at <= ?",
                (now,),
            ).fetchall()
            count = 0
            for row in expired:
                conn.execute(
                    "DELETE FROM utxo_mempool_inputs WHERE tx_id = ?",
                    (row['tx_id'],),
                )
                conn.execute(
                    "DELETE FROM utxo_mempool WHERE tx_id = ?",
                    (row['tx_id'],),
                )
                count += 1
            conn.commit()
            return count
        finally:
            conn.close()

    def mempool_check_double_spend(self, box_id: str) -> bool:
        """Return True if box_id is claimed by a pending mempool TX."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT tx_id FROM utxo_mempool_inputs WHERE box_id = ?",
                (box_id,),
            ).fetchone()
            return row is not None
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Coin selection
# ---------------------------------------------------------------------------

def coin_select(utxos: List[dict], target_nrtc: int
                ) -> Tuple[List[dict], int]:
    """
    Select UTXOs to cover *target_nrtc*.

    Strategy:
    - Smallest-first accumulation (consolidates dust).
    - If input count > 20, restart with largest-first (fewer inputs).
    - Dust change (< DUST_THRESHOLD) absorbed into fee.

    Returns (selected_utxos, change_nrtc).  Empty list if insufficient.
    """
    if not utxos or target_nrtc <= 0:
        return [], 0

    # Attempt 1: smallest-first
    sorted_asc = sorted(utxos, key=lambda u: u['value_nrtc'])
    selected: List[dict] = []
    total = 0
    for u in sorted_asc:
        selected.append(u)
        total += u['value_nrtc']
        if total >= target_nrtc:
            break

    if total < target_nrtc:
        return [], 0  # insufficient funds

    # If too many small inputs, try largest-first
    if len(selected) > 20:
        sorted_desc = sorted(utxos, key=lambda u: u['value_nrtc'], reverse=True)
        selected = []
        total = 0
        for u in sorted_desc:
            selected.append(u)
            total += u['value_nrtc']
            if total >= target_nrtc:
                break
        if total < target_nrtc:
            return [], 0

    change = total - target_nrtc
    if change < DUST_THRESHOLD:
        change = 0  # absorb dust into fee

    return selected, change

