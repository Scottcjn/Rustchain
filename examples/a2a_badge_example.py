#!/usr/bin/env python3
"""
A2A Badge Integration Example

This example demonstrates how to integrate A2A badge tracking
into an agent application using the x402 protocol.

Usage:
    python examples/a2a_badge_example.py
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add tools directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from a2a_badge_verifier import A2ABadgeVerifier, WalletStats


class SimpleAgent:
    """
    Example agent that makes A2A payments and tracks badges.
    """
    
    def __init__(self, name: str, wallet: str):
        self.name = name
        self.wallet = wallet
        self.verifier = A2ABadgeVerifier()
        self.transactions = []
    
    def make_payment(self, recipient_wallet: str, amount: float, description: str = ""):
        """
        Make an A2A payment to another agent.
        
        Args:
            recipient_wallet: Recipient's wallet address
            amount: Payment amount in RTC
            description: Payment description
        """
        import hashlib
        import time
        
        # Generate transaction hash (simulated)
        tx_data = f"{self.wallet}:{recipient_wallet}:{amount}:{time.time()}"
        tx_hash = "0x" + hashlib.sha256(tx_data.encode()).hexdigest()
        
        # Create transaction record
        tx = self.verifier.verify_transaction(
            tx_hash=tx_hash,
            from_wallet=self.wallet,
            to_wallet=recipient_wallet,
            amount=amount,
            timestamp=datetime.now(),
            protocol="x402",
            block_height=1000000 + len(self.transactions)
        )
        
        self.transactions.append({
            "tx_hash": tx_hash,
            "recipient": recipient_wallet,
            "amount": amount,
            "timestamp": datetime.now(),
            "description": description
        })
        
        print(f"💸 Payment: {amount} RTC to {recipient_wallet[:10]}...")
        print(f"   Hash: {tx_hash[:20]}...")
        print(f"   Description: {description}")
        
        return tx
    
    def check_badges(self):
        """Check and display badge eligibility."""
        print(f"\n🏆 Badge Status for {self.name} ({self.wallet[:10]}...)\n")
        
        eligibility = self.verifier.check_badge_eligibility(self.wallet)
        
        earned = [b for b in eligibility if b.earned]
        pending = [b for b in eligibility if not b.earned]
        
        if earned:
            print(f"EARNED ({len(earned)}):")
            for badge in earned:
                print(f"  ✓ {badge.title} [{badge.rarity}]")
                print(f"    {badge.description[:60]}...")
        
        if pending:
            print(f"\nPENDING ({len(pending)}):")
            for badge in pending:
                pct = round(badge.current_progress / badge.threshold * 100, 1) if badge.threshold > 0 else 0
                bar_len = int(pct / 5)
                bar = "█" * bar_len + "░" * (20 - bar_len)
                print(f"  ○ {badge.title}")
                print(f"    [{bar}] {pct}% ({badge.current_progress}/{badge.threshold})")
        
        return earned, pending
    
    def generate_report(self, output_path: str = None):
        """
        Generate a comprehensive activity report.
        
        Args:
            output_path: Optional path to save JSON report
        """
        report = self.verifier.export_wallet_report(self.wallet)
        
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, default=str)
            print(f"📄 Report saved to {output_path}")
        
        return report


def run_example():
    """Run the A2A badge integration example."""
    
    print("=" * 70)
    print("A2A Badge Integration Example")
    print("=" * 70)
    
    # Create example agents
    agent1 = SimpleAgent(
        name="DataBot Alpha",
        wallet="0x1234567890abcdef1234567890abcdef12345678"
    )
    
    agent2 = SimpleAgent(
        name="ServiceBot Beta",
        wallet="0xabcdef1234567890abcdef1234567890abcdef12"
    )
    
    agent3 = SimpleAgent(
        name="APIBot Gamma",
        wallet="0x9876543210fedcba9876543210fedcba98765432"
    )
    
    # Simulate A2A economy
    print("\n📊 Simulating A2A Transaction Economy...\n")
    
    # Agent 1 makes payments to multiple agents
    print("--- Agent 1 Activity ---")
    for i in range(50):
        target = agent2 if i % 2 == 0 else agent3
        agent1.make_payment(
            recipient_wallet=target.wallet,
            amount=10.0 + (i % 5),
            description=f"API call #{i+1} - Data processing"
        )
    
    # Agent 2 makes payments
    print("\n--- Agent 2 Activity ---")
    for i in range(30):
        agent2.make_payment(
            recipient_wallet=agent1.wallet,
            amount=5.0 + (i % 3),
            description=f"Service response #{i+1}"
        )
    
    # Agent 3 makes payments
    print("\n--- Agent 3 Activity ---")
    for i in range(20):
        target = agent1 if i % 2 == 0 else agent2
        agent3.make_payment(
            recipient_wallet=target.wallet,
            amount=15.0 + (i % 10),
            description=f"Skill invocation #{i+1}"
        )
    
    # Check badge eligibility for all agents
    print("\n" + "=" * 70)
    print("BADGE ELIGIBILITY RESULTS")
    print("=" * 70)
    
    for agent in [agent1, agent2, agent3]:
        agent.check_badges()
        print()
    
    # Generate reports
    print("=" * 70)
    print("GENERATING REPORTS")
    print("=" * 70)
    
    report1 = agent1.generate_report()
    print(f"\n{agent1.name}:")
    print(f"  Total Transactions: {report1['statistics']['total_transactions']}")
    print(f"  Total Volume: {report1['statistics']['total_volume']} RTC")
    print(f"  Unique Counterparties: {report1['statistics']['unique_counterparties']}")
    print(f"  Badges Earned: {len(report1['earned_badges'])}")
    
    report2 = agent2.generate_report()
    print(f"\n{agent2.name}:")
    print(f"  Total Transactions: {report2['statistics']['total_transactions']}")
    print(f"  Total Volume: {report2['statistics']['total_volume']} RTC")
    print(f"  Badges Earned: {len(report2['earned_badges'])}")
    
    # Demonstrate x402 header validation
    print("\n" + "=" * 70)
    print("X402 HEADER VALIDATION DEMO")
    print("=" * 70)
    
    valid_headers = {
        "X-Payment-Amount": "100.5",
        "X-Payment-From": "0x1234567890abcdef1234567890abcdef12345678",
        "X-Payment-To": "0xabcdef1234567890abcdef1234567890abcdef12",
        "X-Payment-TxHash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
    }
    
    is_valid, error = agent1.verifier.verify_x402_headers(valid_headers)
    print(f"\n✓ Valid headers test: {'PASS' if is_valid else 'FAIL'}")
    if not is_valid:
        print(f"  Error: {error}")
    
    invalid_headers = {
        "X-Payment-Amount": "100.5",
        "X-Payment-From": "invalid_address",  # Invalid!
        "X-Payment-To": "0xabcdef1234567890abcdef1234567890abcdef12",
        "X-Payment-TxHash": "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
    }
    
    is_valid, error = agent1.verifier.verify_x402_headers(invalid_headers)
    print(f"✓ Invalid headers test: {'CORRECTLY REJECTED' if not is_valid else 'FAIL - should have rejected'}")
    if not is_valid:
        print(f"  Error: {error}")
    
    # Show badge metadata generation
    print("\n" + "=" * 70)
    print("BADGE METADATA GENERATION")
    print("=" * 70)
    
    if report1['earned_badges']:
        first_badge = report1['earned_badges'][0]
        metadata = agent1.verifier.generate_badge_metadata(
            badge_id=first_badge['badge_id'],
            wallet_address=agent1.wallet,
            earned_timestamp=datetime.now()
        )
        
        print(f"\nGenerated metadata for {first_badge['title']}:")
        print(json.dumps(metadata, indent=2, default=str)[:500] + "...")
    
    print("\n" + "=" * 70)
    print("EXAMPLE COMPLETE")
    print("=" * 70)
    print("\nNext steps:")
    print("1. Integrate A2ABadgeVerifier into your agent")
    print("2. Track all x402 transactions")
    print("3. Check badge eligibility periodically")
    print("4. Display earned badges in agent profile")
    print("\nFor more info, see docs/A2A_BADGE_SYSTEM.md")


if __name__ == "__main__":
    run_example()
