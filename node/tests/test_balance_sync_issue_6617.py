# SPDX-License-Identifier: MIT
# Regression test for https://github.com/Scottcjn/Rustchain/issues/6617
# "Peer balance sync can create positive balances for unknown wallets"

import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from rustchain_sync import RustChainSyncManager


@pytest.fixture()
def db(tmp_path):
    """Create a minimal balances table with one known wallet."""
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE balances ("
        "  wallet TEXT PRIMARY KEY,"
        "  balance_urtc INTEGER NOT NULL DEFAULT 0"
        ")"
    )
    conn.execute(
        "INSERT INTO balances (wallet, balance_urtc) VALUES ('known_wallet', 1000)"
    )
    conn.commit()
    conn.close()
    return db_path


def _manager(db_path):
    return RustChainSyncManager(db_path, admin_key="test-key")


# -- helpers ---------------------------------------------------------------


def _get_balances(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT wallet, balance_urtc FROM balances ORDER BY wallet").fetchall()
    conn.close()
    return {r["wallet"]: r["balance_urtc"] for r in rows}


# -- tests -----------------------------------------------------------------


class TestIssue6617PeerBalanceSync:
    """Verify that peer sync cannot create or inflate wallet balances."""

    def test_known_wallet_same_balance_accepted(self, db):
        """Sync with matching local balance should succeed (no-op upsert)."""
        mgr = _manager(db)
        result = mgr.apply_sync_payload(
            "balances", [{"wallet": "known_wallet", "balance_urtc": 1000}]
        )
        assert result is True
        assert _get_balances(db) == {"known_wallet": 1000}

    def test_known_wallet_different_balance_rejected(self, db):
        """Sync with mismatched balance must be rejected."""
        mgr = _manager(db)
        result = mgr.apply_sync_payload(
            "balances", [{"wallet": "known_wallet", "balance_urtc": 9999}]
        )
        assert result is True  # overall operation succeeds
        assert _get_balances(db) == {"known_wallet": 1000}  # balance unchanged

    def test_unknown_wallet_rejected(self, db):
        """Sync for a wallet that does not exist locally must NOT create a new
        row.  This is the core regression described in issue #6617."""
        mgr = _manager(db)
        result = mgr.apply_sync_payload(
            "balances", [{"wallet": "attacker_wallet", "balance_urtc": 50000}]
        )
        assert result is True
        balances = _get_balances(db)
        assert "attacker_wallet" not in balances
        assert balances == {"known_wallet": 1000}

    def test_unknown_wallet_zero_balance_also_rejected(self, db):
        """Even a zero-balance row must not be inserted for unknown wallets,
        because the row itself is the problem (not just the amount)."""
        mgr = _manager(db)
        result = mgr.apply_sync_payload(
            "balances", [{"wallet": "ghost_wallet", "balance_urtc": 0}]
        )
        assert result is True
        assert "ghost_wallet" not in _get_balances(db)

    def test_multiple_unknown_wallets_rejected(self, db):
        """Batch sync with a mix of known and unknown wallets."""
        mgr = _manager(db)
        result = mgr.apply_sync_payload(
            "balances",
            [
                {"wallet": "known_wallet", "balance_urtc": 1000},
                {"wallet": "unknown_a", "balance_urtc": 100},
                {"wallet": "unknown_b", "balance_urtc": 200},
            ],
        )
        assert result is True
        assert _get_balances(db) == {"known_wallet": 1000}

    def test_pk_missing_from_remote_row_skipped(self, db):
        """Rows without the primary key should be silently skipped."""
        mgr = _manager(db)
        result = mgr.apply_sync_payload("balances", [{"balance_urtc": 999}])
        assert result is True
        assert _get_balances(db) == {"known_wallet": 1000}
