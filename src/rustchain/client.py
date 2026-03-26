"""
RustChain Python SDK
Async-first API client for the RustChain Proof-of-Antiquity blockchain network.

Usage:
    # Sync
    from rustchain import RustChainClient
    client = RustChainClient()
    print(client.health())

    # Async
    from rustchain import AsyncRustChainClient
    async def main():
        client = AsyncRustChainClient()
        health = await client.health()
"""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import aiohttp

from .exceptions import APIError, ConnectionError, SigningError, TimeoutError, ValidationError
from .explorer import Explorer
from .crypto import SigningKey

if TYPE_CHECKING:
    from .crypto import SigningKey


# ─────────────────────────────────────────────────────────────────────────────
# Exceptions (re-export for convenience)
# ─────────────────────────────────────────────────────────────────────────────
__all__ = [
    "RustChainError",
    "APIError",
    "ConnectionError",
    "TimeoutError",
    "ValidationError",
    "WalletError",
    "SigningError",
    "AttestationError",
]


# ─────────────────────────────────────────────────────────────────────────────
# Sync Client
# ─────────────────────────────────────────────────────────────────────────────


class RustChainClient:
    """
    Synchronous RustChain API client.

    Attributes:
        explorer: Explorer accessor for block/transaction data.
            e.g. ``client.explorer.blocks()``, ``client.explorer.transactions()``

    Example:
        >>> client = RustChainClient()
        >>> health = client.health()
        >>> print(health["version"])
        2.2.1-rip200

        >>> balance = client.balance("my-wallet")
        >>> print(balance["amount_rtc"])
        42.0

        >>> status = client.attestation_status("my-miner")
        >>> print(status["verified"])
        True
    """

    DEFAULT_BASE_URL = "https://50.28.86.131"

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        timeout: int = 30,
        verify_ssl: bool = False,
        retry_count: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.retry_count = retry_count
        self.retry_delay = retry_delay

        self._ctx: Optional[ssl.SSLContext] = None
        if not verify_ssl:
            self._ctx = ssl.create_default_context()
            self._ctx.check_hostname = False
            self._ctx.verify_mode = ssl.CERT_NONE

        self.explorer = Explorer(
            base_url=self.base_url,
            timeout=self.timeout,
            verify_ssl=self.verify_ssl,
        )

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _urlopen(self, method: str, path: str, data: Optional[bytes] = None) -> Dict[str, Any]:
        """Make an HTTP request with retry logic."""
        import urllib.error

        url = f"{self.base_url}{path}"
        for attempt in range(self.retry_count):
            try:
                req = urllib.request.Request(
                    url,
                    data=data,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    method=method,
                )
                with urllib.request.urlopen(req, context=self._ctx, timeout=self.timeout) as resp:
                    return json.loads(resp.read())
            except urllib.error.HTTPError as e:
                if attempt == self.retry_count - 1:
                    body = e.read().decode(errors="replace")
                    raise APIError(
                        f"HTTP {e.code} on {path}: {body}",
                        status_code=e.code,
                        details={"path": path, "attempt": attempt + 1},
                    )
            except TimeoutError:
                raise TimeoutError(f"Request timed out after {self.timeout}s")
            except Exception as e:
                if attempt == self.retry_count - 1:
                    raise ConnectionError(f"Connection failed: {e}", details={"path": path})

            if attempt < self.retry_count - 1:
                time.sleep(self.retry_delay * (attempt + 1))

        raise ConnectionError("Max retries exceeded")

    def _get(self, path: str) -> Dict[str, Any]:
        return self._urlopen("GET", path)

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        body = json.dumps(payload).encode()
        return self._urlopen("POST", path, data=body)

    # ── Node API ──────────────────────────────────────────────────────────────

    def health(self) -> Dict[str, Any]:
        """
        Check node health and version info.

        Returns:
            Dict with keys: ok, version, uptime_s, db_rw, etc.

        Example:
            >>> client.health()
            {'ok': True, 'version': '2.2.1-rip200', 'uptime_s': 140828}
        """
        return self._get("/health")

    def epoch(self) -> Dict[str, Any]:
        """
        Get current epoch information.

        Returns:
            Dict with keys: epoch, slot, height, blocks_per_epoch, epoch_pot.

        Example:
            >>> client.epoch()
            {'epoch': 95, 'slot': 12345, 'height': 67890}
        """
        return self._get("/epoch")

    def miners(self) -> List[Dict[str, Any]]:
        """
        List all active miners on the network.

        Returns:
            List of miner dicts with keys: miner, antiquity_multiplier,
            device_arch, device_family, hardware_type, last_attest, etc.

        Example:
            >>> clients.miners()[0]
            {'miner': 'g4-powerbook-001', 'antiquity_multiplier': 2.5, 'device_arch': 'G4'}
        """
        return self._get("/api/miners")

    def balance(self, wallet_id: str) -> Dict[str, Any]:
        """
        Get RTC balance for a wallet.

        Args:
            wallet_id: The wallet/miner ID to query.

        Returns:
            Dict with keys: amount_i64, amount_rtc, miner_id.

        Example:
            >>> client.balance("Ivan-houzhiwen")
            {'amount_i64': 155000000, 'amount_rtc': 155.0, 'miner_id': 'Ivan-houzhiwen'}
        """
        if not wallet_id or not wallet_id.strip():
            raise ValidationError("wallet_id cannot be empty")
        return self._get(f"/wallet/balance?miner_id={wallet_id.strip()}")

    def transfer(
        self,
        from_wallet: str,
        to_wallet: str,
        amount: int,
        signature: str,
        fee: int = 0,
        timestamp: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Submit a signed RTC transfer.

        Args:
            from_wallet: Sender wallet ID.
            to_wallet: Recipient wallet ID.
            amount: Amount in smallest units (1 RTC = 1_000_000 units).
            signature: Hex-encoded Ed25519 signature of the transfer payload.
            fee: Transaction fee in smallest units (default 0).
            timestamp: Unix timestamp for replay protection (default: now).

        Returns:
            Dict with keys: success, tx_hash, etc.

        Example:
            >>> client.transfer(
            ...     from_wallet="alice",
            ...     to_wallet="bob",
            ...     amount=1_000_000,   # 1 RTC
            ...     signature="abc123...",
            ... )
            {'success': True, 'tx_hash': '...'}
        """
        if not from_wallet or not to_wallet:
            raise ValidationError("from_wallet and to_wallet cannot be empty")
        if amount <= 0:
            raise ValidationError(f"amount must be positive, got {amount}")
        if timestamp is None:
            timestamp = int(time.time())

        payload = {
            "from": from_wallet,
            "to": to_wallet,
            "amount": amount,
            "fee": fee,
            "signature": signature,
            "timestamp": timestamp,
        }
        return self._post("/wallet/transfer/signed", payload)

    def attestation_status(self, miner_id: str) -> Dict[str, Any]:
        """
        Get attestation status for a miner.

        Args:
            miner_id: The miner ID to check.

        Returns:
            Dict with keys: miner_id, verified, last_attest, epochs_attested,
            fingerprint_quality, antiquity_score, etc.

        Example:
            >>> client.attestation_status("g4-powerbook-001")
            {'miner_id': 'g4-powerbook-001', 'verified': True, 'antiquity_score': 2.5}
        """
        if not miner_id or not miner_id.strip():
            raise ValidationError("miner_id cannot be empty")
        return self._get(f"/attest/status/{miner_id}")

    # ── Signed transfer convenience ────────────────────────────────────────────

    def transfer_signed(
        self,
        from_wallet: str,
        to_wallet: str,
        amount: int,
        signing_key: "SigningKey",
        fee: int = 0,
    ) -> Dict[str, Any]:
        """
        Sign and submit a transfer in one call.

        Args:
            from_wallet: Sender wallet ID.
            to_wallet: Recipient wallet ID.
            amount: Amount in smallest units.
            signing_key: Ed25519 SigningKey instance.
            fee: Transaction fee in smallest units.

        Returns:
            Transfer result from the node.
        """
        sig, payload = signing_key.sign_transfer(from_wallet, to_wallet, amount, fee)
        return self._post("/wallet/transfer/signed", {**payload, "signature": sig})


# ─────────────────────────────────────────────────────────────────────────────
# Async Client
# ─────────────────────────────────────────────────────────────────────────────


class AsyncRustChainClient:
    """
    Async RustChain API client (uses aiohttp).

    Example:
        >>> async def main():
        ...     client = AsyncRustChainClient()
        ...     health = await client.health()
        ...     epoch = await client.epoch()
        ...
        >>> asyncio.run(main())
    """

    DEFAULT_BASE_URL = "https://50.28.86.131"

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        timeout: int = 30,
        verify_ssl: bool = False,
        retry_count: int = 3,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.retry_count = retry_count
        self._ctx: Optional[ssl.SSLContext] = None
        if not verify_ssl:
            self._ctx = ssl.create_default_context()
            self._ctx.check_hostname = False
            self._ctx.verify_mode = ssl.CERT_NONE

        self.explorer = Explorer(
            base_url=self.base_url,
            timeout=self.timeout,
            verify_ssl=self.verify_ssl,
        )

    def _ssl_context(self) -> Optional[ssl.SSLContext]:
        return self._ctx

    async def _request(
        self,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        for attempt in range(self.retry_count):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.request(
                        method,
                        f"{self.base_url}{path}",
                        json=json,
                        params=params,
                        ssl=self._ssl_context(),
                    ) as resp:
                        resp.raise_for_status()
                        return await resp.json()
            except aiohttp.ClientResponseError as e:
                if attempt == self.retry_count - 1:
                    raise APIError(
                        f"HTTP {e.status} on {path}: {e.message}",
                        status_code=e.status,
                        details={"path": path},
                    )
            except TimeoutError:
                raise TimeoutError(f"Request timed out after {self.timeout}s")
            except Exception as e:
                if attempt == self.retry_count - 1:
                    raise ConnectionError(f"Connection failed: {e}", details={"path": path})
        raise ConnectionError("Max retries exceeded")

    async def health(self) -> Dict[str, Any]:
        return await self._request("GET", "/health")

    async def epoch(self) -> Dict[str, Any]:
        return await self._request("GET", "/epoch")

    async def miners(self) -> List[Dict[str, Any]]:
        return await self._request("GET", "/api/miners")

    async def balance(self, wallet_id: str) -> Dict[str, Any]:
        if not wallet_id or not wallet_id.strip():
            raise ValidationError("wallet_id cannot be empty")
        return await self._request("GET", f"/wallet/balance?miner_id={wallet_id.strip()}")

    async def transfer(
        self,
        from_wallet: str,
        to_wallet: str,
        amount: int,
        signature: str,
        fee: int = 0,
        timestamp: Optional[int] = None,
    ) -> Dict[str, Any]:
        if not from_wallet or not to_wallet:
            raise ValidationError("from_wallet and to_wallet cannot be empty")
        if amount <= 0:
            raise ValidationError(f"amount must be positive, got {amount}")
        payload = {
            "from": from_wallet,
            "to": to_wallet,
            "amount": amount,
            "fee": fee,
            "signature": signature,
            "timestamp": timestamp or int(time.time()),
        }
        return await self._request("POST", "/wallet/transfer/signed", json=payload)

    async def attestation_status(self, miner_id: str) -> Dict[str, Any]:
        if not miner_id or not miner_id.strip():
            raise ValidationError("miner_id cannot be empty")
        return await self._request("GET", f"/attest/status/{miner_id}")

    async def transfer_signed(
        self,
        from_wallet: str,
        to_wallet: str,
        amount: int,
        signing_key: "SigningKey",
        fee: int = 0,
    ) -> Dict[str, Any]:
        sig, payload = signing_key.sign_transfer(from_wallet, to_wallet, amount, fee)
        return await self._request(
            "POST", "/wallet/transfer/signed", json={**payload, "signature": sig}
        )
