"""Sync and async clients for the RustChain API."""

from __future__ import annotations

from typing import Any, Optional

import httpx

from rustchain.exceptions import (
    APIError,
    AuthenticationError,
    ConnectionError,
    NotFoundError,
    RustChainError,
)
from rustchain.models import (
    AttestationStatus,
    Balance,
    Block,
    Epoch,
    HealthStatus,
    Miner,
    Transaction,
    TransferResult,
)

DEFAULT_BASE_URL = "https://50.28.86.131"
DEFAULT_TIMEOUT = 30.0


def _handle_response(resp: httpx.Response) -> dict[str, Any]:
    """Raise typed exceptions for non-2xx responses."""
    if resp.status_code == 404:
        raise NotFoundError(f"Not found: {resp.url}", status_code=404)
    if resp.status_code in (401, 403):
        raise AuthenticationError(
            f"Auth failed: {resp.text}", status_code=resp.status_code
        )
    if resp.status_code >= 400:
        raise APIError(
            f"API error {resp.status_code}: {resp.text}",
            status_code=resp.status_code,
        )
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text}


class _ExplorerMixin:
    """Explorer sub-client for blocks and transactions."""

    def __init__(self, fetch):  # noqa: ANN001
        self._fetch = fetch

    def blocks(self, limit: int = 10) -> list[Block]:
        data = self._fetch("/explorer/blocks", params={"limit": limit})
        items = data if isinstance(data, list) else data.get("blocks", [])
        return [Block.model_validate(b) for b in items]

    def transactions(self, limit: int = 10) -> list[Transaction]:
        data = self._fetch("/explorer/transactions", params={"limit": limit})
        items = data if isinstance(data, list) else data.get("transactions", [])
        return [Transaction.model_validate(t) for t in items]


class _AsyncExplorerMixin:
    """Async explorer sub-client."""

    def __init__(self, fetch):  # noqa: ANN001
        self._fetch = fetch

    async def blocks(self, limit: int = 10) -> list[Block]:
        data = await self._fetch("/explorer/blocks", params={"limit": limit})
        items = data if isinstance(data, list) else data.get("blocks", [])
        return [Block.model_validate(b) for b in items]

    async def transactions(self, limit: int = 10) -> list[Transaction]:
        data = await self._fetch("/explorer/transactions", params={"limit": limit})
        items = data if isinstance(data, list) else data.get("transactions", [])
        return [Transaction.model_validate(t) for t in items]


class RustChainClient:
    """Synchronous RustChain API client.

    Usage::

        from rustchain import RustChainClient

        client = RustChainClient("https://50.28.86.131")
        print(client.health())
        print(client.epoch())
        for m in client.miners():
            print(m.miner_id, m.device_family)
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        verify: bool = False,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._http = httpx.Client(
            base_url=self._base_url,
            timeout=timeout,
            verify=verify,
            headers={"User-Agent": "rustchain-python-sdk/0.1.0"},
        )
        self.explorer = _ExplorerMixin(self._get)

    def _get(self, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            resp = self._http.get(path, **kwargs)
        except httpx.ConnectError as exc:
            raise ConnectionError(f"Cannot reach node: {exc}") from exc
        return _handle_response(resp)

    def _post(self, path: str, json: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        try:
            resp = self._http.post(path, json=json, **kwargs)
        except httpx.ConnectError as exc:
            raise ConnectionError(f"Cannot reach node: {exc}") from exc
        return _handle_response(resp)

    def health(self) -> HealthStatus:
        """Check node health."""
        return HealthStatus.model_validate(self._get("/health"))

    def epoch(self) -> Epoch:
        """Get current epoch info."""
        return Epoch.model_validate(self._get("/epoch"))

    def miners(self) -> list[Miner]:
        """List active miners."""
        data = self._get("/api/miners")
        items = data if isinstance(data, list) else data.get("miners", [])
        return [Miner.model_validate(m) for m in items]

    def balance(self, wallet_id: str) -> Balance:
        """Check RTC balance for a wallet."""
        return Balance.model_validate(self._get(f"/api/balance/{wallet_id}"))

    def transfer(
        self,
        from_wallet: str,
        to_wallet: str,
        amount: float,
        signature: str,
    ) -> TransferResult:
        """Submit a signed RTC transfer."""
        return TransferResult.model_validate(
            self._post(
                "/api/transfer",
                json={
                    "from": from_wallet,
                    "to": to_wallet,
                    "amount": amount,
                    "signature": signature,
                },
            )
        )

    def attestation_status(self, miner_id: str) -> AttestationStatus:
        """Check attestation status for a miner."""
        return AttestationStatus.model_validate(
            self._get(f"/api/attestation/{miner_id}")
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self):  # noqa: ANN204
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class AsyncRustChainClient:
    """Async RustChain API client.

    Usage::

        import asyncio
        from rustchain import AsyncRustChainClient

        async def main():
            async with AsyncRustChainClient() as client:
                health = await client.health()
                print(health)

        asyncio.run(main())
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        verify: bool = False,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
            verify=verify,
            headers={"User-Agent": "rustchain-python-sdk/0.1.0"},
        )
        self.explorer = _AsyncExplorerMixin(self._get)

    async def _get(self, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            resp = await self._http.get(path, **kwargs)
        except httpx.ConnectError as exc:
            raise ConnectionError(f"Cannot reach node: {exc}") from exc
        return _handle_response(resp)

    async def _post(self, path: str, json: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        try:
            resp = await self._http.post(path, json=json, **kwargs)
        except httpx.ConnectError as exc:
            raise ConnectionError(f"Cannot reach node: {exc}") from exc
        return _handle_response(resp)

    async def health(self) -> HealthStatus:
        return HealthStatus.model_validate(await self._get("/health"))

    async def epoch(self) -> Epoch:
        return Epoch.model_validate(await self._get("/epoch"))

    async def miners(self) -> list[Miner]:
        data = await self._get("/api/miners")
        items = data if isinstance(data, list) else data.get("miners", [])
        return [Miner.model_validate(m) for m in items]

    async def balance(self, wallet_id: str) -> Balance:
        return Balance.model_validate(await self._get(f"/api/balance/{wallet_id}"))

    async def transfer(
        self,
        from_wallet: str,
        to_wallet: str,
        amount: float,
        signature: str,
    ) -> TransferResult:
        return TransferResult.model_validate(
            await self._post(
                "/api/transfer",
                json={
                    "from": from_wallet,
                    "to": to_wallet,
                    "amount": amount,
                    "signature": signature,
                },
            )
        )

    async def attestation_status(self, miner_id: str) -> AttestationStatus:
        return AttestationStatus.model_validate(
            await self._get(f"/api/attestation/{miner_id}")
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self):  # noqa: ANN204
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
