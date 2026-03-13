"""
RustChain Wallet Operations
===========================

High-level wallet management and utilities.
"""

import re
from typing import Tuple, Optional
from .client import RustChainClient
from .exceptions import WalletError


class Wallet:
    """
    High-level wallet operations for RustChain.
    
    Provides wallet validation, registration guidance, and balance tracking.
    
    Args:
        client: RustChainClient instance
    
    Example:
        >>> client = RustChainClient()
        >>> wallet = Wallet(client)
        >>> is_valid, msg = wallet.validate_name("my-wallet")
    """
    
    # Wallet name validation regex
    WALLET_NAME_RE: re.Pattern = re.compile(r"^[a-z0-9][a-z0-9\-]{1,62}[a-z0-9]$")
    
    def __init__(self, client: RustChainClient) -> None:
        """
        Initialize Wallet handler with a RustChain client.
        
        Args:
            client: RustChainClient instance for API communication.
                   Used for balance queries and wallet registration.
        """
        self.client = client
    
    def validate_name(self, name: str) -> Tuple[bool, str]:
        """
        Validate a wallet name according to RustChain rules.
        
        Rules:
            - 3 to 64 characters
            - Lowercase alphanumeric and hyphens only
            - Must start and end with letter or digit
        
        Args:
            name: Proposed wallet name
        
        Returns:
            Tuple of (is_valid, message)
        
        Example:
            >>> is_valid, msg = wallet.validate_name("my-wallet")
            >>> if is_valid:
            ...     print("Valid wallet name!")
        """
        if not name:
            return False, "Wallet name cannot be empty"
        if len(name) < 3:
            return False, "Wallet name must be at least 3 characters"
        if len(name) > 64:
            return False, "Wallet name must be 64 characters or fewer"
        if name != name.lower():
            return False, "Wallet name must be lowercase"
        if not self.WALLET_NAME_RE.match(name):
            return False, "Wallet name may only contain lowercase letters, digits, and hyphens"
        
        return True, "Valid wallet name"
    
    def exists(self, name: str) -> bool:
        """
        Check if a wallet exists on the network.
        
        Args:
            name: Wallet name to check
        
        Returns:
            True if wallet exists, False otherwise
        
        Example:
            >>> if wallet.exists("my-wallet"):
            ...     print("Wallet already registered!")
        """
        return self.client.check_wallet_exists(name)
    
    def get_balance(self, name: str) -> float:
        """
        Get wallet balance in RTC.
        
        Args:
            name: Wallet name
        
        Returns:
            Balance in RTC (0.0 if wallet doesn't exist)
        
        Example:
            >>> balance = wallet.get_balance("my-wallet")
            >>> print(f"Balance: {balance} RTC")
        """
        result = self.client.get_balance(name)
        if "error" in result:
            return 0.0
        return result.get("balance_rtc", 0.0)
    
    def get_pending(self, name: str) -> list:
        """
        Get pending transfers for a wallet.
        
        Args:
            name: Wallet name
        
        Returns:
            List of pending transfer dictionaries
        
        Example:
            >>> pending = wallet.get_pending("my-wallet")
            >>> for transfer in pending:
            ...     print(f"Pending: {transfer['amount_rtc']} RTC")
        """
        return self.client.get_pending_transfers(name)
    
    def registration_guide(self, name: str) -> str:
        """
        Get wallet registration instructions.
        
        Args:
            name: Desired wallet name
        
        Returns:
            Multi-line instruction string
        
        Example:
            >>> print(wallet.registration_guide("my-wallet"))
        """
        is_valid, msg = self.validate_name(name)
        if not is_valid:
            return f"Invalid wallet name '{name}': {msg}"
        
        exists = self.exists(name)
        if exists:
            return f"Wallet '{name}' already exists on the RustChain network."
        
        return f"""
Wallet Registration Guide for: {name}
{'=' * 50}

Option 1 -- Claim a Bounty (Automatic Registration)
----------------------------------------------------
Comment on any RustChain bounty issue on GitHub with:
  "I would like to claim this bounty. Wallet: {name}"

Your wallet is registered when the first RTC transfer is made.


Option 2 -- Install RustChain Wallet GUI
-----------------------------------------
Download the wallet from the rustchain-bounties repo releases.
The wallet will generate a BIP39 seed phrase and Ed25519 keypair automatically.


Option 3 -- Open Registration Issue
------------------------------------
Create an issue on Scottcjn/rustchain-bounties titled:
  "Wallet Registration: {name}"

An admin will set up your wallet entry.


Next Steps
----------
1. Choose a registration method above
2. Wait for confirmation (usually within 24 hours)
3. Start earning RTC through bounties and mining!

For more info: https://github.com/Scottcjn/bounty-concierge
"""
    
    def check_eligibility(self, name: str) -> dict:
        """
        Check lottery/epoch eligibility for a wallet.
        
        Args:
            name: Wallet name
        
        Returns:
            Eligibility information dictionary
        
        Example:
            >>> eligible = wallet.check_eligibility("my-wallet")
            >>> if eligible.get('eligible'):
            ...     print("Eligible for epoch rewards!")
        """
        return self.client.check_eligibility(name)
