"""
RustChain Transaction Operations
================================

High-level transaction building and sending utilities.
"""

from typing import Optional, Dict, Any, Tuple
from .client import RustChainClient
from .exceptions import TransactionError, AuthenticationError


class Transaction:
    """
    High-level transaction operations for RustChain.
    
    Provides transaction building, validation, and sending capabilities.
    
    Args:
        client: RustChainClient instance
    
    Example:
        >>> client = RustChainClient(admin_key="your-key")
        >>> tx = Transaction(client)
        >>> result = tx.send("from-wallet", "to-wallet", 10.0)
    """
    
    def __init__(self, client: RustChainClient) -> None:
        """
        Initialize Transaction handler with a RustChain client.
        
        Args:
            client: Authenticated RustChainClient instance for API communication.
                   Should have admin_key set for transaction operations.
        """
        self.client = client
    
    def send(
        self,
        from_wallet: str,
        to_wallet: str,
        amount_rtc: float,
        admin_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send RTC from one wallet to another.
        
        Args:
            from_wallet: Source wallet ID
            to_wallet: Destination wallet ID
            amount_rtc: Amount to transfer in RTC
            admin_key: Optional admin key override
        
        Returns:
            Transaction result dictionary with pending_id
        
        Raises:
            TransactionError: If transaction fails
            AuthenticationError: If admin key is missing
        
        Example:
            >>> result = tx.send("wallet1", "wallet2", 10.0)
            >>> print(f"Transaction ID: {result['pending_id']}")
        """
        if amount_rtc <= 0:
            raise TransactionError("Amount must be greater than 0")
        
        # Validate wallet names
        if not from_wallet or not to_wallet:
            raise TransactionError("Both from_wallet and to_wallet are required")
        
        try:
            result = self.client.transfer_rtc(
                from_wallet=from_wallet,
                to_wallet=to_wallet,
                amount_rtc=amount_rtc,
                admin_key=admin_key
            )
            
            if "error" in result:
                raise TransactionError(result["error"])
            
            return result
            
        except AuthenticationError:
            raise
        except Exception as e:
            raise TransactionError(f"Transaction failed: {str(e)}") from e
    
    def build_transfer(
        self,
        from_wallet: str,
        to_wallet: str,
        amount_rtc: float
    ) -> Dict[str, Any]:
        """
        Build a transaction without sending it.
        
        Useful for previewing transaction details before submission.
        
        Args:
            from_wallet: Source wallet ID
            to_wallet: Destination wallet ID
            amount_rtc: Amount to transfer in RTC
        
        Returns:
            Transaction preview dictionary
        
        Example:
            >>> preview = tx.build_transfer("wallet1", "wallet2", 10.0)
            >>> print(f"Will send {preview['amount_rtc']} RTC")
        """
        return {
            "from_miner": from_wallet,
            "to_miner": to_wallet,
            "amount_rtc": amount_rtc,
            "status": "preview"
        }
    
    def validate_transfer(
        self,
        from_wallet: str,
        to_wallet: str,
        amount_rtc: float
    ) -> Tuple[bool, str]:
        """
        Validate a transaction before sending.
        
        Checks:
            - Amount is positive
            - Wallet names are valid format
            - Source wallet exists (if possible)
        
        Args:
            from_wallet: Source wallet ID
            to_wallet: Destination wallet ID
            amount_rtc: Amount to transfer in RTC
        
        Returns:
            Tuple of (is_valid, message)
        
        Example:
            >>> is_valid, msg = tx.validate_transfer("wallet1", "wallet2", 10.0)
            >>> if is_valid:
            ...     print("Transaction is valid!")
        """
        if amount_rtc <= 0:
            return False, "Amount must be greater than 0"
        
        if not from_wallet:
            return False, "Source wallet is required"
        
        if not to_wallet:
            return False, "Destination wallet is required"
        
        if from_wallet == to_wallet:
            return False, "Cannot transfer to same wallet"
        
        # Check if source wallet exists
        if not self.client.check_wallet_exists(from_wallet):
            return False, f"Source wallet '{from_wallet}' does not exist"
        
        return True, "Transaction is valid"
