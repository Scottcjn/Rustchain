"""
RustChain Python SDK
=====================

Official Python client for the RustChain blockchain API.

Features:
    - Wallet queries (balance, existence check)
    - Transaction sending
    - Epoch and miner information
    - Admin operations (requires admin key)

Installation:
    pip install rustchain-py

Usage:
    from rustchain import RustChainClient
    
    client = RustChainClient(node_url="https://50.28.86.131")
    
    # Query wallet balance
    balance = client.get_balance("my-wallet")
    print(f"Balance: {balance['balance_rtc']} RTC")
    
    # Check if wallet exists
    exists = client.check_wallet_exists("my-wallet")
    
    # Send transaction (requires admin key)
    result = client.transfer_rtc("from-wallet", "to-wallet", 10.0, admin_key="your-key")
"""

__version__ = "1.0.0"
__author__ = "RustChain Team"

from rustchain.client import RustChainClient
from rustchain.wallet import Wallet
from rustchain.transaction import Transaction
from rustchain.exceptions import RustChainError, WalletError, TransactionError

__all__ = [
    "RustChainClient",
    "Wallet",
    "Transaction",
    "RustChainError",
    "WalletError",
    "TransactionError",
]
