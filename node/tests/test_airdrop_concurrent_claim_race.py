"""Regression: concurrent claims for the SAME GitHub account with DIFFERENT
wallets must not both succeed (issue #8245).

`_has_claimed()` is a plain SELECT and the INSERT commits later.  The dedup
rule the code intends is "one claim per github_username OR per wallet_address,
per chain", but the table-level UNIQUE constraint only covers the *triple*
(github_username, wallet_address, chain).  So two concurrent claims for the
same username with different wallets both pass the SELECT and both INSERT,
double-allocating from the chain's pool.

The fix has two layers:
  1. process_claim() takes the write lock up front (BEGIN IMMEDIATE) and
     re-checks inside that transaction.
  2. partial unique indexes on (chain, github_username) and
     (chain, wallet_address) let the database itself reject the second row.
"""
import os
import sqlite3
import sys
import threading

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from airdrop_v2 import AirdropV2  # noqa: E402

SOL_A = "5ohjfDfPzGvR6yQXQCkxbnvKuBoQGRfrXKvsAvvhkVs1"
SOL_B = "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"
SOL_C = "7GgPYjS5Dza89wV6FpZ23kUJRG5vbQ1GSQSqD5ByNAmp"


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "airdrop.db")


def _claimed_uwrtc(airdrop, chain="solana"):
    conn = airdrop._get_conn()
    row = conn.execute(
        "SELECT claimed_uwrtc FROM airdrop_allocation WHERE chain = ?", (chain,)
    ).fetchone()
    airdrop._close_conn(conn)
    return row["claimed_uwrtc"]


def _rows(db_path):
    conn = sqlite3.connect(db_path)
    n = conn.execute(
        "SELECT COUNT(*) FROM airdrop_claims WHERE status IN ('pending','completed')"
    ).fetchone()[0]
    conn.close()
    return n


def test_concurrent_same_username_different_wallets_only_one_wins(db_path):
    """The exact race from #8245: one username, three wallets, all at once."""
    airdrop = AirdropV2(db_path)

    results = []
    barrier = threading.Barrier(3)

    def claim(wallet):
        # everyone waits here so the SELECTs really do overlap
        barrier.wait()
        ok, msg, _ = airdrop.claim_airdrop(
            github_username="mallory",
            wallet_address=wallet,
            chain="solana",
            tier="core",
            skip_antisybil=True,
        )
        results.append(ok)

    threads = [threading.Thread(target=claim, args=(w,))
               for w in (SOL_A, SOL_B, SOL_C)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sum(1 for r in results if r) == 1, (
        f"expected exactly one winner, got {sum(1 for r in results if r)} "
        f"-> the same GitHub account double-allocated: {results}"
    )
    assert _rows(db_path) == 1


def test_concurrent_same_wallet_different_usernames_only_one_wins(db_path):
    """Mirror case: one wallet, several GitHub accounts."""
    airdrop = AirdropV2(db_path)
    results = []
    barrier = threading.Barrier(3)

    def claim(user):
        barrier.wait()
        ok, _, _ = airdrop.claim_airdrop(
            github_username=user,
            wallet_address=SOL_A,
            chain="solana",
            tier="core",
            skip_antisybil=True,
        )
        results.append(ok)

    threads = [threading.Thread(target=claim, args=(u,))
               for u in ("alice", "bob", "carol")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sum(1 for r in results if r) == 1, results
    assert _rows(db_path) == 1


def test_allocation_debited_exactly_once_under_race(db_path):
    """Double-allocation is the actual damage — assert the pool math."""
    airdrop = AirdropV2(db_path)
    before = _claimed_uwrtc(airdrop)

    barrier = threading.Barrier(4)

    def claim(wallet):
        barrier.wait()
        airdrop.claim_airdrop(
            github_username="mallory",
            wallet_address=wallet,
            chain="solana",
            tier="core",
            skip_antisybil=True,
        )

    wallets = [SOL_A, SOL_B, SOL_C, "4vJ9JU1bJJE96FWSJKvHsmmFADCg4gpZQff4P3bkLKi"]
    threads = [threading.Thread(target=claim, args=(w,)) for w in wallets]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT amount_uwrtc FROM airdrop_claims "
        "WHERE status IN ('pending','completed')"
    ).fetchall()
    conn.close()
    assert len(row) == 1, f"{len(row)} claim rows survived the race"
    assert _claimed_uwrtc(airdrop) - before == row[0]["amount_uwrtc"], (
        "allocation debited by a different amount than the surviving claim"
    )


def test_database_itself_rejects_second_username_row(db_path):
    """Layer 2: even a writer that bypasses process_claim() is stopped."""
    airdrop = AirdropV2(db_path)
    ok, msg, claim = airdrop.claim_airdrop(
        github_username="alice",
        wallet_address=SOL_A,
        chain="solana",
        tier="core",
        skip_antisybil=True,
    )
    assert ok, msg

    conn = sqlite3.connect(db_path)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO airdrop_claims (claim_id, github_username, wallet_address,"
            " chain, tier, amount_uwrtc, timestamp, status) "
            "VALUES ('raw1','alice',?, 'solana','core',1,1,'pending')",
            (SOL_B,),
        )
        conn.commit()
    conn.close()


def test_database_itself_rejects_second_wallet_row(db_path):
    airdrop = AirdropV2(db_path)
    ok, msg, _ = airdrop.claim_airdrop(
        github_username="alice",
        wallet_address=SOL_A,
        chain="solana",
        tier="core",
        skip_antisybil=True,
    )
    assert ok, msg

    conn = sqlite3.connect(db_path)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO airdrop_claims (claim_id, github_username, wallet_address,"
            " chain, tier, amount_uwrtc, timestamp, status) "
            "VALUES ('raw2','someoneelse',?, 'solana','core',1,1,'pending')",
            (SOL_A,),
        )
        conn.commit()
    conn.close()


def test_failed_claim_does_not_block_a_different_wallet(db_path):
    """The new indexes are PARTIAL on status, so an abandoned claim must not
    keep the account locked forever.

    Note: retrying the *same* (username, wallet, chain) triple stays blocked by
    the pre-existing table-level UNIQUE constraint, which is unrelated to this
    fix and would need a migration to change. What matters here is that the
    guard added by this PR only covers live claims.
    """
    airdrop = AirdropV2(db_path)
    ok, msg, claim = airdrop.claim_airdrop(
        github_username="alice",
        wallet_address=SOL_A,
        chain="solana",
        tier="core",
        skip_antisybil=True,
    )
    assert ok, msg

    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE airdrop_claims SET status = 'failed' WHERE claim_id = ?",
        (claim.claim_id,),
    )
    conn.commit()
    conn.close()

    ok2, msg2, _ = airdrop.claim_airdrop(
        github_username="alice",
        wallet_address=SOL_B,
        chain="solana",
        tier="core",
        skip_antisybil=True,
    )
    assert ok2, f"an abandoned claim must not lock the account forever: {msg2}"


def test_other_chain_is_unaffected(db_path):
    """The indexes are per-chain: a Solana claim must not block Base."""
    airdrop = AirdropV2(db_path)
    ok, msg, _ = airdrop.claim_airdrop(
        github_username="alice", wallet_address=SOL_A, chain="solana",
        tier="core", skip_antisybil=True,
    )
    assert ok, msg
    ok2, msg2, _ = airdrop.claim_airdrop(
        github_username="alice",
        wallet_address="0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6",
        chain="base", tier="core", skip_antisybil=True,
    )
    assert ok2, msg2


def test_legacy_db_with_duplicates_still_boots(db_path, caplog):
    """A pre-existing DB may already hold duplicates; refusing to start would
    be a worse failure mode than the drift we are fixing."""
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE airdrop_claims (
            claim_id TEXT PRIMARY KEY, github_username TEXT NOT NULL,
            wallet_address TEXT NOT NULL, chain TEXT NOT NULL, tier TEXT NOT NULL,
            amount_uwrtc INTEGER NOT NULL, timestamp INTEGER NOT NULL,
            tx_signature TEXT, status TEXT DEFAULT 'pending',
            created_at INTEGER DEFAULT (strftime('%s','now')),
            UNIQUE(github_username, wallet_address, chain)
        );
        """
    )
    conn.executemany(
        "INSERT INTO airdrop_claims (claim_id, github_username, wallet_address,"
        " chain, tier, amount_uwrtc, timestamp, status) VALUES (?,?,?,?,?,?,?,?)",
        [
            ("old1", "mallory", SOL_A, "solana", "core", 1, 1, "pending"),
            ("old2", "mallory", SOL_B, "solana", "core", 1, 1, "pending"),
        ],
    )
    conn.commit()
    conn.close()

    airdrop = AirdropV2(db_path)  # must not raise
    assert airdrop is not None
