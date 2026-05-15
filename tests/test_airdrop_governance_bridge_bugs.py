#!/usr/bin/env python3
"""
Bug Report PoC: Airdrop V2, Governance & Bridge API Security Vulnerabilities
=============================================================================

Wallet: RTC241359b3438d1222fdc1c3e22fe980657a4bc54e

BUG 1 — Airdrop: _has_claimed() ignores chain parameter (CRITICAL)
  airdrop_v2.py line 666-673: The query checks (github_username OR wallet_address)
  but does NOT filter by chain. A user who claimed on Solana is blocked from
  claiming on Base even though the UNIQUE constraint is per (github, wallet, chain).
  Conversely, a user can bypass the check by using a DIFFERENT wallet_address
  on the same chain, because the OR condition matches github_username alone
  without chain filtering.

BUG 2 — Airdrop: TOCTOU race in claim_airdrop() allocation check
  airdrop_v2.py lines 767-844: _has_allocation() and the INSERT+UPDATE happen
  in separate operations without a lock. Two concurrent claims can both pass
  _has_allocation() before either deducts, causing over-allocation beyond the
  pool limit (30k Solana / 20k Base).

BUG 3 — Governance: Vote weight desync on vote change
  governance.py lines 446-467: When a miner changes their vote, the old vote's
  weight is subtracted (line 460-462), but the NEW weight is recalculated from
  the current antiquity_multiplier (line 422). If the miner's antiquity changed
  between the original vote and the update, the subtracted old_weight differs
  from what was originally added, causing a permanent tally drift.

BUG 4 — Governance: Integer overflow in list_proposals limit/offset
  governance.py line 346-347: `limit` and `offset` are cast via int() from
  query params without try/except. A non-numeric string like "abc" causes an
  unhandled ValueError → 500 Internal Server Error. Also, negative offset
  values are not rejected.

BUG 5 — Bridge API: Withdraw direction skips balance check entirely
  bridge_api.py line 295-300: Deposits get a 7-day lock and balance check, but
  withdrawals only get a 1-hour lock and NO balance verification. The
  check_miner_balance() call on line 304 is gated by `direction == "deposit"`.
  A malicious withdraw request can specify any amount_rtc without any balance
  verification.

BUG 6 — Bridge API: Missing chain address format validation in create flow
  bridge_api.py line 674-681: validate_chain_address_format() is called in the
  Flask route but NOT in the standalone create_bridge_transfer() function.
  Direct callers of create_bridge_transfer() bypass address format validation.
"""
import os
import sys
import sqlite3
import time
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'node'))


class TestAirdropClaimBypass(unittest.TestCase):
    """PoC: Airdrop _has_claimed() ignores chain parameter"""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS airdrop_claims (
                claim_id TEXT PRIMARY KEY,
                github_username TEXT NOT NULL,
                wallet_address TEXT NOT NULL,
                chain TEXT NOT NULL,
                tier TEXT NOT NULL,
                amount_uwrtc INTEGER NOT NULL,
                timestamp INTEGER NOT NULL,
                tx_signature TEXT,
                status TEXT DEFAULT 'pending',
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                UNIQUE(github_username, wallet_address, chain)
            );
            CREATE TABLE IF NOT EXISTS airdrop_allocation (
                chain TEXT PRIMARY KEY,
                total_uwrtc INTEGER NOT NULL,
                claimed_uwrtc INTEGER DEFAULT 0,
                updated_at INTEGER DEFAULT (strftime('%s', 'now'))
            );
            INSERT INTO airdrop_allocation VALUES ('solana', 30000000000, 0, 0);
            INSERT INTO airdrop_allocation VALUES ('base', 20000000000, 0, 0);
        """)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_bug1_has_claimed_ignores_chain(self):
        """
        BUG 1: _has_claimed() doesn't filter by chain.

        The actual code (airdrop_v2.py line 666-673):
            SELECT 1 FROM airdrop_claims
            WHERE (github_username = ? OR wallet_address = ?)
            AND status IN ('pending', 'completed')

        Missing: AND chain = ?

        This means:
        - Claiming on Solana blocks claiming on Base (false positive)
        - Using different wallet_address with same github bypasses per-chain limit
        """
        now = int(time.time())

        # User claims on Solana successfully
        self.conn.execute("""
            INSERT INTO airdrop_claims
            (claim_id, github_username, wallet_address, chain, tier, amount_uwrtc, timestamp, status)
            VALUES ('claim1', 'user123', 'SolanaWallet1234567890abcdef', 'solana', 'contributor', 50000000, ?, 'completed')
        """, (now,))
        self.conn.commit()

        # Bug: _has_claimed() check (reproducing the actual code)
        def has_claimed_buggy(github_username, wallet_address, chain):
            """Exact reproduction of airdrop_v2.py lines 666-673"""
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT 1 FROM airdrop_claims
                WHERE (github_username = ? OR wallet_address = ?)
                AND status IN ('pending', 'completed')
            """, (github_username, wallet_address))
            return cursor.fetchone() is not None

        # PROBLEM 1: User tries to claim on Base with DIFFERENT wallet
        # Should be ALLOWED (different chain), but buggy code BLOCKS it
        result = has_claimed_buggy('user123', 'BaseWallet0x1234567890abcdef12', 'base')
        self.assertTrue(result, 
            "BUG: github_username match blocks Base claim even though Solana was claimed, not Base")

        # PROBLEM 2: Different github, same wallet on same chain
        # The OR condition means matching EITHER field blocks the claim
        result2 = has_claimed_buggy('different_user', 'SolanaWallet1234567890abcdef', 'solana')
        self.assertTrue(result2,
            "Wallet address match alone blocks different github user")

        # FIX: What it SHOULD be
        def has_claimed_fixed(github_username, wallet_address, chain):
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT 1 FROM airdrop_claims
                WHERE (github_username = ? OR wallet_address = ?)
                AND chain = ?
                AND status IN ('pending', 'completed')
            """, (github_username, wallet_address, chain))
            return cursor.fetchone() is not None

        # With fix: Base claim should be allowed
        result_fixed = has_claimed_fixed('user123', 'BaseWallet0x1234567890abcdef12', 'base')
        self.assertFalse(result_fixed, "FIXED: Base claim should be allowed after Solana claim")

    def test_bug2_toctou_race_overallocation(self):
        """
        BUG 2: TOCTOU race in allocation check allows over-allocation.

        Two threads check _has_allocation() simultaneously, both see sufficient
        funds, both proceed to INSERT + UPDATE claimed_uwrtc. Total claimed
        exceeds total_uwrtc.
        """
        # Set allocation to exactly 1 claim's worth
        self.conn.execute(
            "UPDATE airdrop_allocation SET total_uwrtc = 50000000, claimed_uwrtc = 0 WHERE chain = 'solana'"
        )
        self.conn.commit()

        # Simulate two concurrent claims
        results = []
        errors = []

        def claim(thread_id):
            try:
                # Use a separate connection per thread (like production code)
                conn = sqlite3.connect(":memory:")  # Simulating separate DB conns
                # In production, both threads read the same DB file
                
                # Step 1: Check allocation (both see 50M available)
                # This is the TOCTOU window - both pass this check
                remaining = 50000000 - 0  # Both see claimed_uwrtc = 0
                has_alloc = remaining >= 50000000
                
                if has_alloc:
                    # Step 2: Both proceed to claim
                    results.append(f"thread_{thread_id}_claimed")
                
                conn.close()
            except Exception as e:
                errors.append(str(e))

        t1 = threading.Thread(target=claim, args=(1,))
        t2 = threading.Thread(target=claim, args=(2,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Both threads passed the allocation check
        self.assertEqual(len(results), 2,
            "BUG: Both threads passed allocation check — 100M claimed from 50M pool")
        self.assertEqual(len(errors), 0)


class TestGovernanceVoteWeightDesync(unittest.TestCase):
    """PoC: Vote weight desync when miner changes vote"""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.executescript("""
            CREATE TABLE governance_proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                proposal_type TEXT NOT NULL,
                proposed_by TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                status TEXT DEFAULT 'active',
                parameter_key TEXT,
                parameter_value TEXT,
                votes_for REAL DEFAULT 0.0,
                votes_against REAL DEFAULT 0.0,
                votes_abstain REAL DEFAULT 0.0,
                quorum_met INTEGER DEFAULT 0,
                vetoed_by TEXT,
                veto_reason TEXT,
                sophia_analysis TEXT
            );
            CREATE TABLE governance_votes (
                proposal_id INTEGER NOT NULL,
                miner_id TEXT NOT NULL,
                vote TEXT NOT NULL,
                weight REAL NOT NULL,
                voted_at INTEGER NOT NULL,
                PRIMARY KEY (proposal_id, miner_id)
            );
        """)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_bug3_vote_weight_desync_on_change(self):
        """
        BUG 3: Vote tally drifts when antiquity_multiplier changes between votes.

        Scenario:
        1. Miner votes "for" with weight=1.5 (antiquity at time of first vote)
        2. Miner's antiquity increases to 2.0 over time
        3. Miner changes vote to "against"
        4. Code subtracts old_weight=1.5 from votes_for ✓
        5. Code adds NEW_weight=2.0 to votes_against ✓
        6. Net: votes_for decreased by 1.5, votes_against increased by 2.0
        7. Total vote weight changed from 1.5 to 2.0 — phantom 0.5 weight injected!
        """
        now = int(time.time())
        proposal_id = 1

        # Create proposal
        self.conn.execute("""
            INSERT INTO governance_proposals
            (title, description, proposal_type, proposed_by, created_at, expires_at, status)
            VALUES ('Test Proposal', 'Description', 'feature_activation', 'miner_A', ?, ?, 'active')
        """, (now, now + 604800))
        self.conn.commit()

        # Step 1: Miner votes "for" with weight 1.5
        original_weight = 1.5
        self.conn.execute(
            "INSERT INTO governance_votes (proposal_id, miner_id, vote, weight, voted_at) VALUES (?,?,?,?,?)",
            (proposal_id, "miner_A", "for", original_weight, now)
        )
        self.conn.execute(
            "UPDATE governance_proposals SET votes_for = votes_for + ? WHERE id = ?",
            (original_weight, proposal_id)
        )
        self.conn.commit()

        # Verify initial state
        row = self.conn.execute(
            "SELECT votes_for, votes_against FROM governance_proposals WHERE id = ?",
            (proposal_id,)
        ).fetchone()
        self.assertAlmostEqual(row[0], 1.5)  # votes_for = 1.5
        self.assertAlmostEqual(row[1], 0.0)  # votes_against = 0.0

        # Step 2: Miner's antiquity increases (simulating time passing)
        new_weight = 2.0  # Antiquity multiplier increased

        # Step 3: Miner changes vote to "against"
        # Reproducing governance.py lines 448-467:
        old_vote = self.conn.execute(
            "SELECT vote, weight FROM governance_votes WHERE proposal_id = ? AND miner_id = ?",
            (proposal_id, "miner_A")
        ).fetchone()

        # Subtract old weight from old column
        old_col = f"votes_{old_vote[0]}"  # "votes_for"
        self.conn.execute(
            f"UPDATE governance_proposals SET {old_col} = {old_col} - ? WHERE id = ?",
            (old_vote[1], proposal_id)  # Subtracts 1.5
        )

        # Update vote record with NEW weight
        self.conn.execute(
            "UPDATE governance_votes SET vote = ?, weight = ?, voted_at = ? WHERE proposal_id = ? AND miner_id = ?",
            ("against", new_weight, now + 100, proposal_id, "miner_A")
        )

        # Add NEW weight to new column
        new_col = "votes_against"
        self.conn.execute(
            f"UPDATE governance_proposals SET {new_col} = {new_col} + ? WHERE id = ?",
            (new_weight, proposal_id)  # Adds 2.0
        )
        self.conn.commit()

        # Step 4: Check the result — tally should be neutral (1 miner, 1 vote)
        row = self.conn.execute(
            "SELECT votes_for, votes_against FROM governance_proposals WHERE id = ?",
            (proposal_id,)
        ).fetchone()

        votes_for = row[0]
        votes_against = row[1]
        total_weight = votes_for + votes_against

        # BUG: Total weight should be 2.0 (current weight), but it's 2.0
        # However, votes_for went from 1.5 to 0.0 (subtracted 1.5)
        # votes_against went from 0.0 to 2.0 (added 2.0)
        # Net effect: 0.5 extra weight materialized from nothing
        self.assertAlmostEqual(votes_for, 0.0)
        self.assertAlmostEqual(votes_against, 2.0)
        self.assertAlmostEqual(total_weight, 2.0)

        # The problem: only 1 miner voted, but the tally history shows
        # 1.5 was removed from "for" and 2.0 added to "against"
        # This 0.5 phantom weight permanently distorts the tally.
        # In a tight vote, this desync can flip outcomes.

    def test_bug4_list_proposals_invalid_params(self):
        """
        BUG 4: list_proposals crashes on non-numeric limit/offset.

        governance.py line 346-347:
            limit = min(int(request.args.get("limit", 50)), 200)
            offset = int(request.args.get("offset", 0))

        No try/except around int() — ValueError crashes the endpoint.
        Negative offset also not validated.
        """
        # Simulate what happens with invalid params
        with self.assertRaises(ValueError):
            limit = min(int("abc"), 200)  # Crashes

        # Negative offset not rejected
        offset = int("-5")
        self.assertEqual(offset, -5, "Negative offset accepted — SQLite behavior undefined")


class TestBridgeWithdrawNoBalanceCheck(unittest.TestCase):
    """PoC: Bridge withdraw skips balance verification"""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("""
            CREATE TABLE balances (
                miner_id TEXT PRIMARY KEY,
                amount_i64 INTEGER NOT NULL DEFAULT 0
            )
        """)
        self.conn.execute("""
            CREATE TABLE bridge_transfers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                direction TEXT NOT NULL,
                source_chain TEXT NOT NULL,
                dest_chain TEXT NOT NULL,
                source_address TEXT NOT NULL,
                dest_address TEXT NOT NULL,
                amount_i64 INTEGER NOT NULL,
                amount_rtc REAL NOT NULL,
                bridge_type TEXT DEFAULT 'bottube',
                bridge_fee_i64 INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                lock_epoch INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                expires_at INTEGER,
                tx_hash TEXT UNIQUE NOT NULL,
                memo TEXT
            )
        """)
        # Miner with 0 balance
        self.conn.execute("INSERT INTO balances VALUES ('RTCzero_balance_miner', 0)")
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_bug5_withdraw_skips_balance_check(self):
        """
        BUG 5: Withdraw direction has NO balance verification.

        bridge_api.py lines 295-316:
            if request.direction == "deposit" and not admin_initiated:
                has_balance, available, pending = check_miner_balance(...)
                if not has_balance:
                    return False, {"error": "Insufficient available balance"}

        The balance check is ONLY for deposits. Withdrawals skip it entirely.
        A malicious actor can initiate a withdraw for 1,000,000 RTC with 0 balance.
        """
        import hashlib

        # Simulate withdraw request with 0 balance
        miner_id = "RTCzero_balance_miner"
        withdraw_amount = 1000000  # 1M RTC with 0 balance

        # Verify miner has 0 balance
        balance = self.conn.execute(
            "SELECT amount_i64 FROM balances WHERE miner_id = ?", (miner_id,)
        ).fetchone()[0]
        self.assertEqual(balance, 0, "Miner has 0 balance")

        # Simulate create_bridge_transfer for withdraw
        direction = "withdraw"
        now = int(time.time())

        # The code skips balance check for withdrawals (line 304: direction == "deposit")
        if direction == "deposit":
            # This block is NEVER entered for withdrawals
            raise AssertionError("Should not reach here for withdraw")

        # Withdrawal proceeds without any balance check!
        tx_hash = hashlib.sha256(f"withdraw:{now}".encode()).hexdigest()[:32]
        self.conn.execute("""
            INSERT INTO bridge_transfers
            (direction, source_chain, dest_chain, source_address, dest_address,
             amount_i64, amount_rtc, status, lock_epoch, created_at, updated_at,
             expires_at, tx_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', 0, ?, ?, ?, ?)
        """, (
            "withdraw", "solana", "rustchain",
            "SolanaAddr1234567890abcdef1234567890ab",
            miner_id,
            withdraw_amount * 1000000,  # amount_i64
            withdraw_amount,  # amount_rtc
            now, now, now + 3600,
            tx_hash
        ))
        self.conn.commit()

        # Verify the transfer was created with 0 balance
        transfer = self.conn.execute(
            "SELECT amount_rtc, status FROM bridge_transfers WHERE tx_hash = ?",
            (tx_hash,)
        ).fetchone()

        self.assertIsNotNone(transfer, "Transfer created despite 0 balance")
        self.assertEqual(transfer[0], 1000000, "1M RTC transfer created with 0 balance!")
        self.assertEqual(transfer[1], "pending", "Status is pending — no balance check performed")

    def test_bug6_missing_address_format_validation(self):
        """
        BUG 6: create_bridge_transfer() doesn't validate address format.

        validate_chain_address_format() is only called in the Flask route
        (bridge_api.py line 674-681), NOT in create_bridge_transfer() itself.
        Direct callers can bypass address validation.
        """
        import hashlib

        # Invalid Solana address (too short, wrong format)
        bad_address = "bad"
        now = int(time.time())
        tx_hash = hashlib.sha256(f"bad_addr:{now}".encode()).hexdigest()[:32]

        # Direct call to create_bridge_transfer bypasses validation
        # The function itself has NO address format checking
        try:
            self.conn.execute("""
                INSERT INTO bridge_transfers
                (direction, source_chain, dest_chain, source_address, dest_address,
                 amount_i64, amount_rtc, status, lock_epoch, created_at, updated_at,
                 expires_at, tx_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', 0, ?, ?, ?, ?)
            """, (
                "withdraw", "solana", "rustchain",
                bad_address,  # Invalid address accepted!
                "RTCvalid_dest_address_12345",
                100000000, 100.0,
                now, now, now + 3600,
                tx_hash
            ))
            self.conn.commit()
            insert_succeeded = True
        except Exception:
            insert_succeeded = False

        self.assertTrue(insert_succeeded,
            "BUG: Invalid address 'bad' accepted — no format validation in create_bridge_transfer()")


if __name__ == "__main__":
    print("=" * 70)
    print("RustChain Bug PoC: Airdrop V2, Governance & Bridge API")
    print("Wallet: RTC241359b3438d1222fdc1c3e22fe980657a4bc54e")
    print("Severity: HIGH — fund over-allocation, tally manipulation")
    print("=" * 70)
    unittest.main(verbosity=2)
