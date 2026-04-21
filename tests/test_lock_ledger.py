#!/usr/bin/env python3
"""
Unit tests for node/lock_ledger.py
Bounty #1589 - 9 test cases
"""

import pytest
import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(__file__))

# Mock the dependency before importing
mock_module = type(sys)('rustchain_v2_integrated_v2_2_1_rip200')
mock_module.DB_PATH = ':memory:'
mock_module.UNIT = 1000000
mock_module.current_slot = lambda: 100
mock_module.slot_to_epoch = lambda s: s // 144
sys.modules['rustchain_v2_integrated_v2_2_1_rip200'] = mock_module


def test_lock_type_enum_values():
    from node.lock_ledger import LockType
    assert LockType.BRIDGE_DEPOSIT.value == "bridge_deposit"
    assert LockType.BRIDGE_WITHDRAW.value == "bridge_withdraw"
    assert LockType.EPOCH_SETTLEMENT.value == "epoch_settlement"
    assert LockType.ADMIN_HOLD.value == "admin_hold"


def test_lock_status_enum_values():
    from node.lock_ledger import LockStatus
    assert LockStatus.LOCKED.value == "locked"
    assert LockStatus.RELEASED.value == "released"
    assert LockStatus.FORFEITED.value == "forfeited"


def test_lock_entry_dataclass_fields():
    from node.lock_ledger import LockEntry
    entry = LockEntry(
        id=1,
        bridge_transfer_id=100,
        miner_id="test-miner",
        amount_i64=5000000,
        lock_type="bridge_deposit",
        locked_at=1000,
        unlock_at=2000,
        unlocked_at=None,
        status="locked",
        created_at=999,
        released_by=None,
        release_tx_hash=None
    )
    assert entry.id == 1
    assert entry.miner_id == "test-miner"
    assert entry.amount_i64 == 5000000
    assert entry.lock_type == "bridge_deposit"


def test_get_lock_by_id_returns_none_for_missing():
    from node.lock_ledger import get_lock_by_id
    mock_cursor = MagicMock()
    mock_cursor.execute.return_value.fetchone.return_value = None
    mock_db = MagicMock()
    mock_db.cursor.return_value = mock_cursor
    result = get_lock_by_id(mock_db, 99999)
    assert result is None


def test_get_locks_by_miner_returns_list():
    from node.lock_ledger import get_locks_by_miner
    mock_cursor = MagicMock()
    mock_cursor.execute.return_value.fetchall.return_value = []
    mock_db = MagicMock()
    mock_db.cursor.return_value = mock_cursor
    result = get_locks_by_miner(mock_db, "nonexistent-miner")
    assert isinstance(result, list)


def test_get_pending_unlocks_returns_list():
    from node.lock_ledger import get_pending_unlocks
    mock_cursor = MagicMock()
    mock_cursor.execute.return_value.fetchall.return_value = []
    mock_db = MagicMock()
    mock_db.cursor.return_value = mock_cursor
    result = get_pending_unlocks(mock_db)
    assert isinstance(result, list)


def test_get_miner_locked_balance_returns_dict():
    from node.lock_ledger import get_miner_locked_balance
    mock_cursor = MagicMock()
    mock_cursor.execute.return_value.fetchone.return_value = (0, 0)
    mock_db = MagicMock()
    mock_db.cursor.return_value = mock_cursor
    result = get_miner_locked_balance(mock_db, "test-miner")
    assert isinstance(result, dict)


def test_release_lock_nonexistent_returns_false():
    from node.lock_ledger import release_lock
    mock_cursor = MagicMock()
    # First call for release_lock: fetchone returns None -> returns (False, error)
    mock_cursor.execute.return_value.fetchone.return_value = None
    mock_db = MagicMock()
    mock_db.cursor.return_value = mock_cursor
    result = release_lock(mock_db, 99999)
    assert result == (False, {"error": "Lock not found"})


def test_forfeit_lock_nonexistent_returns_false():
    from node.lock_ledger import forfeit_lock
    mock_cursor = MagicMock()
    mock_cursor.execute.return_value.fetchone.return_value = None
    mock_db = MagicMock()
    mock_db.cursor.return_value = mock_cursor
    result = forfeit_lock(mock_db, 99999, "test-reason")
    assert result == (False, {"error": "Lock not found"})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
