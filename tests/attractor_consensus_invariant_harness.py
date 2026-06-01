"""
ATTRACTOR: Consensus Invariant Harness
======================================
This module provides a reusable adversarial test harness for RustChain 
consensus invariants. Future contributors can use this template to submit
small, self-contained tests that pin a specific invariant.

SUBMISSION GRAMMAR
------------------
1. One PR titled 'attractor: consensus-invariant harness' (for this initial setup)
   or 'attractor: <invariant_name>' for future submissions.
2. The body of the PR must include:
    - This reusable template.
    - The acceptance rubric.
    - The example invariant tests demonstrating the harness.

ACCEPTANCE RUBRIC
-----------------
ACCEPT if:
    - The test defines a clear one-invariant-per-test grammar.
    - The test includes an objective accept/reject assertion.
    - The invariant is not a trivial tautology (e.g., '1 == 1').
    - The tests pass against current main branch without flakiness.
    - The invariant being pinned is explicitly documented in the docstring.

REJECT if:
    - Examples are flaky (e.g., relying on unpredictable timeouts or threading).
    - The test is trivial or does not actually evaluate a protocol consensus rule.
    - The template is modified in a way that makes future evaluations inconsistent.

"""

import os
import sqlite3
import tempfile
import time
import pytest
from pathlib import Path

# Adjust path to import node modules
import sys
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "node"))

from utxo_db import UtxoDB, UNIT

class ConsensusInvariantHarness:
    """
    Reusable harness for testing RustChain consensus invariants.
    Provides a sterile test environment (DB + UtxoDB instance) 
    for each invariant test.
    """
    def __init__(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.db_fd)
        self._init_db()
        self.utxo_db = UtxoDB(self.db_path)
        self.utxo_db.init_tables()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER DEFAULT 0)")
        conn.commit()
        conn.close()

    def teardown(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

@pytest.fixture
def invariant_harness():
    """Pytest fixture yielding a clean ConsensusInvariantHarness."""
    harness = ConsensusInvariantHarness()
    yield harness
    harness.teardown()


# =====================================================================
# EXAMPLE INVARIANT TESTS
# =====================================================================

def test_invariant_double_spend_is_rejected(invariant_harness):
    """
    INVARIANT: An unspent transaction output (UTXO) can only be spent once.
    Double-spend attempts must be rejected by the protocol.
    """
    harness = invariant_harness
    utxo_db = harness.utxo_db
    
    # 1. Setup: Create a genesis coinbase UTXO for 'alice'
    initial_mint = 100 * UNIT
    utxo_db.apply_transaction(
        {
            "tx_type": "mining_reward",
            "inputs": [],
            "outputs": [{"address": "alice", "value_nrtc": initial_mint}],
            "timestamp": int(time.time()),
            "_allow_minting": True,
        },
        block_height=1
    )
    
    # Verify Alice's balance
    assert utxo_db.get_balance("alice") == initial_mint
    
    # Find Alice's UTXO box
    alice_boxes = utxo_db.get_unspent_for_address("alice")
    assert len(alice_boxes) == 1
    alice_box = alice_boxes[0]
    
    # 2. Action: Create a transaction spending Alice's box to Bob
    tx_spend_1 = {
        "tx_type": "transfer",
        "inputs": [{"box_id": alice_box["box_id"]}],
        "outputs": [{"address": "bob", "value_nrtc": initial_mint}],
        "timestamp": int(time.time())
    }
    
    # First spend should succeed
    success_1 = utxo_db.apply_transaction(tx_spend_1, block_height=2)
    assert success_1 is True, "Valid transfer should be accepted"
    assert utxo_db.get_balance("bob") == initial_mint
    assert utxo_db.get_balance("alice") == 0
    
    # 3. Adversarial Action: Attempt to spend the same box again (Double Spend)
    tx_spend_2 = {
        "tx_type": "transfer",
        "inputs": [{"box_id": alice_box["box_id"]}],
        "outputs": [{"address": "charlie", "value_nrtc": initial_mint}],
        "timestamp": int(time.time()) + 1
    }
    
    # Second spend MUST fail
    success_2 = utxo_db.apply_transaction(tx_spend_2, block_height=3)
    assert success_2 is False, "Double spend transaction was incorrectly accepted"
    assert utxo_db.get_balance("charlie") == 0, "Charlie should not receive funds from a double spend"


def test_invariant_tx_preserves_total_supply(invariant_harness):
    """
    INVARIANT: Standard transfers (non-coinbase) must not mint or burn tokens.
    Sum of inputs must exactly equal sum of outputs (plus implicit fee).
    """
    harness = invariant_harness
    utxo_db = harness.utxo_db
    
    # 1. Setup: Give Alice some tokens
    initial_supply = 50 * UNIT
    utxo_db.apply_transaction(
        {
            "tx_type": "mining_reward",
            "inputs": [],
            "outputs": [{"address": "alice", "value_nrtc": initial_supply}],
            "timestamp": int(time.time()),
            "_allow_minting": True,
        },
        block_height=1
    )
    
    alice_boxes = utxo_db.get_unspent_for_address("alice")
    box_id = alice_boxes[0]["box_id"]
    
    # 2. Adversarial Action: Attempt to transfer MORE than the input value
    adversarial_tx = {
        "tx_type": "transfer",
        "inputs": [{"box_id": box_id}],
        "outputs": [{"address": "bob", "value_nrtc": initial_supply + (10 * UNIT)}],  # Creating 10 RTC out of thin air
        "timestamp": int(time.time())
    }
    
    success = utxo_db.apply_transaction(adversarial_tx, block_height=2)
    
    # Assertion: Transaction must be rejected because inputs < outputs
    assert success is False, "Transaction creating tokens out of thin air was accepted"
    assert utxo_db.get_balance("bob") == 0, "Bob received illegally minted tokens"

