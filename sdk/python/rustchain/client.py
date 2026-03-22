"""Async RustChain client."""

from __future__ import annotations

import os
import ssl
from typing import Any, Dict, List, Optional

import httpx

from .exceptions import (
    RustChainAuthError,
    RustChainConnectionError,
    RustChainHTTPError,
    RustChainNotFoundError,
    RustChainTimeoutError,
)
from .explorer import ExplorerClient

_DEFAULT_NODE = "https://50.28.86.131"


def _build_ssl_context(verify: bool) -> ssl.SSLContext | bool:
    """Return an SSLContext that skips verification, or True for normal TLS."""
    if not verify:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    return True


class RustChainClient:
    """Async client for interacting with a RustChain node.

    Parameters
    ----------
    node_url:
        Base URL of the node.  Defaults to the ``RUSTCHAIN_NODE_URL``
        environment variable or ``https://50.28.86.131``.
    timeout:
        Request timeout in seconds (default 30).
    verify_ssl:
        Whether to verify TLS certificates.  Set to ``False`` when
        connecting to a node served at a bare IP address.
    """

    def __init__(
        self,
        node_url: Optional[str] = None,
        *,
        timeout: float = 30.0,
        verify_ssl: bool = False,
    ) -> None:
        self.node_url = (
            node_url
            or os.environ.get("RUSTCHAIN_NODE_URL", _DEFAULT_NODE)
        ).rstrip("/")
        self._timeout = timeout
        self._verify_ssl = verify_ssl
        self._client: Optional[httpx.AsyncClient] = None
        self.explorer = ExplorerClient(self)

    # ------------------------------------------------------------------ #
    # Context-manager support                                               #
    # ------------------------------------------------------------------ #

    async def __aenter__(self) -> "RustChainClient":
        self._client = httpx.AsyncClient(
            base_url=self.node_url,
            timeout=self._timeout,
            verify=False if not self._verify_ssl else True,
        )
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------ #
    # Low-level helpers                                                     #
    # ------------------------------------------------------------------ #

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.node_url,
                timeout=self._timeout,
                verify=False if not self._verify_ssl else True,
            )
        return self._client

    async def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Issue a GET request and return the parsed JSON body."""
        client = self._get_client()
        try:
            response = await client.get(endpoint, params=params)
        except httpx.TimeoutException as exc:
            raise RustChainTimeoutError(str(exc)) from exc
        except httpx.ConnectError as exc:
            raise RustChainConnectionError(str(exc)) from exc
        return self._handle(response)

    async def _post(self, endpoint: str, json: Optional[Dict[str, Any]] = None) -> Any:
        """Issue a POST request and return the parsed JSON body."""
        client = self._get_client()
        try:
            response = await client.post(endpoint, json=json)
        except httpx.TimeoutException as exc:
            raise RustChainTimeoutError(str(exc)) from exc
        except httpx.ConnectError as exc:
            raise RustChainConnectionError(str(exc)) from exc
        return self._handle(response)

    @staticmethod
    def _handle(response: httpx.Response) -> Any:
        """Raise a typed exception for error status codes."""
        if response.status_code == 404:
            raise RustChainNotFoundError()
        if response.status_code in (401, 403):
            raise RustChainAuthError()
        if response.status_code >= 400:
            raise RustChainHTTPError(
                f"HTTP {response.status_code}: {response.text}",
                status_code=response.status_code,
            )
        return response.json()

    # ------------------------------------------------------------------ #
    # Public API                                                            #
    # ------------------------------------------------------------------ #

    async def health(self) -> Dict[str, Any]:
        """Check node health.

        Returns:
            dict: Health payload (``ok``, ``version``, ``uptime_s``, …).
        """
        return await self._get("/health")

    async def epoch(self) -> Dict[str, Any]:
        """Return current epoch information.

        Returns:
            dict: Epoch payload (``epoch``, ``slot``, ``blocks_per_epoch``, …).
        """
        return await self._get("/epoch")

    async def miners(self) -> List[Dict[str, Any]]:
        """List active miners.

        Returns:
            list: Miner records with hardware and attestation details.
        """
        return await self._get("/api/miners")

    async def balance(self, wallet_id: str) -> Dict[str, Any]:
        """Check the RTC balance for *wallet_id*.

        Parameters
        ----------
        wallet_id:
            The wallet name / miner ID to query.

        Returns:
            dict: Balance payload.
        """
        return await self._get("/wallet/balance", params={"miner_id": wallet_id})

    async def transfer(
        self,
        from_wallet: str,
        to_wallet: str,
        amount: float,
        signature: str,
    ) -> Dict[str, Any]:
        """Submit a signed RTC transfer.

        Parameters
        ----------
        from_wallet:
            Source wallet identifier.
        to_wallet:
            Destination wallet identifier.
        amount:
            Amount in RTC (must be positive).
        signature:
            Cryptographic signature authorising the transfer.

        Returns:
            dict: Transfer result payload.

        Raises:
            ValueError: If *amount* is not positive.
        """
        if amount <= 0:
            raise ValueError(f"amount must be positive, got {amount}")
        payload = {
            "from": from_wallet,
            "to": to_wallet,
            "amount": amount,
            "signature": signature,
        }
        return await self._post("/wallet/transfer", json=payload)

    async def attestation_status(self, miner_id: str) -> Dict[str, Any]:
        """Check the attestation status for *miner_id*.

        Parameters
        ----------
        miner_id:
            The miner whose attestation to query.

        Returns:
            dict: Attestation status payload.
        """
        return await self._get(f"/api/attestation/{miner_id}")
