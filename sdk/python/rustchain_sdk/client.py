"""
RustChain API Client
"""

import asyncio
import ssl
import urllib.request
import json
from typing import Optional, Dict, Any, List
from urllib.error import URLError, HTTPError


class RustChainError(Exception):
    """Base exception for RustChain SDK"""
    pass


class AuthenticationError(RustChainError):
    """Authentication related errors"""
    pass


class APIError(RustChainError):
    """API request errors"""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class RustChainClient:
    """
    RustChain Network API Client
    
    Example:
        from rustchain_sdk import RustChainClient
        
        client = RustChainClient("https://50.28.86.131")
        health = client.health()
        miners = client.get_miners()
        balance = client.get_balance("my-wallet")
    """
    
    def __init__(
        self,
        base_url: str = "https://50.28.86.131",
        verify_ssl: bool = False,
        timeout: int = 30,
        retry_count: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Initialize RustChain Client
        
        Args:
            base_url: Base URL of the RustChain node API
            verify_ssl: Enable SSL verification (disabled by default for self-signed cert)
            timeout: Request timeout in seconds
            retry_count: Number of retries on failure
            retry_delay: Delay between retries (seconds)
        """
        self.base_url = base_url.rstrip("/")
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        
        if not verify_ssl:
            self._ctx = ssl.create_default_context()
            self._ctx.check_hostname = False
            self._ctx.verify_mode = ssl.CERT_NONE
        else:
            self._ctx = None
    
    def _request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Make HTTP request with retry logic"""
        import time
        
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(self.retry_count):
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(data).encode('utf-8') if data else None,
                    headers={
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    method=method
                )
                
                with urllib.request.urlopen(
                    req, 
                    context=self._ctx, 
                    timeout=self.timeout
                ) as response:
                    return json.loads(response.read().decode('utf-8'))
                    
            except HTTPError as e:
                if attempt == self.retry_count - 1:
                    raise APIError(f"HTTP Error: {e.reason}", e.code)
            except URLError as e:
                if attempt == self.retry_count - 1:
                    raise APIError(f"Connection Error: {e.reason}")
            except Exception as e:
                if attempt == self.retry_count - 1:
                    raise APIError(f"Request failed: {str(e)}")
            
            if attempt < self.retry_count - 1:
                time.sleep(self.retry_delay * (attempt + 1))
        
        raise APIError("Max retries exceeded")
    
    def _get(self, endpoint: str) -> Dict:
        """GET request"""
        return self._request("GET", endpoint)
    
    def _post(self, endpoint: str, data: Dict) -> Dict:
        """POST request"""
        return self._request("POST", endpoint, data)
    
    # ========== API Methods ==========
    
    def health(self) -> Dict[str, Any]:
        """
        Get node health status
        
        Returns:
            Dict with keys: ok, version, uptime_s, db_rw, etc.
        
        Example:
            >>> client.health()
            {'ok': True, 'version': '2.2.1-rip200', 'uptime_s': 140828, ...}
        """
        return self._get("/health")
    
    def get_miners(self) -> List[Dict[str, Any]]:
        """
        Get list of active miners
        
        Returns:
            List of miner dictionaries with keys: miner, antiquity_multiplier, 
            device_arch, device_family, hardware_type, last_attest, etc.
        
        Example:
            >>> client.get_miners()
            [{'miner': 'windows-gaming-121', 'antiquity_multiplier': 1.0, ...}, ...]
        """
        return self._get("/api/miners")
    
    def get_balance(self, miner_id: str) -> Dict[str, Any]:
        """
        Get wallet balance for a miner
        
        Args:
            miner_id: Miner wallet ID (e.g., "my-wallet" or "RTC...")
        
        Returns:
            Dict with balance information
        
        Example:
            >>> client.get_balance("my-wallet")
            {'balance': 100.5, 'miner_id': 'my-wallet', ...}
        """
        return self._get(f"/wallet/balance?miner_id={miner_id}")
    
    def get_epoch(self) -> Dict[str, Any]:
        """
        Get current epoch information
        
        Returns:
            Dict with keys: epoch, blocks_per_epoch, epoch_pot, slot, etc.
        
        Example:
            >>> client.get_epoch()
            {'epoch': 92, 'blocks_per_epoch': 144, 'epoch_pot': 1.5, ...}
        """
        return self._get("/epoch")
    
    def check_eligibility(self, miner_id: str) -> Dict[str, Any]:
        """
        Check lottery eligibility for a miner
        
        Args:
            miner_id: Miner wallet ID
        
        Returns:
            Dict with keys: eligible, slot, slot_producer, rotation_size, etc.
        
        Example:
            >>> client.check_eligibility("my-wallet")
            {'eligible': True, 'slot': 13365, 'slot_producer': '...', ...}
        """
        return self._get(f"/lottery/eligibility?miner_id={miner_id}")
    
    def submit_attestation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit attestation to the network
        
        Args:
            payload: Attestation payload dictionary
        
        Returns:
            Dict with submission result
        
        Example:
            >>> payload = {"miner_id": "my-wallet", "signature": "..."}
            >>> client.submit_attestation(payload)
            {'success': True, 'tx_hash': '...'}
        """
        return self._post("/attest/submit", payload)
    
    def transfer(
        self, 
        from_wallet: str, 
        to_wallet: str, 
        amount: float,
        private_key: str
    ) -> Dict[str, Any]:
        """
        Transfer RTC between wallets
        
        Args:
            from_wallet: Source wallet ID
            to_wallet: Destination wallet ID
            amount: Amount of RTC to transfer
            private_key: Private key for signing
        
        Returns:
            Dict with transfer result
        
        Example:
            >>> client.transfer("wallet-a", "wallet-b", 10.0, "private-key")
            {'success': True, 'tx_hash': '...'}
        """
        payload = {
            "from": from_wallet,
            "to": to_wallet,
            "amount": amount,
            "private_key": private_key
        }
        return self._post("/wallet/transfer/signed", payload)
    
    # ========== Async Methods ==========
    
    async def async_health(self) -> Dict[str, Any]:
        """Async version of health()"""
        return await self._async_request("GET", "/health")
    
    async def async_get_miners(self) -> List[Dict[str, Any]]:
        """Async version of get_miners()"""
        return await self._async_request("GET", "/api/miners")
    
    async def async_get_balance(self, miner_id: str) -> Dict[str, Any]:
        """Async version of get_balance()"""
        return await self._async_request("GET", f"/wallet/balance?miner_id={miner_id}")
    
    async def async_get_epoch(self) -> Dict[str, Any]:
        """Async version of get_epoch()"""
        return await self._async_request("GET", "/epoch")
    
    async def async_check_eligibility(self, miner_id: str) -> Dict[str, Any]:
        """Async version of check_eligibility()"""
        return await self._async_request("GET", f"/lottery/eligibility?miner_id={miner_id}")
    
    async def async_submit_attestation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Async version of submit_attestation()"""
        return await self._async_request("POST", "/attest/submit", payload)
    
    async def _async_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None
    ) -> Dict:
        """Async HTTP request"""
        import aiohttp
        
        url = f"{self.base_url}{endpoint}"
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        
        ssl_context = self._ctx if not self.verify_ssl else None
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(
                method, 
                url, 
                json=data,
                ssl=ssl_context if ssl_context else None
            ) as response:
                return await response.json()


# Convenience function for quick usage
def create_client(
    base_url: str = "https://50.28.86.131",
    **kwargs
) -> RustChainClient:
    """
    Create a RustChain client with default settings
    
    Example:
        >>> client = create_client()
        >>> health = client.health()
    """
    return RustChainClient(base_url=base_url, **kwargs)
