import sys
from pathlib import Path


NODE_DIR = Path(__file__).resolve().parents[1]
if str(NODE_DIR) not in sys.path:
    sys.path.insert(0, str(NODE_DIR))

from utxo_db import MAX_SQLITE_INT64, UtxoDB  # noqa: E402


class TrackingConnection:
    def __init__(self, conn):
        self.conn = conn
        self.statements = []

    @property
    def in_transaction(self):
        return self.conn.in_transaction

    def execute(self, sql, *args, **kwargs):
        self.statements.append(" ".join(str(sql).split()).upper())
        return self.conn.execute(sql, *args, **kwargs)

    def commit(self):
        self.statements.append("COMMIT")
        return self.conn.commit()

    def close(self):
        # Keep the connection open so the test can inspect transaction state.
        self.statements.append("CLOSE")

    def really_close(self):
        return self.conn.close()


def test_mempool_add_rolls_back_invalid_timestamp_before_close(tmp_path):
    db = UtxoDB(str(tmp_path / "utxo.db"))
    db.init_tables()

    original_conn = db._conn
    tracked = TrackingConnection(original_conn())
    calls = 0

    def conn_factory():
        nonlocal calls
        calls += 1
        if calls == 1:
            return original_conn()
        return tracked

    db._conn = conn_factory
    try:
        ok = db.mempool_add(
            {
                "tx_id": "bad-timestamp",
                "inputs": [{"box_id": "box-a"}],
                "outputs": [{"address": "bob", "value_nrtc": 100_000_000}],
                "fee_nrtc": 0,
                "timestamp": MAX_SQLITE_INT64 + 1,
            }
        )

        assert ok is False
        assert any(statement == "ROLLBACK" for statement in tracked.statements)
        assert tracked.in_transaction is False
        assert tracked.statements.index("ROLLBACK") < tracked.statements.index("CLOSE")
    finally:
        tracked.really_close()
