"""Tests for spend_box rollback style fix (BUG-2 from PR #6146 review)"""
import pytest
from node.utxo_db import UtxoDB

@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "test_utxo.db")
    instance = UtxoDB(db_path)
    instance.init_tables()
    return instance

def _add_box(db, box_id, value=1000, addr="addr1", height=1):
    db.add_box({
        "box_id": box_id,
        "value_nrtc": value,
        "proposition": addr,
        "owner_address": addr,
        "creation_height": height,
        "transaction_id": f"tx_genesis_{box_id}",
        "output_index": 0,
    })

class TestSpendBoxRollbackBug2:
    def test_spend_nonexistent_returns_none(self, db):
        result = db.spend_box("nonexistent", "tx1")
        assert result is None

    def test_double_spend_raises_and_releases_lock(self, db):
        _add_box(db, "box1", 1000)
        db.spend_box("box1", "tx1")
        with pytest.raises(ValueError, match="Double-spend"):
            db.spend_box("box1", "tx2")
        # After the ValueError, the DB should not be locked
        # (verify we can still do operations)
        _add_box(db, "box2", 500, "addr2")
        result = db.spend_box("box2", "tx3")
        assert result is not None

    def test_spend_box_success(self, db):
        _add_box(db, "box1", 1000)
        result = db.spend_box("box1", "tx1")
        assert result is not None
        assert result["box_id"] == "box1"
