"""
RustChain API Client
====================

Core client for interacting with the RustChain blockchain node.
"""

import requests
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin

from .exceptions import NetworkError, RustChainError, AuthenticationError


class RustChainClient:
    """
    RustChain blockchain API client.
    
    Args:
        node_url: URL of the RustChain node (default: https://50.28.86.131)
        admin_key: Optional admin key for privileged operations
        timeout: Request timeout in seconds (default: 10)
    
    Example:
        >>> client = RustChainClient()
        >>> balance = client.get_balance("my-wallet")
        >>> print(f"Balance: {balance['balance_rtc']} RTC")
    """
    
    def __init__(
        self,
        node_url: str = "https://50.28.86.131",
        admin_key: Optional[str] = None,
        timeout: int = 10
    ):
        """
        Initialize RustChain client with connection parameters.
        
        Sets up the HTTP session with optional admin authentication and configures
        the node URL for all subsequent API calls.
        
        Args:
            node_url: Base URL of the RustChain node API. Defaults to production node.
            admin_key: Optional admin key for privileged endpoints. If provided,
                      automatically added to request headers as 'X-Admin-Key'.
            timeout: Request timeout in seconds. Prevents hanging on slow responses.
        
        Note:
            SSL verification is disabled by default as the node uses self-signed certificates.
            For production use with proper certificates, enable verification.
        """
        self.node_url = node_url.rstrip('/')
        self.admin_key = admin_key
        self.timeout = timeout
        self.session = requests.Session()
        self.session.verify = False  # Node uses self-signed cert
        
        if admin_key:
            self.session.headers.update({"X-Admin-Key": admin_key})
    
    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request to RustChain node.
        
        Args:
            method: HTTP method (GET/POST)
            endpoint: API endpoint path
            params: URL query parameters
            data: JSON body data
            headers: Additional headers
        
        Returns:
            Parsed JSON response as dictionary
        
        Raises:
            NetworkError: If connection fails
            RustChainError: If API returns error
        """
        url = urljoin(self.node_url, endpoint)
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=data,
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
            
        except requests.ConnectionError as e:
            raise NetworkError(f"Could not connect to node at {self.node_url}") from e
        except requests.Timeout as e:
            raise NetworkError(f"Request to node timed out ({self.timeout}s)") from e
        except requests.HTTPError as e:
            status_code = e.response.status_code if e.response else None
            if status_code == 401 or status_code == 403:
                raise AuthenticationError("Admin key required or invalid") from e
            raise RustChainError(f"HTTP {status_code}: {e}", status_code=status_code) from e
        except ValueError as e:
            raise RustChainError("Node returned non-JSON response") from e
    
    # =========================================================================
    # Wallet Operations
    # =========================================================================
    
    def get_balance(self, miner_id: str) -> Dict[str, Any]:
        """
        Get wallet balance for a miner/wallet ID.
        
        Args:
            miner_id: Wallet or miner identifier
        
        Returns:
            Dictionary with miner_id and balance_rtc
        
        Example:
            >>> balance = client.get_balance("my-wallet")
            >>> print(f"Balance: {balance['balance_rtc']} RTC")
        """
        return self._request("GET", "/balance", params={"miner_id": miner_id})
    
    def check_wallet_exists(self, miner_id: str) -> bool:
        """
        Check if a wallet exists on the RustChain network.
        
        Args:
            miner_id: Wallet or miner identifier
        
        Returns:
            True if wallet exists, False otherwise
        
        Example:
            >>> if client.check_wallet_exists("my-wallet"):
            ...     print("Wallet exists!")
        """
        try:
            result = self.get_balance(miner_id)
            return "error" not in result
        except NetworkError:
            return False
    
    def get_pending_transfers(
        self, 
        miner_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get pending transfers for a wallet.
        
        Args:
            miner_id: Wallet or miner identifier
        
        Returns:
            List of pending transfer dictionaries
        
        Example:
            >>> pending = client.get_pending_transfers("my-wallet")
            >>> for transfer in pending:
            ...     print(f"Pending: {transfer['amount_rtc']} RTC")
        """
        result = self._request("GET", "/wallet/pending", params={"miner_id": miner_id})
        if isinstance(result, list):
            return result
        return result.get("pending", [])
    
    def transfer_rtc(
        self,
        from_wallet: str,
        to_wallet: str,
        amount_rtc: float,
        admin_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transfer RTC between wallets.
        
        Requires admin key for authorization.
        
        Args:
            from_wallet: Source wallet ID
            to_wallet: Destination wallet ID
            amount_rtc: Amount to transfer in RTC
            admin_key: Optional admin key override
        
        Returns:
            Transaction result with pending_id
        
        Example:
            >>> result = client.transfer_rtc("wallet1", "wallet2", 10.0)
            >>> print(f"Transaction ID: {result['pending_id']}")
        """
        key = admin_key or self.admin_key
        if not key:
            raise AuthenticationError("Admin key required for transfers")
        
        headers = {"X-Admin-Key": key}
        data = {
            "from_miner": from_wallet,
            "to_miner": to_wallet,
            "amount_rtc": amount_rtc
        }
        return self._request("POST", "/wallet/transfer", data=data, headers=headers)
    
    # =========================================================================
    # Network & Epoch Information
    # =========================================================================
    
    def get_epoch_info(self) -> Dict[str, Any]:
        """
        Get current epoch and slot information.
        
        Returns:
            Dictionary with epoch, slot, and enrolled miners
        
        Example:
            >>> epoch = client.get_epoch_info()
            >>> print(f"Current epoch: {epoch['epoch']}")
        """
        return self._request("GET", "/epoch")
    
    def get_active_miners(self) -> List[Dict]:
        """
        Get list of currently attesting miners.
        
        Returns:
            List of miner dictionaries
        
        Example:
            >>> miners = client.get_active_miners()
            >>> print(f"Active miners: {len(miners)}")
        """
        return self._request("GET", "/api/miners")
    
    def get_all_holders(self, admin_key: Optional[str] = None) -> List[Dict]:
        """
        Get all wallet balances (admin only).
        
        Args:
            admin_key: Optional admin key override
        
        Returns:
            List of wallet dictionaries with miner_id, amount_rtc, category
        
        Example:
            >>> holders = client.get_all_holders()
            >>> for holder in holders[:5]:
            ...     print(f"{holder['miner_id']}: {holder['amount_rtc']} RTC")
        """
        key = admin_key or self.admin_key
        if not key:
            raise AuthenticationError("Admin key required for holder listing")
        
        headers = {"X-Admin-Key": key}
        result = self._request("GET", "/api/balances", headers=headers)
        return result.get("balances", [])
    
    def get_holder_stats(self, admin_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Get aggregated statistics across all wallets (admin only).
        
        Args:
            admin_key: Optional admin key override
        
        Returns:
            Dictionary with aggregate statistics
        
        Example:
            >>> stats = client.get_holder_stats()
            >>> print(f"Total wallets: {stats['total_wallets']}")
        """
        key = admin_key or self.admin_key
        if not key:
            raise AuthenticationError("Admin key required for stats")
        
        headers = {"X-Admin-Key": key}
        return self._request("GET", "/api/holders/stats", headers=headers)
    
    # =========================================================================
    # Lottery & Eligibility
    # =========================================================================
    
    def check_eligibility(self, miner_id: str) -> Dict[str, Any]:
        """
        Check lottery/epoch eligibility for a wallet.
        
        Args:
            miner_id: Wallet or miner identifier
        
        Returns:
            Eligibility information dictionary
        
        Example:
            >>> eligible = client.check_eligibility("my-wallet")
            >>> if eligible.get('eligible'):
            ...     print("Wallet is eligible for lottery!")
        """
        return self._request("GET", "/lottery/eligibility", params={"miner_id": miner_id})
    
    # =========================================================================
    # Health & Status
    # =========================================================================
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check node health status.
        
        Returns:
            Health status dictionary
        
        Example:
            >>> health = client.health_check()
            >>> print(f"Node status: {health['status']}")
        """
        return self._request("GET", "/health")
    
    def get_node_info(self) -> Dict[str, Any]:
        """
        Get node information and version.
        
        Returns:
            Node information dictionary
        
        Example:
            >>> info = client.get_node_info()
            >>> print(f"Node version: {info['version']}")
        """
        return self._request("GET", "/info")
