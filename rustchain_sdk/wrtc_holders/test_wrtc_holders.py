#!/usr/bin/env python3
"""
Test version of wRTC holders with mock data

Usage:
    python3 test_wrtc_holders.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from wrtc_holders import (
    format_balance,
    get_wallet_label,
    print_header,
    print_holders,
    WRTC_SUPPLY
)


def test_with_mock_data():
    """Test with mock holder data"""

    print_header("wRTC Token Holder Snapshot (TEST MODE)")

    # Mock holder data
    mock_holders = [
        {
            "address": "3n7RJanhRghRzW2PBg1UbkV9syiod8iUMugTvLzwTRkW",
            "amount": "8296082000000",  # 8,296,082 wRTC
            "decimals": 6
        },
        {
            "address": "8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb",
            "amount": "4000000000",  # 4,000 wRTC
            "decimals": 6
        },
        {
            "address": "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1",
            "amount": "1000000000",  # 1,000 wRTC
            "decimals": 6
        },
        {
            "address": "9w2B7q3B8vYfNz3K7j8pM8pR9jQkL5mJ2jH5kP7mN8vT",
            "amount": "500000000",  # 500 wRTC
            "decimals": 6
        },
    ]

    print(f"\nMint: 12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X")
    print(f"Total Supply: {WRTC_SUPPLY:,} wRTC")
    print(f"Holders: {len(mock_holders)} (mock data)")
    print()

    print_header()
    print_holders(mock_holders)

    # Summary
    print_header("Summary")

    top_holder_balance = int(mock_holders[0].get("amount", "0")) / 10**6
    top_holder_pct = (top_holder_balance / WRTC_SUPPLY) * 100

    print(f"Total Holders: {len(mock_holders)}")
    print(f"Top Holder: {format_balance(mock_holders[0].get('amount', '0'))} wRTC ({top_holder_pct:.2f}%)")

    # Check for whales
    whales = [h for h in mock_holders if (int(h.get("amount", 0)) / 10**6) > (WRTC_SUPPLY * 0.01)]
    print(f"Whales (>1% supply): {len(whales)}")
    if whales:
        for whale in whales:
            balance = int(whale.get("amount", 0)) / 10**6
            wallet = whale.get("address", "Unknown")
            label = get_wallet_label(wallet)
            print(f"  - {wallet[:16]}...: {format_balance(whale.get('amount', '0'))} wRTC ({label})")

    print()
    print("Labels:")
    print("  [Reserve]   = Project reserve wallet")
    print("  [Raydium LP] = Liquidity pool on Raydium")
    print("  [Team]      = Team/Dev wallet")


if __name__ == "__main__":
    test_with_mock_data()
