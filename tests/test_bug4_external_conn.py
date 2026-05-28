"""Regression test: BUG-4 stale eviction must work via external-connection path.

The utxo_endpoints.py transfer endpoint opens BEGIN IMMEDIATE on its own
connection, then calls apply_transaction(conn=outer_conn). The eviction must
run on that same connection inside the transaction.
"""
import json, time, sqlite3, pytest
from node.utxo_db import UtxoDB


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "test_utxo.db")
    instance = UtxoDB(db_path)
    instance.init_tables()
    return instance


def _mint(db, addr, value, height=1):
    """Mint a box and return its box_id."""
    result = db.apply_transaction({
        "tx_type": "mining_reward",
        "inputs": [],
        "outputs": [{"address": addr, "value_nrtc": value}],
        "fee_nrtc": 0,
        "data_inputs": [],
        "_allow_minting": True,
    }, block_height=height)
    assert result, "minting failed"
    conn = db._conn()
    try:
        row = conn.execute(
            "SELECT box_id FROM utxo_boxes WHERE owner_address=? AND spent_at IS NULL ORDER BY box_id ASC LIMIT 1",
            (addr,),
        ).fetchone()
    finally:
        conn.close()
    assert row, f"no box for {addr}"
    return row["box_id"]


def _add_mempool_tx_with_data_input(db, tx_id, input_box_ids, data_input_box_ids, fee=100):
    """Directly insert a mempool tx with data_inputs in tx_data_json."""
    now = int(time.time())
    tx_data = {
        "tx_id": tx_id,
        "data_inputs": data_input_box_ids,
    }
    conn = db._conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO utxo_mempool (tx_id, tx_data_json, fee_nrtc, expires_at, submitted_at) VALUES (?,?,?,?,?)",
            (tx_id, json.dumps(tx_data), fee, now + 3600, now),
        )
        for bid in input_box_ids:
            conn.execute(
                "INSERT INTO utxo_mempool_inputs (box_id, tx_id) VALUES (?,?)",
                (bid, tx_id),
            )
        conn.commit()
    finally:
        conn.close()


class TestExternalConnEvictionBug4:
    """BUG-4 fix: stale eviction must work when apply_transaction() is called
    with an external connection (the utxo_endpoints.py transfer pattern)."""

    def test_stale_data_input_tx_evicted_via_external_conn(self, db):
        """Stale mempool tx referencing a spent box via data_input must be
        evicted even when the spend happens via an external connection
        (BEGIN IMMEDIATE on outer, apply_transaction(conn=outer), COMMIT)."""
        # 1. Mint two boxes
        box_a = _mint(db, "alice", 10000)
        box_b = _mint(db, "bob", 20000, height=2)

        # 2. Add mempool tx that uses box_a as data_input
        _add_mempool_tx_with_data_input(
            db, "tx_stale_di", [box_b], [box_a], fee=50
        )

        # Verify tx is in mempool
        conn = db._conn()
        try:
            row = conn.execute(
                "SELECT tx_id FROM utxo_mempool WHERE tx_id=?", ("tx_stale_di",)
            ).fetchone()
        finally:
            conn.close()
        assert row is not None, "stale tx should be in mempool"

        # 3. Spend box_a via EXTERNAL CONNECTION path
        outer = sqlite3.connect(db.db_path)
        outer.row_factory = sqlite3.Row
        outer.execute("BEGIN IMMEDIATE")

        ok = db.apply_transaction({
            "tx_type": "transfer",
            "inputs": [{"box_id": box_a, "spending_proof": "p2"}],
            "outputs": [{"address": "carol", "value_nrtc": 9900}],
            "fee_nrtc": 100,
            "data_inputs": [],
            "_allow_mempool_override": True,
        }, block_height=3, conn=outer)

        outer.execute("COMMIT")
        outer.close()
        assert ok, "apply_transaction via external conn failed"

        # 4. Verify stale tx was evicted
        conn = db._conn()
        try:
            mp = conn.execute(
                "SELECT tx_id FROM utxo_mempool WHERE tx_id=?", ("tx_stale_di",)
            ).fetchone()
            inp = conn.execute(
                "SELECT tx_id FROM utxo_mempool_inputs WHERE tx_id=?", ("tx_stale_di",)
            ).fetchone()
        finally:
            conn.close()
        assert mp is None, "BUG-4: stale tx should be evicted via external-conn path"
        assert inp is None, "BUG-4: stale input rows should be cleaned up"

    def test_stale_regular_input_tx_evicted_via_external_conn(self, db):
        """Stale mempool tx claiming a spent box as regular input must be
        evicted via the external-connection path."""
        box_a = _mint(db, "alice", 10000)

        # Add mempool tx claiming box_a
        _add_mempool_tx_with_data_input(
            db, "tx_stale_reg", [box_a], [], fee=50
        )

        # Spend box_a via external connection
        outer = sqlite3.connect(db.db_path)
        outer.row_factory = sqlite3.Row
        outer.execute("BEGIN IMMEDIATE")

        ok = db.apply_transaction({
            "tx_type": "transfer",
            "inputs": [{"box_id": box_a, "spending_proof": "p2"}],
            "outputs": [{"address": "carol", "value_nrtc": 9900}],
            "fee_nrtc": 100,
            "data_inputs": [],
            "_allow_mempool_override": True,
        }, block_height=2, conn=outer)

        outer.execute("COMMIT")
        outer.close()
        assert ok

        # Verify eviction
        conn = db._conn()
        try:
            mp = conn.execute(
                "SELECT tx_id FROM utxo_mempool WHERE tx_id=?", ("tx_stale_reg",)
            ).fetchone()
        finally:
            conn.close()
        assert mp is None, "stale tx with regular input should be evicted"

    def test_own_conn_eviction_still_works(self, db):
        """Regression guard: own-connection (manage_tx=True) path still
        evicts stale txs after the fix."""
        box_a = _mint(db, "alice", 10000)
        box_b = _mint(db, "bob", 20000, height=2)

        _add_mempool_tx_with_data_input(
            db, "tx_stale_own", [box_b], [box_a], fee=50
        )

        # Own-connection path (no conn=... argument)
        ok = db.apply_transaction({
            "tx_type": "transfer",
            "inputs": [{"box_id": box_a, "spending_proof": "p2"}],
            "outputs": [{"address": "carol", "value_nrtc": 9900}],
            "fee_nrtc": 100,
            "data_inputs": [],
            "_allow_mempool_override": True,
        }, block_height=3)
        assert ok

        # Verify eviction
        conn = db._conn()
        try:
            mp = conn.execute(
                "SELECT tx_id FROM utxo_mempool WHERE tx_id=?", ("tx_stale_own",)
            ).fetchone()
        finally:
            conn.close()
        assert mp is None, "own-connection eviction should still work"
