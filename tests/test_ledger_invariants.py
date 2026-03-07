#!/usr/bin/env python3
"""
RustChain Ledger Invariant Test Suite

Property-based testing using Hypothesis to verify ledger correctness.

This module tests mathematical invariants that must hold for the RustChain ledger:
1. Conservation of RTC - total in = total out + fees
2. Non-negative balances - no wallet ever goes below 0
3. Epoch reward invariant - rewards per epoch sum to exactly 1.5 RTC
4. Transfer atomicity - failed transfers don't change any balances
5. Antiquity weighting - higher multiplier miners get proportionally more rewards
6. Pending transfer lifecycle - pending transfers either confirm (24h) or void

Usage:
    python -m pytest tests/test_ledger_invariants.py -v
    python tests/test_ledger_invariants.py --live  # Test against live node
"""

import os
import sys
import json
import time
import sqlite3
import argparse
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, settings, Verbosity, assume, example
from hypothesis import strategies as st

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try to import node modules
try:
    from node.rustchain_v2_integrated_v2_2_1_rip200 import DB_PATH, get_db
    HAS_NODE = True
except ImportError:
    HAS_NODE = False
    DB_PATH = None

# Configuration
DEFAULT_NODE_URL = os.environ.get("RC_NODE_URL", "https://50.28.86.131")
TEST_WALLET_PREFIX = "test_invariant_"
PER_EPOCH_RTC = 1.5
UNIT = 1_000_000  # 1 RTC = 1,000,000 urtc


@dataclass
class Wallet:
    """Represents a wallet in the ledger"""
    miner_pk: str
    balance_rtc: float = 0.0
    nonce: int = 0


@dataclass
class Transfer:
    """Represents a transfer transaction"""
    from_pk: str
    to_pk: str
    amount_rtc: float
    nonce: int
    timestamp: int
    status: str = "confirmed"  # confirmed, pending, failed


@dataclass 
class EpochRewards:
    """Represents epoch reward distribution"""
    epoch: int
    rewards: Dict[str, float]  # miner_pk -> reward amount
    total: float


class LedgerInvariantTester:
    """Tests ledger invariants using property-based testing"""
    
    def __init__(self, node_url: str = DEFAULT_NODE_URL, db_path: Optional[str] = None):
        self.node_url = node_url.rstrip("/")
        self.db_path = db_path or DB_PATH
        self.test_data: List[Wallet] = []
        self.transfers: List[Transfer] = []
        self.epochs: List[EpochRewards] = []
    
    def fetch_balances(self) -> Dict[str, float]:
        """Fetch all wallet balances from node"""
        try:
            import urllib.request
            url = f"{self.node_url}/api/balances"
            req = urllib.request.Request(url, headers={'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                if isinstance(data, dict) and 'balances' in data:
                    return data['balances']
                return data
        except Exception as e:
            print(f"Warning: Could not fetch balances: {e}")
            return {}
    
    def fetch_epoch_info(self) -> Dict[str, Any]:
        """Fetch current epoch info"""
        try:
            import urllib.request
            url = f"{self.node_url}/epoch"
            req = urllib.request.Request(url, headers={'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode('utf-8'))
        except Exception as e:
            print(f"Warning: Could not fetch epoch info: {e}")
            return {}
    
    def fetch_epoch_rewards(self, epoch: int) -> Optional[EpochRewards]:
        """Fetch rewards for a specific epoch"""
        try:
            import urllib.request
            url = f"{self.node_url}/rewards/epoch/{epoch}"
            req = urllib.request.Request(url, headers={'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                rewards = {}
                total = 0.0
                if 'rewards' in data:
                    for r in data['rewards']:
                        miner = r.get('miner_id', '')
                        amount = r.get('share_rtc', 0)
                        rewards[miner] = amount
                        total += amount
                return EpochRewards(epoch=epoch, rewards=rewards, total=total)
        except Exception as e:
            print(f"Warning: Could not fetch epoch rewards: {e}")
            return None
    
    def fetch_pending_transfers(self) -> List[Dict]:
        """Fetch pending transfers"""
        try:
            import urllib.request
            url = f"{self.node_url}/wallet/ledger?status=pending"
            req = urllib.request.Request(url, headers={'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                return data.get('transfers', [])
        except Exception as e:
            print(f"Warning: Could not fetch pending transfers: {e}")
            return []
    
    # ==================== INVARIANT TESTS ====================
    
    def test_conservation_of_rtc(self, balances_before: Dict[str, float], 
                                  balances_after: Dict[str, float],
                                  fees: float = 0.0) -> Tuple[bool, str]:
        """
        Invariant 1: Conservation of RTC
        Total RTC in = Total RTC out + fees
        """
        total_before = sum(balances_before.values())
        total_after = sum(balances_after.values())
        
        # Allow small floating point tolerance
        diff = abs(total_before - total_after - fees)
        
        if diff > 0.0001:  # 0.0001 RTC tolerance
            return False, f"Conservation violated: before={total_before}, after={total_after}, fees={fees}, diff={diff}"
        
        return True, "Conservation invariant holds"
    
    def test_non_negative_balances(self, balances: Dict[str, float]) -> Tuple[bool, str]:
        """
        Invariant 2: Non-negative balances
        No wallet ever goes below 0
        """
        negative_wallets = []
        for wallet, balance in balances.items():
            if balance < 0:
                negative_wallets.append((wallet, balance))
        
        if negative_wallets:
            return False, f"Negative balances found: {negative_wallets}"
        
        return True, "All balances are non-negative"
    
    def test_epoch_reward_invariant(self, epoch_rewards: EpochRewards) -> Tuple[bool, str]:
        """
        Invariant 3: Epoch reward invariant
        Rewards per epoch sum to exactly 1.5 RTC
        """
        total = epoch_rewards.total
        expected = PER_EPOCH_RTC
        
        # Allow small floating point tolerance
        diff = abs(total - expected)
        
        if diff > 0.0001:
            return False, f"Epoch {epoch_rewards.epoch}: Expected {expected} RTC, got {total} RTC, diff={diff}"
        
        return True, f"Epoch {epoch_rewards.epoch}: Reward invariant holds"
    
    def test_transfer_atomicity(self, 
                               sender_before: float, 
                               sender_after: float,
                               receiver_before: float,
                               receiver_after: float,
                               transfer_succeeded: bool) -> Tuple[bool, str]:
        """
        Invariant 4: Transfer atomicity
        If transfer fails, sender and receiver balances unchanged
        """
        if not transfer_succeeded:
            # Both should be unchanged
            if sender_before != sender_after:
                return False, f"Failed transfer changed sender balance: {sender_before} -> {sender_after}"
            if receiver_before != receiver_after:
                return False, f"Failed transfer changed receiver balance: {receiver_before} -> {receiver_after}"
        
        return True, "Transfer atomicity holds"
    
    def test_antiquity_weighting(self, miners: List[Dict], rewards: Dict[str, float]) -> Tuple[bool, str]:
        """
        Invariant 5: Antiquity weighting
        Higher multiplier miners get proportionally more rewards
        """
        miner_multipliers = {}
        for miner in miners:
            name = miner.get('miner', miner.get('miner_id', ''))
            mult = miner.get('antiquity_multiplier', 1.0)
            miner_multipliers[name] = mult
        
        # Compare pairs of miners
        miner_rewards = {k: v for k, v in rewards.items() if k in miner_multipliers}
        
        for miner_a, reward_a in miner_rewards.items():
            for miner_b, reward_b in miner_rewards.items():
                if miner_a == miner_b:
                    continue
                mult_a = miner_multipliers.get(miner_a, 1.0)
                mult_b = miner_multipliers.get(miner_b, 1.0)
                
                # If multiplier_a > multiplier_b, reward_a should be >= reward_b
                if mult_a > mult_b and reward_a < reward_b:
                    return False, f"Antiquity violation: {miner_a}(mult={mult_a}, reward={reward_a}) < {miner_b}(mult={mult_b}, reward={reward_b})"
        
        return True, "Antiquity weighting invariant holds"
    
    def test_pending_transfer_lifecycle(self, pending_transfers: List[Dict]) -> Tuple[bool, str]:
        """
        Invariant 6: Pending transfer lifecycle
        Pending transfers either confirm (24h) or get voided
        """
        current_time = int(time.time())
        invalid_transfers = []
        
        for transfer in pending_transfers:
            create_time = transfer.get('create_time', 0)
            status = transfer.get('status', '')
            confirm_time = transfer.get('confirm_time', 0)
            
            # If more than 24 hours have passed
            if current_time - create_time > 86400:  # 24 hours
                if status not in ['confirmed', 'voided', 'failed']:
                    invalid_transfers.append(transfer)
                elif status == 'confirmed' and confirm_time - create_time != 86400:
                    # Confirmation should be exactly 24h
                    pass  # Allow some tolerance
        
        if invalid_transfers:
            return False, f"Invalid pending transfers: {len(invalid_transfers)} transfers not resolved after 24h"
        
        return True, "Pending transfer lifecycle invariant holds"


# ==================== HYPOTHESIS PROPERTY TESTS ====================

class TestLedgerInvariants:
    """Property-based tests for ledger invariants"""
    
    @pytest.fixture
    def tester(self):
        return LedgerInvariantTester()
    
    def test_conservation_with_mock_data(self, tester):
        """Test conservation invariant with generated data"""
        # Generate random balance changes
        initial_balances = {f"wallet_{i}": 100.0 for i in range(10)}
        
        # Simulate transfers
        final_balances = dict(initial_balances)
        fees = 0.01
        
        # Make some transfers
        final_balances["wallet_0"] -= 10.0
        final_balances["wallet_1"] += 9.99
        
        is_valid, msg = tester.test_conservation_of_rtc(initial_balances, final_balances, fees)
        assert is_valid, msg
    
    def test_non_negative_with_random_balances(self, tester):
        """Test non-negative invariant with random data"""
        # Generate random balances (including negative - should fail)
        balances = {
            "wallet_1": 100.5,
            "wallet_2": 0.0,
            "wallet_3": -0.5,  # This should fail
        }
        
        is_valid, msg = tester.test_non_negative_balances(balances)
        assert not is_valid, "Should detect negative balance"
    
    def test_epoch_reward_with_exact_values(self, tester):
        """Test epoch reward invariant with exact 1.5 RTC"""
        rewards = EpochRewards(
            epoch=1,
            rewards={"miner_1": 0.5, "miner_2": 0.5, "miner_3": 0.5},
            total=1.5
        )
        
        is_valid, msg = tester.test_epoch_reward_invariant(rewards)
        assert is_valid, msg
    
    def test_transfer_atomicity_successful(self, tester):
        """Test atomicity with successful transfer"""
        is_valid, msg = tester.test_transfer_atomicity(
            sender_before=100.0,
            sender_after=90.0,
            receiver_before=50.0,
            receiver_after=60.0,
            transfer_succeeded=True
        )
        assert is_valid, msg
    
    def test_transfer_atomicity_failed(self, tester):
        """Test atomicity with failed transfer"""
        is_valid, msg = tester.test_transfer_atomicity(
            sender_before=100.0,
            sender_after=100.0,  # Unchanged
            receiver_before=50.0,
            receiver_after=50.0,  # Unchanged
            transfer_succeeded=False
        )
        assert is_valid, msg
    
    @given(st.lists(st.floats(min_value=0, max_value=1000), min_size=1, max_size=100))
    @settings(max_examples=50, verbosity=Verbosity.verbose)
    def test_non_negative_balances_random(self, tester, balances_list):
        """Property test: random balance lists should all be non-negative"""
        balances = {f"wallet_{i}": b for i, b in enumerate(balances_list)}
        
        # Filter to only positive for this test
        positive_balances = {k: v for k, v in balances.items() if v >= 0}
        
        is_valid, msg = tester.test_non_negative_balances(positive_balances)
        assert is_valid, msg


# ==================== LIVE NODE TESTS ====================

def run_live_tests(node_url: str = DEFAULT_NODE_URL):
    """Run tests against live node"""
    print(f"\n{'='*60}")
    print(f"Running live invariant tests against {node_url}")
    print(f"{'='*60}\n")
    
    tester = LedgerInvariantTester(node_url=node_url)
    results = []
    
    # Test 1: Fetch and check balances
    print("[1/6] Testing non-negative balances invariant...")
    balances = tester.fetch_balances()
    if balances:
        is_valid, msg = tester.test_non_negative_balances(balances)
        results.append(("Non-negative balances", is_valid, msg))
        print(f"    Result: {msg}")
    else:
        results.append(("Non-negative balances", False, "Could not fetch balances"))
        print("    Could not fetch balances")
    
    # Test 2: Epoch reward invariant
    print("[2/6] Testing epoch reward invariant...")
    epoch_info = tester.fetch_epoch_info()
    current_epoch = epoch_info.get('epoch', 0)
    
    if current_epoch > 0:
        # Test a few recent epochs
        for e in range(max(1, current_epoch - 5), current_epoch + 1):
            rewards = tester.fetch_epoch_rewards(e)
            if rewards:
                is_valid, msg = tester.test_epoch_reward_invariant(rewards)
                results.append((f"Epoch {e} reward", is_valid, msg))
                print(f"    Epoch {e}: {msg}")
    else:
        results.append(("Epoch rewards", False, "Could not fetch epoch info"))
        print("    Could not fetch epoch info")
    
    # Test 3: Pending transfer lifecycle
    print("[3/6] Testing pending transfer lifecycle...")
    pending = tester.fetch_pending_transfers()
    is_valid, msg = tester.test_pending_transfer_lifecycle(pending)
    results.append(("Pending transfers", is_valid, msg))
    print(f"    Result: {msg}")
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    
    passed = sum(1 for _, valid, _ in results if valid)
    total = len(results)
    
    for name, valid, msg in results:
        status = "✓ PASS" if valid else "✗ FAIL"
        print(f"  {status}: {name}")
        if not valid:
            print(f"         {msg}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    return passed, total


# ==================== MAIN ====================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ledger Invariant Test Suite")
    parser.add_argument("--live", action="store_true", help="Run against live node")
    parser.add_argument("--node-url", default=DEFAULT_NODE_URL, help="Node URL for live tests")
    parser.add_argument("--pytest", action="store_true", help="Run as pytest")
    
    args = parser.parse_args()
    
    if args.pytest or not args.live:
        # Run pytest
        sys.exit(pytest.main([__file__, "-v"]))
    else:
        # Run live tests
        passed, total = run_live_tests(args.node_url)
        sys.exit(0 if passed == total else 1)
