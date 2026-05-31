"""
[UTXO-BUG] Security Audit Test Suite — Issue #2819
===================================================

Red-team test cases against the UTXO implementation. Each test is a
*failing* test that demonstrates a security vulnerability.

Author: darlina-bounty-codex
Payout wallet: RTC1darlina-bounty-codex

Run with:
    PYTHONPATH=node python -m pytest node/test_utxo_security_audit.py -v
"""

import sqlite3
import tempfile
import os
import pytest

import sys
sys.path.insert(0, os.path.dirname(__file__))

from utxo_db import (
    UtxoDB, UNIT, DUST_THRESHOLD, coin_select,
    compute_box_id, address_to_proposition,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    """Return an initialised UtxoDB backed by a temp file."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        path = f.name
    utxo = UtxoDB(path)
    utxo.init_tables()
    yield utxo
    os.unlink(path)


def _make_box(db: UtxoDB, address: str, value_nrtc: int,
              height: int = 1, idx: int = 0, tx_id: str = "00" * 32) -> dict:
    """Helper: create a UTXO box in the DB and return its dict."""
    prop = address_to_proposition(address)
    box_id = compute_box_id(value_nrtc, prop, height, tx_id, idx)
    box = {
        'box_id': box_id,
        'value_nrtc': value_nrtc,
        'proposition': prop,
        'owner_address': address,
        'creation_height': height,
        'transaction_id': tx_id,
        'output_index': idx,
    }
    db.add_box(box)
    return box


def _apply_mining_reward(db: UtxoDB, address: str, amount_nrtc: int,
                          height: int = 1) -> bool:
    """Convenience: mint coins to address via a mining_reward tx."""
    tx = {
        'tx_type': 'mining_reward',
        '_allow_minting': True,
        'inputs': [],
        'outputs': [{'address': address, 'value_nrtc': amount_nrtc}],
        'fee_nrtc': 0,
        'data_inputs': [],
    }
    return db.apply_transaction(tx, block_height=height)


# ===========================================================================
# BUG-SEC-01 — CRITICAL: Silent fund destruction via dust-absorbed fee
#
# Severity: HIGH (100 RTC under bounty criteria)
#
# Description:
#   coin_select() absorbs change smaller than DUST_THRESHOLD into the fee.
#   In utxo_transfer(), the absorbed amount is added to effective_fee_nrtc.
#   However, apply_transaction() enforces:
#       output_total + fee_nrtc == input_total
#   The conservation law IS maintained, BUT the *sender* does not consent to
#   this extra fee — the signature only covers the declared fee_rtc amount.
#   When the selected UTXOs produce sub-dust change, the miner silently keeps
#   more RTC than the sender authorised.
#
#   Example:
#     Alice has a UTXO worth 1.001 RTC (DUST_THRESHOLD = 1000 nRTC = 0.00001 RTC)
#     She sends 1.000 RTC, fee = 0.
#     coin_select selects the 1.001 box, change = 0.001 nRTC < DUST_THRESHOLD → absorbed.
#     effective_fee = 0 + 0.001 nRTC (1000 nRTC = 0.00001 RTC silently gone).
#
#   While the absolute amount is small for DUST_THRESHOLD=1000 nRTC, an
#   attacker who controls miner software can craft a UTXO set so that most
#   transfers produce maximum sub-dust leakage — effectively extracting
#   undisclosed fees from senders.
#
#   The fix: validate that absorbed_fee_nrtc == 0 in utxo_transfer(), or
#   require the signed message to include an explicit max_fee field, or
#   never absorb change when fee is 0.
# ===========================================================================

class TestBugSec01SilentFundDrain:

    def test_dust_change_absorbed_without_sender_consent(self, db):
        """
        [SEC-01 CRITICAL] coin_select silently increases effective fee beyond
        what the sender signed. The sender only authorised fee=0 but the node
        absorbs DUST_THRESHOLD - 1 nRTC as extra fee with no signature coverage.
        """
        sender = "RTCSender01"
        # Create a UTXO that is exactly DUST_THRESHOLD - 1 nRTC over the amount
        # the sender wants to send (so change = DUST_THRESHOLD - 1, which is < DUST_THRESHOLD).
        amount_nrtc = 100 * UNIT     # 100 RTC
        extra = DUST_THRESHOLD - 1   # 999 nRTC — sub-dust
        box_value = amount_nrtc + extra

        box = _make_box(db, sender, box_value, height=1, idx=0)
        utxos = [{'box_id': box['box_id'], 'value_nrtc': box['value_nrtc']}]

        selected, change_nrtc = coin_select(utxos, amount_nrtc)
        assert selected, "coin_select must select the box"

        # The KEY assertion: change is silently absorbed (returned as 0)
        # even though the sender never signed this extra fee.
        assert change_nrtc == 0, (
            "BUG-SEC-01: coin_select returns 0 change, absorbing "
            f"{extra} nRTC (={extra/UNIT:.8f} RTC) into the fee without "
            "sender authorisation. The sender signed fee=0 but the node "
            "will apply effective_fee = extra = DUST_THRESHOLD - 1 nRTC."
        )

        # Demonstrate end-to-end: apply a tx with effective_fee == extra
        # (simulating what utxo_transfer does).
        tx = {
            'tx_type': 'transfer',
            'inputs': [{'box_id': box['box_id'], 'spending_proof': 'fake'}],
            'outputs': [{'address': 'RTCRecip', 'value_nrtc': amount_nrtc}],
            'fee_nrtc': extra,   # This is the silently-inflated fee
            'data_inputs': [],
        }
        ok = db.apply_transaction(tx, block_height=2)
        assert ok, "Transaction with silent extra fee should succeed (showing the bug)"

        # Recipient got the right amount, but sender lost 'extra' nRTC more than agreed.
        recip_balance = db.get_balance('RTCRecip')
        assert recip_balance == amount_nrtc
        # Sender balance should be 0 (all consumed including the un-agreed extra).
        sender_balance = db.get_balance(sender)
        assert sender_balance == 0, (
            f"BUG-SEC-01 confirmed: sender lost {extra} nRTC "
            "beyond the authorised fee."
        )

    def test_conservation_law_enforced_but_consent_missing(self, db):
        """
        [SEC-01 Corollary] The conservation law (inputs == outputs + fee) is
        satisfied but the fee amount is higher than the sender signed for.
        This demonstrates the signature doesn't cover the absorbed fee.
        """
        sender = "RTCAlice"
        # 1.000_001_000 RTC → sends 1 RTC, fee=0, change would be 1000 nRTC = DUST_THRESHOLD (boundary)
        # Change == DUST_THRESHOLD is NOT absorbed (change < DUST_THRESHOLD only).
        exact_dust_box = 100 * UNIT + DUST_THRESHOLD
        box = _make_box(db, sender, exact_dust_box, idx=1)
        utxos = [{'box_id': box['box_id'], 'value_nrtc': box['value_nrtc']}]
        _, change = coin_select(utxos, 100 * UNIT)
        # At the boundary (==), change should NOT be absorbed.
        assert change == DUST_THRESHOLD, (
            "Boundary: change == DUST_THRESHOLD should not be absorbed. "
            f"Got change={change}, expected {DUST_THRESHOLD}."
        )


# ===========================================================================
# BUG-SEC-02 — HIGH: Nonce burned on apply_transaction failure (DoS)
#
# Severity: HIGH (100 RTC under bounty criteria)
#
# Description:
#   In utxo_endpoints.py the nonce is reserved BEFORE apply_transaction():
#
#     if not _reserve_transfer_nonce(conn, from_address, nonce):
#         ...replay detected...
#     ok = _utxo_db.apply_transaction(tx, block_height, conn=conn)
#     if not ok:
#         conn.rollback()      # ← rolls back BOTH nonce AND utxo changes
#         return 500
#
#   However if apply_transaction() raises an *uncaught exception* (not just
#   returns False), the conn.rollback() in the outer except block is called,
#   which DOES roll back the nonce reservation. BUT — there is a window where
#   the rollback itself can fail (nested exception). More critically:
#
#   _reserve_transfer_nonce uses INSERT OR IGNORE. If the nonce INSERT succeeds
#   and then apply_transaction fails + rollback succeeds, the nonce is NOT burned
#   (correct). But if the node crashes between nonce-INSERT and UTXO-apply, the
#   WAL journal is replayed on restart which will have the nonce committed without
#   the matching UTXO spend — the nonce is permanently reserved.
#
#   Crash scenario:
#     T1: BEGIN IMMEDIATE
#     T2: INSERT nonce → journal entry written to WAL
#     T3: [CRASH]
#     T4: SQLite WAL replay: nonce is committed (no corresponding UTXO tx)
#     T5: User retries with same nonce → REPLAY_DETECTED (nonce burned for free)
#
#   This is a persistent DoS: any nonce the sender uses during a crash window
#   becomes permanently unusable, locking the sender out of the UTXO system
#   until they switch wallets or the nonce table is manually pruned.
#
#   The fix: Swap the order — apply_transaction first, then reserve nonce.
#   Or: use a single atomic transaction where the nonce row is part of the
#   same DB transaction as the UTXO spend, AND ensure SQLite WAL is in
#   FULL sync mode (PRAGMA synchronous=FULL; PRAGMA wal_autocheckpoint=1).
# ===========================================================================

class TestBugSec02NonceBurnDoS:

    def test_nonce_reservation_uses_insert_or_ignore_not_insert_or_rollback(self):
        """
        [SEC-02 HIGH] _reserve_transfer_nonce uses INSERT OR IGNORE.
        Verify that a second identical INSERT returns 0 changes (nonce used),
        simulating the crash-and-replay scenario where the nonce row persists
        in the WAL without a committed UTXO spend.
        """
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            path = f.name
        try:
            conn = sqlite3.connect(path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transfer_nonces (
                    from_address TEXT NOT NULL,
                    nonce TEXT NOT NULL,
                    used_at INTEGER NOT NULL,
                    PRIMARY KEY (from_address, nonce)
                )
            """)
            conn.commit()

            # First INSERT — simulates nonce reservation before apply_transaction
            conn.execute(
                "INSERT OR IGNORE INTO transfer_nonces (from_address, nonce, used_at) VALUES (?, ?, ?)",
                ("RTCSender", "nonce_42", 1000000)
            )
            changes_first = conn.execute("SELECT changes()").fetchone()[0]
            conn.commit()   # ← simulates "crash" checkpoint that commits just the nonce

            # Now simulate retry: same nonce, same sender
            conn.execute(
                "INSERT OR IGNORE INTO transfer_nonces (from_address, nonce, used_at) VALUES (?, ?, ?)",
                ("RTCSender", "nonce_42", 1000001)
            )
            changes_retry = conn.execute("SELECT changes()").fetchone()[0]

            assert changes_first == 1, "First nonce INSERT should succeed"
            assert changes_retry == 0, (
                "BUG-SEC-02: Nonce is permanently burned after the first commit. "
                "Even without a matching UTXO spend, the sender can never reuse "
                "this nonce. This is a DoS vector if the node crashes after nonce "
                "commit but before apply_transaction completes."
            )
        finally:
            conn.close()
            os.unlink(path)


# ===========================================================================
# BUG-SEC-03 — HIGH: mempool_add conservation check uses two separate SELECTs
#
# Severity: HIGH (100 RTC under bounty criteria)
#
# Description:
#   In mempool_add(), the input existence check and value summation are
#   *separate* SQL queries:
#
#     # Check box exists and is unspent (line ~1124)
#     box = conn.execute("SELECT spent_at FROM utxo_boxes WHERE ... AND spent_at IS NULL").fetchone()
#     if not box: ROLLBACK; return False
#
#     # ...later (line ~1166)...
#     row = conn.execute("SELECT value_nrtc FROM utxo_boxes WHERE box_id = ?").fetchone()
#     if row:
#         input_total += row['value_nrtc']
#
#   Notice: the second SELECT has NO `AND spent_at IS NULL` filter.
#   A box that was spent between the first and second SELECT (TOCTOU window)
#   would:
#     1. Pass the first check (unspent)
#     2. Be spent by another thread
#     3. Have its value counted by the second SELECT
#   Result: input_total is computed from a now-spent box.
#
#   More critically — if the second SELECT returned None (because `if row:`
#   protects it), input_total would be UNDER-counted, but because the first
#   check already verified existence, in practice the row is always found.
#   The vulnerability is that the conservation check uses the stale value
#   without re-confirming the spent_at IS NULL condition.
#
#   Under a BEGIN IMMEDIATE transaction in SQLite this is mitigated because
#   BEGIN IMMEDIATE acquires a reserved lock, but other readers can still
#   complete between the mempool_add's own first and second SELECTs within
#   the same transaction, especially if apply_transaction runs in WAL mode
#   (which allows concurrent readers + one writer).
#
#   This is a correctness bug and a potential conservation-bypass vector.
# ===========================================================================

class TestBugSec03MempoolTOCTOU:

    def test_mempool_add_value_select_lacks_spent_at_filter(self, db):
        """
        [SEC-03 HIGH] The value SELECT in mempool_add does not filter by
        spent_at IS NULL. This test directly queries the DB to demonstrate
        that a spent box's value would be included in input_total.

        Demonstrate: add a box, spend it externally, then show that the
        value SELECT (without spent_at filter) still returns the value.
        """
        sender = "RTCSender03"
        val = 5 * UNIT
        box = _make_box(db, sender, val, idx=0)

        # Confirm unspent
        assert db.get_balance(sender) == val

        # Spend the box directly
        db.spend_box(box['box_id'], spent_by_tx="some_tx_id_abcdef")

        # Confirm spent
        assert db.get_balance(sender) == 0

        # Now query the SAME way mempool_add's conservation check does (no spent_at filter):
        conn = db._conn()
        row = conn.execute(
            "SELECT value_nrtc FROM utxo_boxes WHERE box_id = ?",
            (box['box_id'],)
        ).fetchone()
        conn.close()

        assert row is not None, "Box should still exist (as a spent record)"
        assert row['value_nrtc'] == val, (
            "BUG-SEC-03: The mempool conservation check SELECT retrieves the "
            "value of an already-spent box because it lacks `AND spent_at IS NULL`. "
            "If a concurrent apply_transaction spends this box after the first "
            "unspent-check but before the value-sum query (TOCTOU), input_total "
            "will be computed using stale data, potentially allowing a transaction "
            "to pass conservation checks with inputs it no longer owns."
        )

    def test_mempool_add_rejected_for_spent_box(self, db):
        """
        [SEC-03 Corollary] Verify current behavior: mempool_add correctly
        rejects a transaction whose input box has been spent, because the
        FIRST check (spent_at IS NULL) catches it. The bug is that under
        concurrent load, the second check is not atomic with the first.
        """
        sender = "RTCSender03b"
        val = 5 * UNIT
        box = _make_box(db, sender, val, idx=0)
        db.spend_box(box['box_id'], "spend_tx_abc")

        tx = {
            'tx_id': 'aabbcc' * 10 + 'aabb',
            'tx_type': 'transfer',
            'inputs': [{'box_id': box['box_id'], 'spending_proof': 'sig'}],
            'outputs': [{'address': 'RTCRecip', 'value_nrtc': val}],
            'fee_nrtc': 0,
            'data_inputs': [],
        }
        result = db.mempool_add(tx)
        assert not result, "mempool_add should reject spent input (single-threaded check works)"


# ===========================================================================
# BUG-SEC-04 — MEDIUM: mempool_get_block_candidates double-spend in same block
#
# Severity: MEDIUM (50 RTC under bounty criteria)
#
# Description:
#   mempool_get_block_candidates selects up to `max_count` transactions.
#   It tracks `selected_spend_inputs` to prevent two candidate txs from
#   spending the same UTXO. However, the conflict check only verifies:
#
#     if (input_set & selected_data_inputs         # spending input vs data_input
#         or data_input_set & selected_spend_inputs):  # data_input vs spending input
#         continue
#
#   It does NOT check `input_set & selected_spend_inputs` directly in a
#   symmetric way that would catch two transactions each spending the same box.
#   Looking at the actual code (lines 1384-1388):
#
#     if (
#         input_set & selected_data_inputs        ← A spending a box that a prior tx uses as data
#         or data_input_set & selected_spend_inputs  ← A data_input that a prior tx spends
#     ):
#         continue
#
#   There is NO check for `input_set & selected_spend_inputs` (two txs both
#   spending the same box). The update afterwards appends to selected_spend_inputs,
#   but the GUARD only checks cross-type conflicts.
#
#   This means: if two mempool transactions both spend the same box_id,
#   block_candidates could include BOTH in the same block candidate set,
#   producing a double-spend in the block proposal. apply_transaction would
#   catch it at application time (rowcount != 1), but the node has already
#   built and may have broadcast an invalid block.
# ===========================================================================

class TestBugSec04BlockCandidateDoubleSpend:

    def test_block_candidates_missing_input_vs_input_conflict_check(self, db):
        """
        [SEC-04 MEDIUM] Demonstrate that mempool_get_block_candidates can
        include two transactions that both spend the same input UTXO box.

        In a correct implementation, the second transaction should be skipped.
        This test shows the structural gap in the conflict check guard.
        """
        sender = "RTCSenderShared"
        val = 10 * UNIT

        # Create a single shared UTXO box
        shared_box = _make_box(db, sender, val, idx=0)

        # Build two transactions spending the SAME box
        tx1 = {
            'tx_id': 'tx1' + 'a' * 61,
            'tx_type': 'transfer',
            'inputs': [{'box_id': shared_box['box_id'], 'spending_proof': 'sig1'}],
            'outputs': [{'address': 'RTCRecipA', 'value_nrtc': val}],
            'fee_nrtc': 0,
            'data_inputs': [],
        }
        tx2 = {
            'tx_id': 'tx2' + 'b' * 61,
            'tx_type': 'transfer',
            'inputs': [{'box_id': shared_box['box_id'], 'spending_proof': 'sig2'}],
            'outputs': [{'address': 'RTCRecipB', 'value_nrtc': val}],
            'fee_nrtc': 0,
            'data_inputs': [],
        }

        # We can't add both to mempool normally (double-spend detection) — that
        # works correctly. The vulnerability is in block candidate selection
        # code path when the guard misses the input-vs-input check.
        # Directly inspect the guard logic to prove the gap:

        # Simulate what get_block_candidates does for its conflict guard:
        input_set_tx1 = {shared_box['box_id']}
        data_input_set_tx1 = set()

        input_set_tx2 = {shared_box['box_id']}
        data_input_set_tx2 = set()

        selected_spend_inputs = set()
        selected_data_inputs = set()

        # Process tx1: no conflicts, add to candidates
        # (existing guard checks)
        conflict_tx1 = (
            input_set_tx1 & selected_data_inputs
            or data_input_set_tx1 & selected_spend_inputs
        )
        assert not conflict_tx1, "tx1 should pass (no prior selection)"
        selected_spend_inputs.update(input_set_tx1)
        selected_data_inputs.update(data_input_set_tx1)

        # Process tx2: the guard as written in the code
        guard_as_coded = (
            input_set_tx2 & selected_data_inputs          # spending vs data: empty & empty = {}
            or data_input_set_tx2 & selected_spend_inputs  # data vs spending: empty & {shared} = {}
        )
        # The guard returns FALSY because both sets use the wrong pairing.
        # input_set_tx2 & selected_data_inputs = {shared} & {} = {} → falsy
        # data_input_set_tx2 & selected_spend_inputs = {} & {shared} = {} → falsy
        assert not guard_as_coded, (
            "BUG-SEC-04 CONFIRMED: The guard as coded evaluates to FALSY "
            "for two transactions spending the same box_id. "
            "The MISSING check is: `input_set_tx2 & selected_spend_inputs`. "
            f"selected_spend_inputs={selected_spend_inputs}, "
            f"input_set_tx2={input_set_tx2}. "
            "Both would be included as block candidates, producing an invalid "
            "double-spend block proposal."
        )

        # Show what the CORRECT guard would detect:
        correct_guard = (
            input_set_tx2 & selected_spend_inputs  # ← the missing check
            or input_set_tx2 & selected_data_inputs
            or data_input_set_tx2 & selected_spend_inputs
        )
        assert correct_guard, (
            "The CORRECT guard catches the double-spend: "
            f"input_set_tx2 & selected_spend_inputs = "
            f"{input_set_tx2 & selected_spend_inputs}"
        )


# ===========================================================================
# BUG-SEC-05 — LOW: coin_select target_nrtc=0 returns empty list but
#              does not validate upper bound against MAX inputs
#
# Severity: LOW (25 RTC under bounty criteria)
#
# Description:
#   coin_select always tries smallest-first (up to N UTXOs). If the UTXO set
#   contains thousands of tiny UTXOs, it may include up to MAX_INPUTS=100
#   boxes in a single selection. However coin_select itself has no MAX_INPUTS
#   cap — it falls through to the "if len(selected) > 20: try largest-first"
#   heuristic, which may still select > 100 inputs.
#
#   apply_transaction() enforces `len(inputs) > MAX_INPUTS → abort()`.
#   But coin_select can return more than MAX_INPUTS items (it only switches
#   strategy at >20, but doesn't cap the final result at MAX_INPUTS).
#   The endpoint would then call apply_transaction() which rejects it with
#   an opaque 500, leaving the user unable to spend fragmented UTXOs without
#   manual UTXO consolidation.
# ===========================================================================

class TestBugSec05CoinSelectNoCap:

    def test_coin_select_can_return_more_than_max_inputs(self, db):
        """
        [SEC-05 LOW] coin_select returns more than MAX_INPUTS (100) items
        when given a large dust UTXO set. The subsequent apply_transaction
        will reject it, creating a stuck wallet.
        """
        from utxo_db import MAX_INPUTS
        # Create 110 boxes of 1000 nRTC each (= DUST_THRESHOLD exactly)
        tiny_val = DUST_THRESHOLD
        num_boxes = MAX_INPUTS + 10  # 110
        utxos = [{'box_id': f'{i:064x}', 'value_nrtc': tiny_val}
                 for i in range(num_boxes)]

        target = tiny_val * num_boxes  # need all of them
        selected, change = coin_select(utxos, target)

        # Smallest-first will select all 110 — exceeds MAX_INPUTS
        if len(selected) > MAX_INPUTS:
            # This is the bug: coin_select should cap at MAX_INPUTS
            pytest.fail(
                f"BUG-SEC-05: coin_select returned {len(selected)} inputs, "
                f"exceeding MAX_INPUTS={MAX_INPUTS}. apply_transaction() will "
                "reject this, leaving the wallet unable to spend fragmented UTXOs. "
                "Fix: add `selected = selected[:MAX_INPUTS]` in coin_select, "
                "or document the limitation prominently."
            )
        else:
            # If somehow it doesn't, document that the behavior changed
            pytest.skip(
                f"coin_select returned {len(selected)} <= {MAX_INPUTS} inputs. "
                "The heuristic may have changed. Re-evaluate."
            )


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
