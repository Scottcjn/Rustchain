"""
RustChain Python SDK - API Client

A clean, pip-installable Python SDK for the RustChain Proof-of-Antiquity blockchain.
"""

import time
import logging
from typing import Optional, Dict, List, Any, Union
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class Miner:
    """Represents a RustChain miner."""
    miner_id: str
    device_family: str
    device_arch: str
    hardware_type: str
    antiquity_multiplier: float
    entropy_score: float
    last_attest: int


@dataclass
class EpochInfo:
    """Current epoch information."""
    epoch: int
    slot: int
    blocks_per_epoch: int
    epoch_pot: float
    enrolled_miners: int


@dataclass
class Balance:
    """Wallet balance information."""
    miner_id: str
    amount_rtc: float
    amount_i64: int


@dataclass
class TransferResult:
    """Result of a signed transfer."""
    success: bool
    tx_hash: Optional[str] = None
    new_balance: Optional[int] = None
    error: Optional[str] = None


class RustChainError(Exception):
    """Base exception for RustChain SDK errors."""
    pass


class ConnectionError(RustChainError):
    """Failed to connect to node."""
    pass


class APIError(RustChainError):
    """API returned an error."""
    pass


class RustChainClient:
    """
    RustChain API Client.
    
    Args:
        base_url: Node URL (default: https://50.28.86.131)
        verify_ssl: Verify SSL certificates (default: True)
        ca_bundle_path: Optional path to a CA bundle (useful for self-signed node certs)
        timeout: Request timeout in seconds (default: 30)
        max_retries: Maximum retry attempts (default: 3)
        retry_delay: Initial retry delay in seconds (default: 1)
    
    Example:
        >>> from rustchain_sdk import RustChainClient
        >>> client = RustChainClient()
        >>> miners = client.get_miners()
        >>> balance = client.get_balance("my-wallet")
    """
    
    DEFAULT_NODE = "https://50.28.86.131"
    
    def __init__(
        self,
        base_url: str = DEFAULT_NODE,
        verify_ssl: bool = True,
        ca_bundle_path: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        self.base_url = base_url.rstrip('/')
        self.verify_ssl = verify_ssl
        self.ca_bundle_path = ca_bundle_path
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # httpx `verify` accepts either a bool or a path to a CA bundle.
        # Use a CA bundle path when provided (useful for self-signed deployments).
        verify: Union[bool, str] = ca_bundle_path if ca_bundle_path else verify_ssl
        
        self._client = httpx.Client(
            base_url=self.base_url,
            verify=verify,
            timeout=timeout,
        )
    
    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic."""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                response = self._client.request(
                    method=method,
                    url=endpoint,
                    params=params,
                    json=json,
                )
                response.raise_for_status()
                return response.json()
                
            except httpx.ConnectError as e:
                last_error = ConnectionError(f"Failed to connect to {self.base_url}: {e}")
                logger.warning(f"Connection failed (attempt {attempt + 1}/{self.max_retries}): {e}")
                
            except httpx.HTTPStatusError as e:
                last_error = APIError(f"API error {e.response.status_code}: {e.response.text}")
                if e.response.status_code < 500:
                    raise last_error  # Don't retry client errors
                logger.warning(f"Server error (attempt {attempt + 1}/{self.max_retries}): {e}")
                
            except Exception as e:
                last_error = RustChainError(f"Request failed: {e}")
                logger.warning(f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}")
            
            # Exponential backoff
            if attempt < self.max_retries - 1:
                delay = self.retry_delay * (2 ** attempt)
                time.sleep(delay)
        
        raise last_error
    
    def health(self) -> Dict[str, Any]:
        """
        Check node health status.
        
        Returns:
            Dict with health info: ok, version, uptime_s, db_rw, backup_age_hours, tip_age_slots
        
        Example:
            >>> client.health()
            {'ok': True, 'version': '2.2.1-rip200', 'uptime_s': 18728, ...}
        """
        return self._request("GET", "/health")
    
    def get_epoch(self) -> EpochInfo:
        """
        Get current epoch information.
        
        Returns:
            EpochInfo with epoch, slot, blocks_per_epoch, epoch_pot, enrolled_miners
        
        Example:
            >>> epoch = client.get_epoch()
            >>> print(f"Current epoch: {epoch.epoch}, pot: {epoch.epoch_pot} RTC")
        """
        data = self._request("GET", "/epoch")
        return EpochInfo(
            epoch=data["epoch"],
            slot=data["slot"],
            blocks_per_epoch=data["blocks_per_epoch"],
            epoch_pot=data["epoch_pot"],
            enrolled_miners=data["enrolled_miners"],
        )
    
    def get_miners(self) -> List[Miner]:
        """
        Get all active/enrolled miners.
        
        Returns:
            List of Miner objects with hardware details and multipliers
        
        Example:
            >>> miners = client.get_miners()
            >>> for m in miners:
            ...     print(f"{m.miner_id}: {m.hardware_type} ({m.antiquity_multiplier}x)")
        """
        data = self._request("GET", "/api/miners")
        return [
            Miner(
                miner_id=m.get("miner", m.get("miner_id", "")),
                device_family=m.get("device_family", ""),
                device_arch=m.get("device_arch", ""),
                hardware_type=m.get("hardware_type", ""),
                antiquity_multiplier=m.get("antiquity_multiplier", 1.0),
                entropy_score=m.get("entropy_score", 0.0),
                last_attest=m.get("last_attest", 0),
            )
            for m in data
        ]
    
    def get_balance(self, miner_id: str) -> Balance:
        """
        Get RTC balance for a wallet.
        
        Args:
            miner_id: Wallet/miner identifier
        
        Returns:
            Balance with miner_id, amount_rtc, amount_i64
        
        Example:
            >>> bal = client.get_balance("my-wallet")
            >>> print(f"Balance: {bal.amount_rtc} RTC")
        """
        data = self._request("GET", "/wallet/balance", params={"miner_id": miner_id})
        return Balance(
            miner_id=data.get("miner_id", miner_id),
            amount_rtc=data.get("amount_rtc", 0.0),
            amount_i64=data.get("amount_i64", 0),
        )
    
    def check_eligibility(self, miner_id: str) -> Dict[str, Any]:
        """
        Check lottery eligibility for a miner.
        
        Args:
            miner_id: Wallet/miner identifier
        
        Returns:
            Dict with eligibility status
        """
        return self._request("GET", "/lottery/eligibility", params={"miner_id": miner_id})
    
    def submit_attestation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit hardware attestation for epoch enrollment.
        
        Args:
            payload: Attestation data with fingerprint and signature
        
        Returns:
            Dict with enrollment result: success, enrolled, epoch, multiplier
        
        Example:
            >>> result = client.submit_attestation({
            ...     "miner_id": "my-wallet",
            ...     "fingerprint": {...},
            ...     "signature": "base64..."
            ... })
        """
        return self._request("POST", "/attest/submit", json=payload)
    
    def transfer(
        self,
        from_wallet: str,
        to_wallet: str,
        amount_rtc: float,
        signature: str,
        nonce: int,
    ) -> TransferResult:
        """
        Execute a signed RTC transfer.
        
        Args:
            from_wallet: Sender miner_id
            to_wallet: Recipient miner_id
            amount_rtc: Amount in RTC (will be converted to i64)
            signature: Base64-encoded Ed25519 signature
            nonce: Transaction nonce
        
        Returns:
            TransferResult with success, tx_hash, new_balance, error
        
        Note:
            The signature must be over the message: "{from}:{to}:{amount_i64}:{nonce}"
        
        Example:
            >>> result = client.transfer(
            ...     from_wallet="sender-id",
            ...     to_wallet="recipient-id", 
            ...     amount_rtc=1.5,
            ...     signature="base64...",
            ...     nonce=1
            ... )
        """
        amount_i64 = int(amount_rtc * 1_000_000)
        
        data = self._request(
            "POST",
            "/wallet/transfer/signed",
            json={
                "from": from_wallet,
                "to": to_wallet,
                "amount_i64": amount_i64,
                "nonce": nonce,
                "signature": signature,
            }
        )
        
        return TransferResult(
            success=data.get("success", False),
            tx_hash=data.get("tx_hash"),
            new_balance=data.get("new_balance"),
            error=data.get("error"),
        )
    
    def close(self):
        """Close the HTTP client."""
        self._client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()


class AsyncRustChainClient:
    """
    Async RustChain API Client.
    
    Same interface as RustChainClient but with async methods.
    
    Example:
        >>> async with AsyncRustChainClient() as client:
        ...     miners = await client.get_miners()
    """
    
    DEFAULT_NODE = "https://50.28.86.131"
    
    def __init__(
        self,
        base_url: str = DEFAULT_NODE,
        verify_ssl: bool = True,
        ca_bundle_path: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        self.base_url = base_url.rstrip('/')
        self.verify_ssl = verify_ssl
        self.ca_bundle_path = ca_bundle_path
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        verify: Union[bool, str] = ca_bundle_path if ca_bundle_path else verify_ssl
        
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            verify=verify,
            timeout=timeout,
        )
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make async HTTP request with retry logic."""
        import asyncio
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                response = await self._client.request(
                    method=method,
                    url=endpoint,
                    params=params,
                    json=json,
                )
                response.raise_for_status()
                return response.json()
                
            except httpx.ConnectError as e:
                last_error = ConnectionError(f"Failed to connect to {self.base_url}: {e}")
                
            except httpx.HTTPStatusError as e:
                last_error = APIError(f"API error {e.response.status_code}: {e.response.text}")
                if e.response.status_code < 500:
                    raise last_error
                
            except Exception as e:
                last_error = RustChainError(f"Request failed: {e}")
            
            if attempt < self.max_retries - 1:
                delay = self.retry_delay * (2 ** attempt)
                await asyncio.sleep(delay)
        
        raise last_error
    
    async def health(self) -> Dict[str, Any]:
        """Check node health status."""
        return await self._request("GET", "/health")
    
    async def get_epoch(self) -> EpochInfo:
        """Get current epoch information."""
        data = await self._request("GET", "/epoch")
        return EpochInfo(
            epoch=data["epoch"],
            slot=data["slot"],
            blocks_per_epoch=data["blocks_per_epoch"],
            epoch_pot=data["epoch_pot"],
            enrolled_miners=data["enrolled_miners"],
        )
    
    async def get_miners(self) -> List[Miner]:
        """Get all active/enrolled miners."""
        data = await self._request("GET", "/api/miners")
        return [
            Miner(
                miner_id=m.get("miner", m.get("miner_id", "")),
                device_family=m.get("device_family", ""),
                device_arch=m.get("device_arch", ""),
                hardware_type=m.get("hardware_type", ""),
                antiquity_multiplier=m.get("antiquity_multiplier", 1.0),
                entropy_score=m.get("entropy_score", 0.0),
                last_attest=m.get("last_attest", 0),
            )
            for m in data
        ]
    
    async def get_balance(self, miner_id: str) -> Balance:
        """Get RTC balance for a wallet."""
        data = await self._request("GET", "/wallet/balance", params={"miner_id": miner_id})
        return Balance(
            miner_id=data.get("miner_id", miner_id),
            amount_rtc=data.get("amount_rtc", 0.0),
            amount_i64=data.get("amount_i64", 0),
        )
    
    async def check_eligibility(self, miner_id: str) -> Dict[str, Any]:
        """Check lottery eligibility for a miner."""
        return await self._request("GET", "/lottery/eligibility", params={"miner_id": miner_id})
    
    async def submit_attestation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Submit hardware attestation for epoch enrollment."""
        return await self._request("POST", "/attest/submit", json=payload)
    
    async def transfer(
        self,
        from_wallet: str,
        to_wallet: str,
        amount_rtc: float,
        signature: str,
        nonce: int,
    ) -> TransferResult:
        """Execute a signed RTC transfer."""
        amount_i64 = int(amount_rtc * 1_000_000)
        
        data = await self._request(
            "POST",
            "/wallet/transfer/signed",
            json={
                "from": from_wallet,
                "to": to_wallet,
                "amount_i64": amount_i64,
                "nonce": nonce,
                "signature": signature,
            }
        )
        
        return TransferResult(
            success=data.get("success", False),
            tx_hash=data.get("tx_hash"),
            new_balance=data.get("new_balance"),
            error=data.get("error"),
        )
    
    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        await self.close()
