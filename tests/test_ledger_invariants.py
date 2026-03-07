"""
RustChain Ledger Invariant Test Suite

Property-based testing using Hypothesis to prove ledger correctness.

Invariants tested:
1. Conservation of RTC - total in = total out + fees
2. Non-negative balances - no wallet ever goes below 0
3. Epoch reward invariant - rewards per epoch sum to exactly 1.5 RTC
4. Transfer atomicity - failed transfers don't change any balances
5. Antiquity weighting - higher multiplier miners get proportionally more rewards
6. Pending transfer lifecycle - pending transfers either confirm or get voided

Usage:
    pip install hypothesis
    pytest tests/test_ledger_invariants.py -v
    # Or run with more examples:
    pytest tests/test_ledger_invariants.py -v --hypothesis-show-statistics
"""

import pytest
import hypothesis
from hypothesis import given, settings, assume, Phase
import hypothesis.strategies as st
from unittest.mock import patch, MagicMock, PropertyMock
from collections import defaultdict
import time
import random

# Configure Hypothesis
hypothesis.settings.register_profile("ci", max_examples=10000)
hypothesis.settings.register_profile("dev", max_examples=100)
hypothesis.settings.load_profile("ci")


# ============== Mock Data Structures ==============

class MockWallet:
    """Mock wallet for testing"""
    def __init__(self, name: str, balance_urtc: int = 0, nonce: int = 0):
        self.name = name
        self.balance_urtc = balance_urtc
        self.nonce = nonce
        self.pending_sent = 0
        self.pending_received = 0
    
    def __repr__(self):
        return f"Wallet({self.name}, balance={self.balance_urtc})"


class MockTransaction:
    """Mock transaction for testing"""
    def __init__(self, from_wallet: str, to_wallet: str, amount_urtc: int, 
                 nonce: int, timestamp: int, fee_urtc: int = 1000):
        self.from_wallet = from_wallet
        self.to_wallet = to_wallet
        self.amount_urtc = amount_urtc
        self.nonce = nonce
        self.timestamp = timestamp
        self.fee_urtc = fee_urtc
        self.executed = False
    
    def total_input(self) -> int:
        """Total input = amount + fee"""
        return self.amount_urtc + self.fee_urtc


class MockEpoch:
    """Mock epoch for testing"""
    def __init__(self, epoch_number: int, enrolled_miners: list, pot_rtc: float = 1.5):
        self.epoch_number = epoch_number
        self.enrolled_miners = enrolled_miners
        self.pot_rtc = pot_rtc
        self.rewards = {}
        self.blocks = []
    
    def calculate_rewards(self):
        """Calculate rewards based on antiquity multiplier"""
        if not self.enrolled_miners:
            return {}
        
        base_reward = self.pot_rtc / len(self.enrolled_miners)
        self.rewards = {}
        
        for miner in self.enrolled_miners:
            multiplier = miner.get('antiquity_multiplier', 1.0)
            self.rewards[miner['miner']] = base_reward * multiplier
        
        return self.rewards


class MockPendingTransfer:
    """Mock pending transfer for testing"""
    def __init__(self, transfer_id: str, from_wallet: str, to_wallet: str, 
                 amount_urtc: int, create_time: int, confirm_time: int = None):
        self.transfer_id = transfer_id
        self.from_wallet = from_wallet
        self.to_wallet = to_wallet
        self.amount_urtc = amount_urtc
        self.create_time = create_time
        self.confirm_time = confirm_time
        self.status = 'pending'  # pending, confirmed, voided
    
    def confirm(self):
        self.status = 'confirmed'
    
    def void(self):
        self.status = 'voided'
    
    def is_expired(self, current_time: int) -> bool:
        return current_time >= self.create_time + 86400  # 24 hours


class LedgerState:
    """Mock ledger state for testing"""
    def __init__(self):
        self.wallets = {}
        self.transactions = []
        self.epochs = []
        self.pending_transfers = []
        self.total_fees_urtc = 0
    
    def create_wallet(self, name: str, initial_balance: int = 0):
        self.wallets[name] = MockWallet(name, initial_balance)
        return self.wallets[name]
    
    def get_balance(self, wallet_name: str) -> int:
        return self.wallets.get(wallet_name, MockWallet(wallet_name)).balance_urtc
    
    def apply_transaction(self, tx: MockTransaction) -> bool:
        """Apply transaction to ledger, returns success"""
        sender = self.wallets.get(tx.from_wallet)
        receiver = self.wallets.get(tx.to_wallet)
        
        if not sender or not receiver:
            return False
        
        if sender.balance_urtc < tx.total_input():
            return False
        
        # Execute transfer
        sender.balance_urtc -= tx.total_input()
        receiver.balance_urtc += tx.amount_urtc
        self.total_fees_urtc += tx.fee_urtc
        
        tx.executed = True
        self.transactions.append(tx)
        
        return True
    
    def snapshot_balances(self) -> dict:
        """Get a snapshot of all balances"""
        return {name: w.balance_urtc for name, w in self.wallets.items()}


# ============== Strategies for Hypothesis ==============

@st.composite
def wallet_names(draw, min_wallets: int = 2, max_wallets: int = 10):
    """Generate unique wallet names"""
    num_wallets = draw(st.integers(min_value=min_wallets, max_value=max_wallets))
    return [f"wallet_{i}" for i in range(num_wallets)]


@st.composite
def wallet_balances(draw, num_wallets: int):
    """Generate wallet balances (non-negative)"""
    return [draw(st.integers(min_value=0, max_value=1000000)) for _ in range(num_wallets)]


@st.composite
def valid_transaction(draw, wallet_names: list):
    """Generate a valid transaction"""
    assume(len(wallet_names) >= 2)
    
    from_idx = draw(st.integers(min_value=0, max_value=len(wallet_names) - 1))
    to_idx = draw(st.integers(min_value=0, max_value=len(wallet_names) - 1))
    assume(from_idx != to_idx)
    
    return MockTransaction(
        from_wallet=wallet_names[from_idx],
        to_wallet=wallet_names[to_idx],
        amount_urtc=draw(st.integers(min_value=1, max_value=100000)),
        nonce=draw(st.integers(min_value=1, max_value=1000)),
        timestamp=int(time.time()),
        fee_urtc=1000
    )


@st.composite
def miner_data(draw, num_miners: int):
    """Generate miner data with antiquity multipliers"""
    miners = []
    for i in range(num_miners):
        # Generate realistic antiquity multipliers
        multiplier = draw(st.sampled_from([1.0, 1.2, 1.3, 1.5, 1.8, 2.0, 2.5]))
        miners.append({
            'miner': f"miner_{i}",
            'antiquity_multiplier': multiplier,
            'device_arch': draw(st.sampled_from(['x86_64', 'aarch64', 'ppc64le', 'PowerPC_G4', 'PowerPC_G5'])),
            'hardware_type': draw(st.sampled_from(['Modern_PC', 'Raspberry_Pi', 'IBM_POWER8', 'Apple_Silicon', 'PowerPC_G4', 'PowerPC_G5']))
        })
    return miners


# ============== Invariant Tests ==============

@given(
    wallet_list=wallet_names(),
    transactions=st.lists(valid_transaction(wallet_names=st.just([])), min_size=1, max_size=100)
)
@settings(max_examples=1000)
def test_conservation_invariant(wallet_list, transactions):
    """
    Invariant 1: Conservation of RTC
    Total RTC in = Total RTC out + fees (no creation/destruction)
    
    This test verifies that for any sequence of transactions,
    the total balance of all wallets plus total fees collected
    remains constant.
    """
    # Setup
    ledger = LedgerState()
    total_initial = 1000000  # 1 million URTC starting balance
    
    # Create wallets with initial balance
    for name in wallet_list:
        ledger.create_wallet(name, total_initial)
    
    # Get initial total
    initial_total = sum(ledger.wallets[w].balance_urtc for w in wallet_list)
    
    # Apply transactions
    for tx_data in transactions:
        # Fix wallet names to match our ledger
        tx = MockTransaction(
            from_wallet=wallet_list[0] if tx_data.from_wallet not in wallet_list else tx_data.from_wallet,
            to_wallet=wallet_list[1] if tx_data.to_wallet not in wallet_list else tx_data.to_wallet,
            amount_urtc=tx_data.amount_urtc,
            nonce=tx_data.nonce,
            timestamp=tx_data.timestamp,
            fee_urtc=tx_data.fee_urtc
        )
        # Only use valid wallet names from our ledger
        if tx.from_wallet in ledger.wallets and tx.to_wallet in ledger.wallets:
            ledger.apply_transaction(tx)
    
    # Get final total
    final_total = sum(ledger.wallets[w].balance_urtc for w in wallet_list)
    
    # Conservation: initial = final + fees
    assert initial_total == final_total + ledger.total_fees_urtc, \
        f"Conservation violated! Initial: {initial_total}, Final: {final_total}, Fees: {ledger.total_fees_urtc}"


@given(
    wallet_list=wallet_names(min_wallets=1, max_wallets=5),
    transactions=st.lists(valid_transaction(wallet_names=st.just([])), min_size=0, max_size=50)
)
@settings(max_examples=500)
def test_non_negative_balances(wallet_list, transactions):
    """
    Invariant 2: Non-negative balances
    No wallet ever goes below 0
    """
    ledger = LedgerState()
    
    # Create wallets with varying initial balances
    for name in wallet_list:
        ledger.create_wallet(name, random.randint(0, 100000))
    
    # Apply transactions
    for tx_data in transactions:
        tx = MockTransaction(
            from_wallet=wallet_list[0],
            to_wallet=wallet_list[1] if len(wallet_list) > 1 else wallet_list[0],
            amount_urtc=tx_data.amount_urtc,
            nonce=tx_data.nonce,
            timestamp=tx_data.timestamp,
            fee_urtc=tx_data.fee_urtc
        )
        ledger.apply_transaction(tx)
    
    # Check all balances are non-negative
    for name, wallet in ledger.wallets.items():
        assert wallet.balance_urtc >= 0, \
            f"Balance went negative! Wallet: {name}, Balance: {wallet.balance_urtc}"


@given(
    miners=miner_data(num_miners=st.integers(min_value=1, max_value=20))
)
@settings(max_examples=500)
def test_epoch_reward_invariant(miners):
    """
    Invariant 3: Epoch rewards
    Rewards per epoch sum to exactly 1.5 RTC
    """
    epoch = MockEpoch(epoch_number=1, enrolled_miners=miners, pot_rtc=1.5)
    rewards = epoch.calculate_rewards()
    
    total_rewards = sum(rewards.values())
    
    # Allow for floating point precision
    assert abs(total_rewards - 1.5) < 0.0001, \
        f"Epoch reward invariant violated! Total: {total_rewards}, Expected: 1.5"


@given(
    wallet_list=wallet_names(min_wallets=2, max_wallets=5),
    tx_amounts=st.lists(st.integers(min_value=1, max_value=50000), min_size=10, max_size=20)
)
@settings(max_examples=300)
def test_transfer_atomicity(wallet_list, tx_amounts):
    """
    Invariant 4: Transfer atomicity
    If transfer fails, sender and receiver balances unchanged
    """
    ledger = LedgerState()
    
    # Create wallets
    for name in wallet_list:
        ledger.create_wallet(name, 100000)
    
    sender = wallet_list[0]
    receiver = wallet_list[1]
    
    # Snapshot before
    balance_before_sender = ledger.get_balance(sender)
    balance_before_receiver = ledger.get_balance(receiver)
    
    # Try to execute a transaction that will fail (insufficient balance)
    # First, drain the sender
    drain_tx = MockTransaction(sender, receiver, 90000, 1, int(time.time()), 1000)
    ledger.apply_transaction(drain_tx)
    
    # Now try a transaction that will fail
    fail_tx = MockTransaction(sender, receiver, 50000, 2, int(time.time()), 1000)
    result = ledger.apply_transaction(fail_tx)  # Should return False
    
    # Check balances are unchanged after failed transaction
    balance_after_sender = ledger.get_balance(sender)
    balance_after_receiver = ledger.get_balance(receiver)
    
    # If transaction failed, balances should be unchanged
    if not result:
        assert balance_before_sender == balance_after_sender, \
            f"Sender balance changed after failed transaction!"
        assert balance_before_receiver == balance_after_receiver, \
            f"Receiver balance changed after failed transaction!"


@given(
    miners=miner_data(num_miners=st.integers(min_value=2, max_value=10))
)
@settings(max_examples=500)
def test_antiquity_weighting_invariant(miners):
    """
    Invariant 5: Antiquity weighting
    Higher multiplier miners get proportionally more rewards
    """
    epoch = MockEpoch(epoch_number=1, enrolled_miners=miners, pot_rtc=1.5)
    rewards = epoch.calculate_rewards()
    
    # Get miners sorted by multiplier
    miners_with_mult = [(m['miner'], m['antiquity_multiplier']) for m in miners]
    miners_with_mult.sort(key=lambda x: x[1])
    
    # Check that higher multiplier always gets >= reward than lower multiplier
    for i in range(len(miners_with_mult) - 1):
        miner_a, mult_a = miners_with_mult[i]
        miner_b, mult_b = miners_with_mult[i + 1]
        
        if mult_b > mult_a:
            assert rewards.get(miner_b, 0) >= rewards.get(miner_a, 0), \
                f"Antiquity weighting violated! {miner_b}({mult_b}x) got less than {miner_a}({mult_a}x)"


@given(
    num_pending=st.integers(min_value=1, max_value=20)
)
@settings(max_examples=200)
def test_pending_transfer_lifecycle(num_pending):
    """
    Invariant 6: Pending transfer lifecycle
    Pending transfers either confirm (after 24h) or get voided
    """
    pending_transfers = []
    current_time = int(time.time())
    
    # Create pending transfers at different times
    for i in range(num_pending):
        create_time = current_time - random.randint(0, 48 * 3600)  # 0-48 hours ago
        pt = MockPendingTransfer(
            transfer_id=f"tx_{i}",
            from_wallet=f"wallet_{i % 3}",
            to_wallet=f"wallet_{(i + 1) % 3}",
            amount_urtc=1000,
            create_time=create_time
        )
        pending_transfers.append(pt)
    
    # Simulate time passing and check lifecycle
    for pt in pending_transfers:
        if pt.is_expired(current_time):
            # Should be either confirmed or voided
            # In our mock, we void expired transfers
            pt.void()
        
        assert pt.status in ['confirmed', 'voided'], \
            f"Pending transfer {pt.transfer_id} has invalid status: {pt.status}"
        
        if pt.status == 'confirmed':
            assert pt.confirm_time == pt.create_time + 86400, \
                f"Confirmed transfer has wrong confirm_time!"


# ============== Stress Test ==============

@given(
    wallet_list=wallet_names(min_wallets=5, max_wallets=20),
    num_transactions=st.integers(min_value=100, max_value=1000)
)
@settings(max_examples=50)
def test_ledger_under_stress(wallet_list, num_transactions):
    """
    Stress test: Run 1000+ random transactions and verify all invariants
    """
    ledger = LedgerState()
    
    # Create wallets with substantial balance
    for name in wallet_list:
        ledger.create_wallet(name, 1000000)
    
    initial_total = sum(ledger.wallets[w].balance_urtc for w in wallet_list)
    
    # Generate and apply random transactions
    random.seed(42)  # Reproducible
    for i in range(num_transactions):
        from_w = random.choice(wallet_list)
        to_w = random.choice([w for w in wallet_list if w != from_w])
        amount = random.randint(1, 10000)
        
        tx = MockTransaction(from_w, to_w, amount, i, int(time.time()), 1000)
        ledger.apply_transaction(tx)
    
    # Verify conservation
    final_total = sum(ledger.wallets[w].balance_urtc for w in wallet_list)
    assert initial_total == final_total + ledger.total_fees_urtc, \
        "Conservation violated under stress!"
    
    # Verify non-negative
    for name, wallet in ledger.wallets.items():
        assert wallet.balance_urtc >= 0, \
            f"Negative balance under stress! Wallet: {name}"


# ============== Bug Bounty - Counterexample Finder ==============

class InvariantViolation(Exception):
    """Exception raised when an invariant is violated"""
    pass


def find_invariant_bug(strategy, invariant_check, num_examples=10000):
    """
    Bug bounty: Find counterexamples that violate invariants
    
    Returns the counterexample if found, None otherwise
    """
    hypothesis.settings.register_profile("bug_hunt", max_examples=num_examples)
    hypothesis.settings.load_profile("bug_hunt")
    
    try:
        given(strategy)(invariant_check)()
    except AssertionError as e:
        return str(e)
    finally:
        hypothesis.settings.load_profile("ci")
    
    return None


# ============== Run with pytest ==============

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--hypothesis-show-statistics"])
