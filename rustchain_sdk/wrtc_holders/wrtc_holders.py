#!/usr/bin/env python3
"""
wRTC Holder Snapshot Tool

Queries Solana blockchain to list all wallets holding wRTC tokens.

Usage:
    python3 wrtc_holders.py

Requirements:
    pip install requests
"""

import json
import sys
from typing import List, Dict, Optional
import requests

# wRTC Token Details
WRTC_MINT = "12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X"
WRTC_DECIMALS = 6
WRTC_SUPPLY = 8_300_000

# Known wallet addresses for labeling
KNOWN_WALLETS = {
    "3n7RJanhRghRzW2PBg1UbkV9syiod8iUMugTvLzwTRkW": "[Reserve]",
    "8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb": "[Raydium LP]",
    "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1": "[Team]",
}


class SolanaClient:
    """Simple Solana RPC client"""

    # List of public RPC endpoints to try
    RPC_ENDPOINTS = [
        "https://api.mainnet-beta.solana.com",
        "https://solana-api.projectserum.com",
        "https://rpc.ankr.com/solana",
    ]

    def __init__(self, rpc_url: str = None):
        """
        Initialize Solana client

        Args:
            rpc_url: Solana RPC endpoint (defaults to first public endpoint)
        """
        self.rpc_url = rpc_url or self.RPC_ENDPOINTS[0]

    def rpc_call(self, method: str, params: list = None) -> Dict:
        """
        Make RPC call to Solana node

        Args:
            method: RPC method name
            params: Method parameters

        Returns:
            RPC response as dict
        """
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or []
        }

        try:
            response = requests.post(
                self.rpc_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
            result = response.json()

            if "error" in result:
                print(f"RPC Error: {result['error']}", file=sys.stderr)
                return None

            return result.get("result")

        except Exception as e:
            print(f"Request failed: {e}", file=sys.stderr)
            return None

    def get_token_largest_accounts(self, mint: str) -> Optional[List[Dict]]:
        """
        Get largest token holders for a mint

        Args:
            mint: Token mint address

        Returns:
            List of holder accounts with balances
        """
        result = self.rpc_call("getTokenLargestAccounts", [mint])

        if result is None:
            return None

        return result.get("value", [])

    def get_token_supply(self, mint: str) -> Optional[int]:
        """
        Get token supply for a mint

        Args:
            mint: Token mint address

        Returns:
            Token supply as integer (in base units)
        """
        result = self.rpc_call("getTokenSupply", [mint])

        if result is None:
            return None

        value = result.get("value", {})
        amount_str = value.get("amount", "0")
        decimals = value.get("decimals", WRTC_DECIMALS)

        return int(amount_str)

    def get_account_info(self, pubkey: str) -> Optional[Dict]:
        """
        Get account information

        Args:
            pubkey: Public key of the account

        Returns:
            Account information
        """
        result = self.rpc_call("getAccountInfo", [pubkey])

        if result is None:
            return None

        return result.get("value")


def format_balance(balance_raw, decimals: int = WRTC_DECIMALS) -> str:
    """
    Format raw balance to human-readable string

    Args:
        balance_raw: Raw balance (in base units) as int or str
        decimals: Token decimals

    Returns:
        Formatted balance string with commas
    """
    # Convert to int if string
    if isinstance(balance_raw, str):
        balance_raw = int(balance_raw)

    balance = balance_raw / (10 ** decimals)
    return f"{balance:,.0f}"


def get_wallet_label(wallet: str) -> str:
    """
    Get label for known wallet addresses

    Args:
        wallet: Wallet address

    Returns:
        Label string or empty string
    """
    return KNOWN_WALLETS.get(wallet, "")


def print_header(title: str = None):
    """Print section header"""
    if title:
        print(title)
    print("=" * 70)


def print_holders(holders: List[Dict], decimals: int = WRTC_DECIMALS):
    """
    Print holder list in formatted table

    Args:
        holders: List of holder accounts
        decimals: Token decimals
    """
    print(f"{'Rank':<5} {'Wallet':<45} {'Balance':>12} {'% Supply':<10} {'Label':<10}")
    print("-" * 85)

    for rank, holder in enumerate(holders, 1):
        wallet = holder.get("address", "Unknown")
        balance_raw = int(holder.get("amount", "0"))
        balance = balance_raw / (10 ** decimals)

        # Calculate percentage of supply
        pct_supply = (balance / WRTC_SUPPLY) * 100

        label = get_wallet_label(wallet)

        # Truncate wallet address for display
        wallet_short = wallet[:44]

        print(f"{rank:<5} {wallet_short:<45} {format_balance(balance_raw):>12} {pct_supply:>6.2f}% {label:<10}")


def main():
    """Main function"""
    print_header("wRTC Token Holder Snapshot")

    # Initialize Solana client
    client = SolanaClient()

    print(f"\nMint: {WRTC_MINT}")
    print(f"Total Supply: {WRTC_SUPPLY:,} wRTC")
    print()

    # Get token supply
    print("Fetching token supply...")
    supply = client.get_token_supply(WRTC_MINT)
    if supply:
        supply_formatted = supply / (10 ** WRTC_DECIMALS)
        print(f"Actual Supply: {supply_formatted:,} wRTC")
    print()

    # Get largest holders
    print("Fetching token holders...")
    holders = client.get_token_largest_accounts(WRTC_MINT)

    if holders is None:
        print("Failed to fetch holders. Please check your RPC endpoint.", file=sys.stderr)
        sys.exit(1)

    print(f"Holders found: {len(holders)}")
    print()

    # Print holders
    print_header()
    print_holders(holders)

    # Print summary
    print_header("Summary")

    # Calculate concentration metrics
    if holders:
        top_holder_balance = int(holders[0].get("amount", "0")) / (10 ** WRTC_DECIMALS)
        top_holder_pct = (top_holder_balance / WRTC_SUPPLY) * 100

        print(f"Total Holders: {len(holders)}")
        print(f"Top Holder: {format_balance(holders[0].get('amount', '0'))} wRTC ({top_holder_pct:.2f}%)")

        # Calculate Gini coefficient (concentration)
        total_balance = sum(int(h.get("amount", 0)) for h in holders) / (10 ** WRTC_DECIMALS)
        if len(holders) > 1:
            gini_num = sum(abs(i - j) for i in range(len(holders)) for j in range(len(holders)))
            gini_den = len(holders) * len(holders)
            gini = gini_num / gini_den if gini_den > 0 else 0
            print(f"Gini Coefficient: {gini:.3f} (0 = equal, 1 = concentrated)")

        # Check for whales (>1% of supply)
        whales = [h for h in holders if (int(h.get("amount", 0)) / (10 ** WRTC_DECIMALS)) > (WRTC_SUPPLY * 0.01)]
        print(f"Whales (>1% supply): {len(whales)}")
        if whales:
            for whale in whales:
                balance = int(whale.get("amount", 0)) / (10 ** WRTC_DECIMALS)
                wallet = whale.get("address", "Unknown")
                label = get_wallet_label(wallet)
                print(f"  - {wallet[:16]}...: {format_balance(whale.get('amount', '0'))} wRTC ({label})")

    print()
    print("Labels:")
    print("  [Reserve]   = Project reserve wallet")
    print("  [Raydium LP] = Liquidity pool on Raydium")
    print("  [Team]      = Team/Dev wallet")


if __name__ == "__main__":
    main()
