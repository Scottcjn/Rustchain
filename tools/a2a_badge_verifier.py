#!/usr/bin/env python3
"""
A2A Transaction Badge Verification Tool

This module provides verification and tracking for Agent-to-Agent (A2A) 
transaction badges on the RustChain network using x402 protocol.

Usage:
    python a2a_badge_verifier.py verify <wallet_address>
    python a2a_badge_verifier.py progress <wallet_address> <badge_id>
    python a2a_badge_verifier.py list <wallet_address>
    python a2a_badge_verifier.py check-transaction <tx_hash>
"""

import json
import hashlib
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
import argparse


class BadgeTier(Enum):
    """Badge rarity tiers."""
    MYTHIC = "Mythic"
    LEGENDARY = "Legendary"
    EPIC = "Epic"
    RARE = "Rare"
    UNCOMMON = "Uncommon"
    COMMON = "Common"
    
    @property
    def color(self) -> str:
        colors = {
            "Mythic": "#FF1493",    # Deep Pink
            "Legendary": "#FFD700",  # Gold
            "Epic": "#9370DB",       # Purple
            "Rare": "#4169E1",       # Blue
            "Uncommon": "#32CD32",   # Green
            "Common": "#C0C0C0",     # Silver
        }
        return colors[self.value]
    
    @property
    def stars(self) -> int:
        stars = {
            "Mythic": 6,
            "Legendary": 5,
            "Epic": 4,
            "Rare": 3,
            "Uncommon": 2,
            "Common": 1,
        }
        return stars[self.value]


@dataclass
class A2ATransaction:
    """Represents a verified A2A transaction."""
    tx_hash: str
    from_wallet: str
    to_wallet: str
    amount: float
    timestamp: datetime
    protocol: str
    block_height: int
    verified: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BadgeCriteria:
    """Criteria for earning a badge."""
    badge_id: str
    title: str
    criteria_type: str
    threshold: int
    current_progress: int = 0
    earned: bool = False
    earned_timestamp: Optional[datetime] = None
    description: str = ""
    rarity: str = ""


@dataclass
class WalletStats:
    """Statistics for a wallet's A2A activity."""
    wallet_address: str
    total_transactions: int = 0
    total_volume: float = 0.0
    unique_counterparties: int = 0
    counterparties: List[str] = field(default_factory=list)
    first_transaction: Optional[datetime] = None
    last_transaction: Optional[datetime] = None
    protocols_used: List[str] = field(default_factory=list)
    monthly_volume: Dict[str, float] = field(default_factory=dict)


class A2ABadgeVerifier:
    """
    Verifies A2A transactions and checks badge eligibility.
    
    This class provides methods to:
    - Verify individual x402 transactions
    - Track wallet statistics
    - Check badge eligibility
    - Generate badge metadata
    """
    
    def __init__(self, schema_path: Optional[str] = None):
        """
        Initialize the verifier.
        
        Args:
            schema_path: Path to the badge schema JSON file
        """
        self.schema_path = schema_path or "schemas/relic_a2a_badges.json"
        self.badges_schema = self._load_schema()
        self.transaction_cache: Dict[str, A2ATransaction] = {}
        self.wallet_stats: Dict[str, WalletStats] = {}
        
    def _load_schema(self) -> Dict:
        """Load the badge schema from JSON file."""
        try:
            with open(self.schema_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: Schema file not found at {self.schema_path}")
            return {"badges": []}
        except json.JSONDecodeError as e:
            print(f"Error parsing schema: {e}")
            return {"badges": []}
    
    def verify_x402_headers(self, headers: Dict[str, str]) -> Tuple[bool, str]:
        """
        Verify x402 payment headers.
        
        Args:
            headers: HTTP headers from the transaction
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        required_headers = [
            'X-Payment-Amount',
            'X-Payment-From',
            'X-Payment-To',
            'X-Payment-TxHash'
        ]
        
        missing = [h for h in required_headers if h not in headers]
        if missing:
            return False, f"Missing required headers: {', '.join(missing)}"
        
        # Validate wallet address format (Base/Ethereum style)
        from_addr = headers.get('X-Payment-From', '')
        to_addr = headers.get('X-Payment-To', '')
        
        if not re.match(r'^0x[a-fA-F0-9]{40}$', from_addr):
            return False, "Invalid X-Payment-From address format"
        
        if not re.match(r'^0x[a-fA-F0-9]{40}$', to_addr):
            return False, "Invalid X-Payment-To address format"
        
        # Validate amount
        try:
            amount = float(headers['X-Payment-Amount'])
            if amount <= 0:
                return False, "Payment amount must be positive"
        except ValueError:
            return False, "Invalid payment amount format"
        
        # Validate tx hash
        tx_hash = headers.get('X-Payment-TxHash', '')
        if not re.match(r'^0x[a-fA-F0-9]{64}$', tx_hash):
            return False, "Invalid transaction hash format"
        
        return True, ""
    
    def verify_transaction(
        self,
        tx_hash: str,
        from_wallet: str,
        to_wallet: str,
        amount: float,
        timestamp: datetime,
        protocol: str = "x402",
        block_height: int = 0
    ) -> A2ATransaction:
        """
        Verify and record an A2A transaction.
        
        Args:
            tx_hash: Transaction hash
            from_wallet: Sender wallet address
            to_wallet: Receiver wallet address
            amount: Transaction amount
            timestamp: Transaction timestamp
            protocol: Payment protocol used
            block_height: Block height when transaction occurred
            
        Returns:
            Verified A2ATransaction object
        """
        # Validate addresses
        if not re.match(r'^0x[a-fA-F0-9]{40}$', from_wallet):
            raise ValueError(f"Invalid from_wallet address: {from_wallet}")
        
        if not re.match(r'^0x[a-fA-F0-9]{40}$', to_wallet):
            raise ValueError(f"Invalid to_wallet address: {to_wallet}")
        
        # Validate amount
        if amount <= 0:
            raise ValueError("Transaction amount must be positive")
        
        # Create transaction record
        tx = A2ATransaction(
            tx_hash=tx_hash,
            from_wallet=from_wallet,
            to_wallet=to_wallet,
            amount=amount,
            timestamp=timestamp,
            protocol=protocol,
            block_height=block_height
        )
        
        # Cache transaction
        self.transaction_cache[tx_hash] = tx
        
        # Update wallet statistics
        self._update_wallet_stats(from_wallet, tx, is_sender=True)
        self._update_wallet_stats(to_wallet, tx, is_sender=False)
        
        return tx
    
    def _update_wallet_stats(
        self,
        wallet: str,
        tx: A2ATransaction,
        is_sender: bool
    ):
        """Update statistics for a wallet based on a transaction."""
        if wallet not in self.wallet_stats:
            self.wallet_stats[wallet] = WalletStats(wallet_address=wallet)
        
        stats = self.wallet_stats[wallet]
        stats.total_transactions += 1
        stats.total_volume += tx.amount
        
        # Track counterparties
        counterparty = tx.to_wallet if is_sender else tx.from_wallet
        if counterparty not in stats.counterparties:
            stats.counterparties.append(counterparty)
            stats.unique_counterparties = len(stats.counterparties)
        
        # Track timestamps
        if stats.first_transaction is None or tx.timestamp < stats.first_transaction:
            stats.first_transaction = tx.timestamp
        if stats.last_transaction is None or tx.timestamp > stats.last_transaction:
            stats.last_transaction = tx.timestamp
        
        # Track protocols
        if tx.protocol not in stats.protocols_used:
            stats.protocols_used.append(tx.protocol)
        
        # Track monthly volume
        month_key = tx.timestamp.strftime("%Y-%m")
        if month_key not in stats.monthly_volume:
            stats.monthly_volume[month_key] = 0.0
        stats.monthly_volume[month_key] += tx.amount
    
    def get_wallet_stats(self, wallet_address: str) -> Optional[WalletStats]:
        """Get statistics for a wallet."""
        return self.wallet_stats.get(wallet_address)
    
    def check_badge_eligibility(self, wallet_address: str) -> List[BadgeCriteria]:
        """
        Check which badges a wallet is eligible for.
        
        Args:
            wallet_address: Wallet to check
            
        Returns:
            List of BadgeCriteria objects with eligibility status
        """
        stats = self.wallet_stats.get(wallet_address)
        if not stats:
            return []
        
        eligible_badges = []
        
        for badge_def in self.badges_schema.get("badges", []):
            criteria = self._check_single_badge(badge_def, stats)
            eligible_badges.append(criteria)
        
        return eligible_badges
    
    def _check_single_badge(
        self,
        badge_def: Dict,
        stats: WalletStats
    ) -> BadgeCriteria:
        """Check eligibility for a single badge."""
        criteria_def = badge_def.get("criteria", {})
        criteria_type = criteria_def.get("type", "")
        threshold = criteria_def.get("threshold", 0)
        
        current_progress = 0
        earned = False
        
        # Check different criteria types
        if criteria_type == "a2a_transactions":
            current_progress = stats.total_transactions
            earned = current_progress >= threshold
            
        elif criteria_type == "a2a_unique_counterparties":
            current_progress = stats.unique_counterparties
            earned = current_progress >= threshold
            
        elif criteria_type == "x402_exclusive":
            # Check if only x402 protocol is used
            if stats.protocols_used == ["x402"]:
                current_progress = stats.total_transactions
                earned = current_progress >= threshold
            else:
                current_progress = 0
                earned = False
                
        elif criteria_type == "multi_protocol":
            current_progress = len(stats.protocols_used)
            earned = current_progress >= threshold
            
        elif criteria_type == "a2a_monthly_volume_leader":
            # This would require network-wide comparison
            # For now, just show current monthly volume
            current_month = datetime.now().strftime("%Y-%m")
            current_progress = int(stats.monthly_volume.get(current_month, 0))
            earned = False  # Would need network-wide check
            
        elif criteria_type == "first_a2a_transaction":
            # Special case - would need network-wide tracking
            current_progress = 1 if stats.total_transactions > 0 else 0
            earned = False  # Would need genesis tracking
        
        return BadgeCriteria(
            badge_id=badge_def.get("nft_id", ""),
            title=badge_def.get("title", ""),
            criteria_type=criteria_type,
            threshold=threshold,
            current_progress=current_progress,
            earned=earned,
            description=badge_def.get("description", ""),
            rarity=badge_def.get("rarity", "")
        )
    
    def get_progress(
        self,
        wallet_address: str,
        badge_id: str
    ) -> Optional[BadgeCriteria]:
        """
        Get progress toward a specific badge.
        
        Args:
            wallet_address: Wallet to check
            badge_id: Badge ID to check progress for
            
        Returns:
            BadgeCriteria with progress info, or None if badge not found
        """
        badge_def = None
        for b in self.badges_schema.get("badges", []):
            if b.get("nft_id") == badge_id:
                badge_def = b
                break
        
        if not badge_def:
            return None
        
        stats = self.wallet_stats.get(wallet_address)
        if not stats:
            return None
        
        return self._check_single_badge(badge_def, stats)
    
    def generate_badge_metadata(
        self,
        badge_id: str,
        wallet_address: str,
        earned_timestamp: Optional[datetime] = None
    ) -> Optional[Dict]:
        """
        Generate NFT metadata for an earned badge.
        
        Args:
            badge_id: Badge ID
            wallet_address: Owner wallet
            earned_timestamp: When badge was earned
            
        Returns:
            Badge metadata dictionary
        """
        badge_def = None
        for b in self.badges_schema.get("badges", []):
            if b.get("nft_id") == badge_id:
                badge_def = b
                break
        
        if not badge_def:
            return None
        
        timestamp = earned_timestamp or datetime.utcnow()
        
        # Generate unique badge hash
        badge_data = f"{badge_id}:{wallet_address}:{timestamp.isoformat()}"
        badge_hash = hashlib.sha256(badge_data.encode()).hexdigest()
        
        metadata = {
            "nft_id": badge_id,
            "title": badge_def.get("title", ""),
            "class": badge_def.get("class", ""),
            "description": badge_def.get("description", ""),
            "emotional_resonance": badge_def.get("emotional_resonance", {}),
            "symbol": badge_def.get("symbol", ""),
            "visual_anchor": badge_def.get("visual_anchor", ""),
            "rarity": badge_def.get("rarity", ""),
            "soulbound": badge_def.get("soulbound", True),
            "owner": wallet_address,
            "earned_timestamp": timestamp.isoformat() + "Z",
            "badge_hash": badge_hash,
            "version": "1.0"
        }
        
        return metadata
    
    def list_available_badges(self) -> List[Dict]:
        """List all available A2A badges."""
        return self.badges_schema.get("badges", [])
    
    def export_wallet_report(self, wallet_address: str) -> Dict:
        """
        Export a comprehensive report for a wallet's A2A activity.
        
        Args:
            wallet_address: Wallet to report on
            
        Returns:
            Dictionary with full wallet report
        """
        stats = self.wallet_stats.get(wallet_address)
        if not stats:
            return {"error": "Wallet not found"}
        
        eligibility = self.check_badge_eligibility(wallet_address)
        earned_badges = [b for b in eligibility if b.earned]
        pending_badges = [b for b in eligibility if not b.earned]
        
        report = {
            "wallet_address": wallet_address,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "statistics": {
                "total_transactions": stats.total_transactions,
                "total_volume": stats.total_volume,
                "unique_counterparties": stats.unique_counterparties,
                "first_transaction": stats.first_transaction.isoformat() if stats.first_transaction else None,
                "last_transaction": stats.last_transaction.isoformat() if stats.last_transaction else None,
                "protocols_used": stats.protocols_used,
                "monthly_volume": stats.monthly_volume
            },
            "earned_badges": [asdict(b) for b in earned_badges],
            "pending_badges": [asdict(b) for b in pending_badges],
            "badge_progress_percentage": round(
                len(earned_badges) / len(eligibility) * 100, 2
            ) if eligibility else 0
        }
        
        return report


def load_mock_transactions(verifier: A2ABadgeVerifier):
    """Load mock transactions for testing/demo purposes."""
    import random
    
    wallets = [
        "0x1234567890abcdef1234567890abcdef12345678",
        "0xabcdef1234567890abcdef1234567890abcdef12",
        "0x9876543210fedcba9876543210fedcba98765432",
        "0xfedcba9876543210fedcba9876543210fedcba98",
        "0x5555555555555555555555555555555555555555",
    ]
    
    base_time = datetime.now() - timedelta(days=30)
    
    for i in range(150):
        from_wallet = random.choice(wallets)
        to_wallet = random.choice([w for w in wallets if w != from_wallet])
        
        tx = verifier.verify_transaction(
            tx_hash=f"0x{''.join(random.choices('0123456789abcdef', k=64))}",
            from_wallet=from_wallet,
            to_wallet=to_wallet,
            amount=round(random.uniform(1, 100), 2),
            timestamp=base_time + timedelta(hours=i),
            protocol="x402",
            block_height=1000000 + i
        )
    
    print(f"Loaded {len(verifier.transaction_cache)} mock transactions")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="A2A Transaction Badge Verification Tool"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Verify wallet badges")
    verify_parser.add_argument("wallet", help="Wallet address to check")
    verify_parser.add_argument("--mock", action="store_true", help="Load mock transactions")
    
    # Progress command
    progress_parser = subparsers.add_parser("progress", help="Check badge progress")
    progress_parser.add_argument("wallet", help="Wallet address")
    progress_parser.add_argument("badge_id", help="Badge ID to check")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List available badges")
    
    # Report command
    report_parser = subparsers.add_parser("report", help="Generate wallet report")
    report_parser.add_argument("wallet", help="Wallet address")
    report_parser.add_argument("--output", "-o", help="Output file path")
    
    args = parser.parse_args()
    
    verifier = A2ABadgeVerifier()
    
    if args.command == "list":
        badges = verifier.list_available_badges()
        print(f"\nAvailable A2A Badges ({len(badges)} total):\n")
        for badge in badges:
            tier = badge.get("rarity", "Unknown")
            title = badge.get("title", "Unknown")
            badge_id = badge.get("nft_id", "")
            symbol = badge.get("symbol", "")
            print(f"  {symbol} [{tier}] {title}")
            print(f"     ID: {badge_id}")
            print(f"     {badge.get('description', '')[:100]}...")
            print()
    
    elif args.command == "verify":
        if args.mock:
            load_mock_transactions(verifier)
        
        eligibility = verifier.check_badge_eligibility(args.wallet)
        if not eligibility:
            print(f"No data for wallet: {args.wallet}")
            print("Use --mock to load sample transactions")
            return
        
        print(f"\nBadge Eligibility for {args.wallet}:\n")
        earned = [b for b in eligibility if b.earned]
        pending = [b for b in eligibility if not b.earned]
        
        if earned:
            print(f"EARNED ({len(earned)}):")
            for badge in earned:
                print(f"  ✓ {badge.title} ({badge.rarity})")
        
        if pending:
            print(f"\nPENDING ({len(pending)}):")
            for badge in pending:
                pct = round(badge.current_progress / badge.threshold * 100, 1) if badge.threshold > 0 else 0
                print(f"  ○ {badge.title}: {badge.current_progress}/{badge.threshold} ({pct}%)")
    
    elif args.command == "progress":
        if args.mock:
            load_mock_transactions(verifier)
        
        progress = verifier.get_progress(args.wallet, args.badge_id)
        if not progress:
            print(f"Badge not found: {args.badge_id}")
            return
        
        pct = round(progress.current_progress / progress.threshold * 100, 1) if progress.threshold > 0 else 0
        status = "✓ EARNED" if progress.earned else f"{pct}% complete"
        
        print(f"\nProgress: {progress.title}")
        print(f"Status: {status}")
        print(f"Progress: {progress.current_progress}/{progress.threshold}")
        print(f"Description: {progress.description}")
    
    elif args.command == "report":
        if args.mock:
            load_mock_transactions(verifier)
        
        report = verifier.export_wallet_report(args.wallet)
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2)
            print(f"Report saved to {args.output}")
        else:
            print(json.dumps(report, indent=2))
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
