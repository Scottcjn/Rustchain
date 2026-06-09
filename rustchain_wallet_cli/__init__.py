#!/usr/bin/env python3
"""
RustChain Wallet CLI — Command-Line RTC Management

Stdlib-only wallet tool for RustChain. Create wallets, check balances,
send transfers — all from the terminal.

Compatible with existing rustchain_crypto.py wallet format.

Usage:
    rustchain-wallet create
    rustchain-wallet balance <wallet-id>
    rustchain-wallet send <to> <amount> --from <wallet> --password <pw>
    rustchain-wallet import <seed-phrase>
    rustchain-wallet export <wallet> --password <pw>

Bounty: #39
Wallet: klowagent
"""

__version__ = "1.0.0"
