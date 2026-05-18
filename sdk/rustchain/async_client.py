"""
RustChain Async Client

Async client for interacting with RustChain node API using aiohttp.
"""

import asyncio
from typing import Dict, List, Optional, Any
import aiohttp
import json
from rustchain.exceptions import (
    RustChainError,
    ConnectionError,
    ValidationError,
    APIError,
    AttestationError,
    TransferError,
)


class AsyncRustChainClient:
    """
    Async client for interacting with RustChain node API.

    Args:
        base_url: Base URL of RustChain node (e.g., "https://rustchain.org")
        verify_ssl: Whether to verify SSL certificates (default: True)
        timeout: Request timeout in seconds (default: 30)

    Example:
        >>> import asyncio
        >>> from rustchain.async_client import AsyncRustChainClient
        >>>
        >>> async def main():
        ...     async with AsyncRustChainClient("https://rustchain.org") as client:
        ...         health = await client.health()
        ...         print(f"Node version: {health['version']}")
        >>>
        >>> asyncio.run(main())
    """

    def __init__(
        self,
        base_url: str,
        verify_ssl: bool = True,
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            ssl_context = True if self.verify_ssl else False
            self._session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=ssl_context)
            )
        return self._session

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Dict = None,
        data: Dict = None,
        json_payload: Dict = None,
    ) -> Dict:
        """
        Make async HTTP request to RustChain node.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: URL query parameters
            data: Form data
            json_payload: JSON payload

        Returns:
            Response JSON as dict

        Raises:
            ConnectionError: If request fails
            APIError: If API returns error
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = {"Content-Type": "application/json"}

        try:
            session = await self._get_session()
            async with session.request(
                method=method,
                url=url,
                params=params,
                data=data,
                json=json_payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            ) as response:
                # Check for HTTP errors
                if response.status >= 400:
                    raise APIError(
                        f"HTTP {response.status}: {response.reason}",
                        status_code=response.status,
                    )

                # Parse JSON response
                try:
                    return await response.json()
                except (json.JSONDecodeError, aiohttp.ContentTypeError):
                    text = await response.text()
                    return {"raw_response": text}

        except aiohttp.ClientConnectionError as e:
            raise ConnectionError(f"Failed to connect to {url}: {e}") from e
        except asyncio.TimeoutError as e:
            raise ConnectionError(f"Request timeout to {url}: {e}") from e
        except aiohttp.ClientError as e:
            raise ConnectionError(f"Request failed: {e}") from e

    async def health(self) -> Dict[str, Any]:
        """
        Get node health status.

        Returns:
            Dict with health information:
                - ok (bool): Node is healthy
                - uptime_s (int): Uptime in seconds
                - version (str): Node version
                - db_rw (bool): Database read/write status
        """
        return await self._request("GET", "/health")

    async def epoch(self) -> Dict[str, Any]:
        """
        Get current epoch information.

        Returns:
            Dict with epoch information:
                - epoch (int): Current epoch number
                - slot (int): Current slot
                - blocks_per_epoch (int): Blocks per epoch
                - enrolled_miners (int): Number of enrolled miners
                - epoch_pot (float): Current epoch PoT
        """
        return await self._request("GET", "/epoch")

    async def miners(self) -> List[Dict[str, Any]]:
        """
        Get list of all miners.

        Returns:
            List of miner dicts with:
                - miner (str): Miner wallet address
                - antiquity_multiplier (float): Hardware antiquity multiplier
                - hardware_type (str): Hardware type description
                - device_arch (str): Device architecture
                - last_attest (int): Last attestation timestamp
        """
        result = await self._request("GET", "/api/miners")
        return result if isinstance(result, list) else []

    async def balance(self, miner_id: str) -> Dict[str, Any]:
        """
        Get wallet balance for a miner.

        Args:
            miner_id: Miner wallet address

        Returns:
            Dict with balance information:
                - miner_pk (str): Wallet address
                - balance (float): Current balance in RTC
                - epoch_rewards (float): Rewards in current epoch
                - total_earned (float): Total RTC earned

        Raises:
            ValidationError: If miner_id is invalid
        """
        if not miner_id or not isinstance(miner_id, str):
            raise ValidationError("miner_id must be a non-empty string")

        return await self._request("GET", "/wallet/balance", params={"miner_id": miner_id})

    async def transfer(
        self,
        from_addr: str,
        to_addr: str,
        amount: float,
        signature: str = None,
        fee: float = 0.01,
    ) -> Dict[str, Any]:
        """
        Transfer RTC from one wallet to another.

        Args:
            from_addr: Source wallet address
            to_addr: Destination wallet address
            amount: Amount to transfer (in RTC)
            signature: Transaction signature (if signed offline)
            fee: Transfer fee (default: 0.01 RTC)

        Returns:
            Dict with transfer result:
                - success (bool): Transfer succeeded
                - tx_id (str): Transaction ID
                - fee (float): Fee deducted
                - new_balance (float): New balance after transfer

        Raises:
            ValidationError: If parameters are invalid
            TransferError: If transfer fails
        """
        # Validate parameters
        if not from_addr or not isinstance(from_addr, str):
            raise ValidationError("from_addr must be a non-empty string")
        if not to_addr or not isinstance(to_addr, str):
            raise ValidationError("to_addr must be a non-empty string")
        if amount <= 0:
            raise ValidationError("amount must be positive")

        payload = {
            "from": from_addr,
            "to": to_addr,
            "amount": amount,
            "fee": fee,
        }

        if signature:
            payload["signature"] = signature

        try:
            result = await self._request("POST", "/wallet/transfer/signed", json_payload=payload)

            if not result.get("success", False):
                error_msg = result.get("error", "Transfer failed")
                raise TransferError(f"Transfer failed: {error_msg}")

            return result

        except APIError as e:
            raise TransferError(f"Transfer failed: {e}") from e

    async def transfer_history(self, miner_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get transfer history for a wallet.

        Args:
            miner_id: Wallet address
            limit: Maximum number of records to return (default: 50)

        Returns:
            List of transfer dicts with:
                - tx_id (str): Transaction ID
                - from_addr (str): Source address
                - to_addr (str): Destination address
                - amount (float): Amount transferred
                - timestamp (int): Unix timestamp
                - status (str): Transaction status
        """
        if not miner_id or not isinstance(miner_id, str):
            raise ValidationError("miner_id must be a non-empty string")

        result = await self._request(
            "GET",
            "/wallet/history",
            params={"miner_id": miner_id, "limit": limit},
        )
        return result if isinstance(result, list) else []

    async def submit_attestation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit hardware attestation to the node.

        Args:
            payload: Attestation payload containing:
                - miner_id (str): Miner wallet address
                - device (dict): Device information
                - fingerprint (dict): Fingerprint check results
                - nonce (str): Unique nonce for replay protection

        Returns:
            Dict with attestation result:
                - success (bool): Attestation accepted
                - epoch (int): Epoch number
                - slot (int): Slot number
                - multiplier (float): Applied antiquity multiplier

        Raises:
            ValidationError: If payload is invalid
            AttestationError: If attestation fails
        """
        if not payload or not isinstance(payload, dict):
            raise ValidationError("payload must be a non-empty dict")

        # Validate required fields
        required_fields = ["miner_id", "device", "fingerprint"]
        for field in required_fields:
            if field not in payload:
                raise ValidationError(f"Missing required field: {field}")

        try:
            result = await self._request("POST", "/attest/submit", json_payload=payload)

            if not result.get("success", False):
                error_msg = result.get("error", "Attestation failed")
                raise AttestationError(f"Attestation failed: {error_msg}")

            return result

        except APIError as e:
            raise AttestationError(f"Attestation failed: {e}") from e

    async def enroll_miner(self, miner_id: str) -> Dict[str, Any]:
        """
        Enroll a new miner in the network.

        Args:
            miner_id: Wallet address to enroll

        Returns:
            Dict with enrollment result:
                - success (bool): Enrollment succeeded
                - miner_id (str): Enrolled wallet address
                - enrolled_at (int): Unix timestamp
        """
        if not miner_id or not isinstance(miner_id, str):
            raise ValidationError("miner_id must be a non-empty string")

        try:
            result = await self._request("POST", "/enroll", json_payload={"miner_id": miner_id})
            return result

        except APIError as e:
            raise RustChainError(f"Enrollment failed: {e}") from e

    async def close(self):
        """Close the HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
