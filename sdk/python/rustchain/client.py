"""
RustChain API Client
A pip-installable Python SDK for the RustChain blockchain network.
"""

import asyncio
import ssl
import json as _json
import urllib.request
from typing import Any, Dict, List, Optional

from .explorer import ExplorerClient, ExplorerError
from .exceptions import RustChainError, AuthenticationError, APIError


class RustChainClient:
    """
    RustChain Network API Client
    
    Example:
        >>> from rustchain import RustChainClient
        >>> 
        >>> client = RustChainClient("https://50.28.86.131")
        >>> health = client.health()
        >>> miners = client.miners()
        >>> balance = client.balance("my-wallet")
    
    Async example:
        >>> client = RustChainClient()
        >>> health = await client.async_health()
    """
    
    def __init__(
        self,
        base_url: str = "https://50.28.86.131",
        verify_ssl: bool = False,
        timeout: int = 30,
        retry_count: int = 3,
        retry_delay: float = 1.0
    ):
        self.base_url = base_url.rstrip("/")
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        
        # Explorer subclient
        self._explorer = ExplorerClient(
            base_url=base_url,
            verify_ssl=verify_ssl,
            timeout=timeout
        )
        
        if not verify_ssl:
            self._ctx = ssl.create_default_context()
            self._ctx.check_hostname = False
            self._ctx.verify_mode = ssl.CERT_NONE
        else:
            self._ctx = None
    
    @property
    def explorer(self) -> ExplorerClient:
        """Access the explorer subclient for block/transaction data"""
        return self._explorer
    
    def _request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None,
        retry_count: Optional[int] = None
    ) -> Any:
        """Make HTTP request with retry logic"""
        import time
        
        url = f"{self.base_url}{endpoint}"
        retries = retry_count if retry_count is not None else self.retry_count
        
        for attempt in range(retries):
            try:
                req = urllib.request.Request(
                    url,
                    data=_json.dumps(data).encode("utf-8") if data else None,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    },
                    method=method
                )
                
                with urllib.request.urlopen(
                    req, 
                    context=self._ctx, 
                    timeout=self.timeout
                ) as response:
                    return _json.loads(response.read().decode("utf-8"))
                    
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    raise AuthenticationError(f"Authentication failed: {e.reason}")
                if attempt == retries - 1:
                    raise APIError(f"HTTP Error: {e.reason}", e.code)
            except urllib.error.URLError as e:
                if attempt == retries - 1:
                    raise APIError(f"Connection Error: {e.reason}")
            except Exception as e:
                if attempt == retries - 1:
                    raise APIError(f"Request failed: {str(e)}")
            
            if attempt < retries - 1:
                time.sleep(self.retry_delay * (attempt + 1))
        
        raise APIError("Max retries exceeded")
    
    def _get(self, endpoint: str) -> Any:
        """GET request"""
        return self._request("GET", endpoint)
    
    def _post(self, endpoint: str, data: Dict) -> Any:
        """POST request"""
        return self._request("POST", endpoint, data)
    
    # ========== Primary API Methods (bounty spec names) ==========
    
    def health(self) -> Dict[str, Any]:
        """
        Get node health status.
        
        Returns:
            Dict with keys: ok, version, uptime_s, db_rw, backup_age_hours, tip_age_slots.
        
        Example:
            >>> client.health()
            {'ok': True, 'version': '2.2.1-rip200', 'uptime_s': 140828, ...}
        """
        return self._get("/health")
    
    def epoch(self) -> Dict[str, Any]:
        """
        Get current epoch information. Alias for get_epoch().
        
        Returns:
            Dict with keys: epoch, blocks_per_epoch, epoch_pot, slot, 
            enrolled_miners, total_supply_rtc.
        
        Example:
            >>> client.epoch()
            {'epoch': 112, 'blocks_per_epoch': 144, 'epoch_pot': 1.5, ...}
        """
        return self._get("/epoch")
    
    def miners(self) -> List[Dict[str, Any]]:
        """
        Get list of active miners. Alias for get_miners().
        
        Returns:
            List of miner dictionaries with keys: miner, antiquity_multiplier, 
            device_arch, device_family, hardware_type, last_attest, etc.
        
        Example:
            >>> client.miners()
            [{'miner': 'nox-ventures', 'antiquity_multiplier': 1.0, ...}, ...]
        """
        return self._get("/api/miners")
    
    def balance(self, wallet_id: str) -> Dict[str, Any]:
        """
        Get wallet balance for a miner. Alias for get_balance().
        
        Args:
            wallet_id: Miner wallet ID (e.g., "nox-ventures" or "RTC...")
        
        Returns:
            Dict with balance information.
        
        Example:
            >>> client.balance("nox-ventures")
            {'balance': 100.5, 'miner_id': 'nox-ventures', ...}
        """
        return self._get(f"/balance/{urllib.parse.quote(wallet_id)}")
    
    def transfer(
        self, 
        from_wallet: str, 
        to_wallet: str, 
        amount: float,
        signature: str
    ) -> Dict[str, Any]:
        """
        Transfer RTC between wallets (Ed25519 signed).
        
        Args:
            from_wallet: Source wallet ID
            to_wallet: Destination wallet ID
            amount: Amount of RTC to transfer
            signature: Ed25519 signature of the transfer payload
        
        Returns:
            Dict with transfer result including tx_hash.
        
        Example:
            >>> client.transfer("wallet-a", "wallet-b", 10.0, "signature-hex...")
            {'success': True, 'tx_hash': '...'}
        """
        payload = {
            "from": from_wallet,
            "to": to_wallet,
            "amount": amount,
            "signature": signature
        }
        return self._post("/wallet/transfer/signed", payload)
    
    def attestation_status(self, miner_id: str) -> Dict[str, Any]:
        """
        Get attestation status for a miner via beacon envelopes.
        
        Args:
            miner_id: Miner wallet ID
        
        Returns:
            Dict with attestation history from beacon envelopes.
        
        Example:
            >>> client.attestation_status("nox-ventures")
            {'envelopes': [...], 'count': 50}
        """
        envelopes_data = self.explorer.beacon_envelopes(limit=50)
        
        # Filter envelopes for the specific miner
        miner_envelopes = [
            e for e in envelopes_data.get("envelopes", [])
            if miner_id.lower() in e.get("agent_id", "").lower() 
            or miner_id.lower() in e.get("nonce", "").lower()
        ]
        
        return {
            "miner_id": miner_id,
            "attestations": miner_envelopes,
            "count": len(miner_envelopes)
        }
    
    # ========== Additional API Methods ==========
    
    def get_miners(self) -> List[Dict[str, Any]]:
        """Get list of active miners. Use miners() for bounty spec API."""
        return self._get("/api/miners")
    
    def get_epoch(self) -> Dict[str, Any]:
        """Get current epoch info. Use epoch() for bounty spec API."""
        return self._get("/epoch")
    
    def get_balance(self, miner_id: str) -> Dict[str, Any]:
        """Get wallet balance. Use balance() for bounty spec API."""
        # Try wallet/balance first (requires miner_id param)
        try:
            return self._get(f"/wallet/balance?miner_id={miner_id}")
        except APIError:
            # Fallback to balance/{minerPk}
            return self._get(f"/balance/{miner_id}")
    
    def check_eligibility(self, miner_id: str) -> Dict[str, Any]:
        """
        Check lottery eligibility for a miner (RIP-0200).
        
        Args:
            miner_id: Miner wallet ID
        
        Returns:
            Dict with keys: eligible, slot, slot_producer, rotation_size, reason.
        """
        return self._get(f"/lottery/eligibility?miner_id={miner_id}")
    
    def submit_attestation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit attestation to the network.
        
        Args:
            payload: Attestation payload (miner_id, signature, etc.)
        
        Returns:
            Dict with submission result.
        """
        return self._post("/attest/submit", payload)
    
    def get_attestation_challenge(self, miner_id: str) -> Dict[str, Any]:
        """
        Get an attestation challenge for a miner.
        
        Args:
            miner_id: Miner wallet ID
        
        Returns:
            Dict with challenge details.
        """
        return self._post("/attest/challenge", {"miner_id": miner_id})
    
    def wallet_history(self, wallet_id: str, limit: int = 50) -> Dict[str, Any]:
        """
        Get transaction history for a wallet.
        
        Args:
            wallet_id: Wallet ID
            limit: Maximum number of history entries
        
        Returns:
            Dict with transaction history.
        """
        return self._get(f"/wallet/history?miner_id={wallet_id}&limit={limit}")
    
    def get_chain_tip(self) -> Dict[str, Any]:
        """
        Get the current chain tip header.
        
        Returns:
            Dict with miner, slot, signature_prefix, tip_age.
        """
        return self._get("/headers/tip")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get system statistics."""
        return self._get("/api/stats")
    
    def get_node_info(self) -> Dict[str, Any]:
        """Get detailed node information."""
        return self._get("/api/nodes")
    
    def get_p2p_stats(self) -> Dict[str, Any]:
        """Get P2P network statistics."""
        return self._get("/p2p/stats")
    
    # ========== Async Methods ==========
    
    async def async_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None
    ) -> Any:
        """Async HTTP request using aiohttp"""
        try:
            import aiohttp
        except ImportError:
            raise RustChainError(
                "aiohttp is required for async methods. "
                "Install with: pip install rustchain-sdk[async]"
            )
        
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
    
    async def async_health(self) -> Dict[str, Any]:
        """Async version of health()"""
        return await self.async_request("GET", "/health")
    
    async def async_epoch(self) -> Dict[str, Any]:
        """Async version of epoch()"""
        return await self.async_request("GET", "/epoch")
    
    async def async_miners(self) -> List[Dict[str, Any]]:
        """Async version of miners()"""
        return await self.async_request("GET", "/api/miners")
    
    async def async_balance(self, wallet_id: str) -> Dict[str, Any]:
        """Async version of balance()"""
        return await self.async_request("GET", f"/balance/{wallet_id}")
    
    async def async_get_epoch(self) -> Dict[str, Any]:
        """Async version of get_epoch()"""
        return await self.async_request("GET", "/epoch")
    
    async def async_get_miners(self) -> List[Dict[str, Any]]:
        """Async version of get_miners()"""
        return await self.async_request("GET", "/api/miners")
    
    async def async_get_balance(self, miner_id: str) -> Dict[str, Any]:
        """Async version of get_balance()"""
        return await self.async_request("GET", f"/wallet/balance?miner_id={miner_id}")
    
    async def async_check_eligibility(self, miner_id: str) -> Dict[str, Any]:
        """Async version of check_eligibility()"""
        return await self.async_request("GET", f"/lottery/eligibility?miner_id={miner_id}")


# ========== urllib import for quote ==========
import urllib.parse


def create_client(base_url: str = "https://50.28.86.131", **kwargs) -> RustChainClient:
    """
    Create a RustChain client with default settings.
    
    Example:
        >>> client = create_client()
        >>> health = client.health()
    """
    return RustChainClient(base_url=base_url, **kwargs)
