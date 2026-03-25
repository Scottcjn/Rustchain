"""Sync and async clients for RustChain nodes."""
from __future__ import annotations
import httpx
from typing import Any, Optional
from .exceptions import APIError, ConnectionError, TimeoutError, ValidationError
from .models import (
    HealthStatus, EpochInfo, Miner, Balance, TransferResult,
    AttestationStatus, Block, Transaction,
)

DEFAULT_NODE = "https://50.28.86.131"
DEFAULT_TIMEOUT = 30.0


def _parse_health(data: dict[str, Any]) -> HealthStatus:
    return HealthStatus(
        status=data.get("status", "unknown"),
        uptime=float(data.get("uptime", 0)),
        version=data.get("version", "unknown"),
        raw=data,
    )

def _parse_epoch(data: dict[str, Any]) -> EpochInfo:
    return EpochInfo(
        epoch=int(data.get("epoch", 0)),
        start_time=data.get("start_time", ""),
        end_time=data.get("end_time", ""),
        miners_active=int(data.get("miners_active", 0)),
        raw=data,
    )

def _parse_miner(data: dict[str, Any]) -> Miner:
    return Miner(
        id=data.get("id", data.get("miner_id", "")),
        wallet=data.get("wallet", data.get("wallet_id", "")),
        hardware=data.get("hardware", data.get("hardware_hash", "")),
        score=float(data.get("score", data.get("antiquity_score", 0))),
        status=data.get("status", "unknown"),
        raw=data,
    )

def _parse_balance(wallet_id: str, data: dict[str, Any]) -> Balance:
    return Balance(
        wallet_id=wallet_id,
        balance=float(data.get("balance", 0)),
        currency=data.get("currency", "RTC"),
        raw=data,
    )

def _parse_transfer(data: dict[str, Any]) -> TransferResult:
    return TransferResult(
        tx_hash=data.get("tx_hash", ""),
        from_wallet=data.get("from", data.get("from_wallet", "")),
        to_wallet=data.get("to", data.get("to_wallet", "")),
        amount=float(data.get("amount", 0)),
        status=data.get("status", "pending"),
        raw=data,
    )

def _parse_attestation(miner_id: str, data: dict[str, Any]) -> AttestationStatus:
    return AttestationStatus(
        miner_id=miner_id,
        attested=bool(data.get("attested", False)),
        epoch=int(data.get("epoch", 0)),
        hardware_hash=data.get("hardware_hash", ""),
        raw=data,
    )

def _parse_block(data: dict[str, Any]) -> Block:
    return Block(
        height=int(data.get("height", data.get("block_height", 0))),
        hash=data.get("hash", data.get("block_hash", "")),
        timestamp=data.get("timestamp", ""),
        miner=data.get("miner", data.get("miner_id", "")),
        tx_count=int(data.get("tx_count", data.get("transactions", 0))),
        raw=data,
    )

def _parse_transaction(data: dict[str, Any]) -> Transaction:
    return Transaction(
        tx_hash=data.get("tx_hash", ""),
        from_wallet=data.get("from", data.get("from_wallet", "")),
        to_wallet=data.get("to", data.get("to_wallet", "")),
        amount=float(data.get("amount", 0)),
        block_height=int(data.get("block_height", 0)),
        timestamp=data.get("timestamp", ""),
        raw=data,
    )


class _ExplorerMixin:
    """Explorer sub-namespace for block/tx queries."""
    def __init__(self, _get):
        self._get = _get

    def blocks(self, limit: int = 10) -> list[Block]:
        data = self._get("/api/explorer/blocks", params={"limit": limit})
        items = data if isinstance(data, list) else data.get("blocks", data.get("items", []))
        return [_parse_block(b) for b in items]

    def transactions(self, limit: int = 10) -> list[Transaction]:
        data = self._get("/api/explorer/transactions", params={"limit": limit})
        items = data if isinstance(data, list) else data.get("transactions", data.get("items", []))
        return [_parse_transaction(t) for t in items]


class _AsyncExplorerMixin:
    def __init__(self, _get):
        self._get = _get

    async def blocks(self, limit: int = 10) -> list[Block]:
        data = await self._get("/api/explorer/blocks", params={"limit": limit})
        items = data if isinstance(data, list) else data.get("blocks", data.get("items", []))
        return [_parse_block(b) for b in items]

    async def transactions(self, limit: int = 10) -> list[Transaction]:
        data = await self._get("/api/explorer/transactions", params={"limit": limit})
        items = data if isinstance(data, list) else data.get("transactions", data.get("items", []))
        return [_parse_transaction(t) for t in items]


class RustChainClient:
    """Synchronous RustChain client."""

    def __init__(self, node_url: str = DEFAULT_NODE, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._base = node_url.rstrip("/")
        self._client = httpx.Client(base_url=self._base, timeout=timeout, verify=False)
        self.explorer = _ExplorerMixin(self._get)

    def _get(self, path: str, params: Optional[dict] = None) -> Any:
        try:
            r = self._client.get(path, params=params)
        except httpx.ConnectError as e:
            raise ConnectionError(str(e)) from e
        except httpx.TimeoutException as e:
            raise TimeoutError(str(e)) from e
        if r.status_code >= 400:
            raise APIError(r.status_code, r.text[:500])
        return r.json()

    def _post(self, path: str, json_body: dict) -> Any:
        try:
            r = self._client.post(path, json=json_body)
        except httpx.ConnectError as e:
            raise ConnectionError(str(e)) from e
        except httpx.TimeoutException as e:
            raise TimeoutError(str(e)) from e
        if r.status_code >= 400:
            raise APIError(r.status_code, r.text[:500])
        return r.json()

    def health(self) -> HealthStatus:
        return _parse_health(self._get("/health"))

    def epoch(self) -> EpochInfo:
        return _parse_epoch(self._get("/epoch"))

    def miners(self) -> list[Miner]:
        data = self._get("/api/miners")
        items = data if isinstance(data, list) else data.get("miners", [])
        return [_parse_miner(m) for m in items]

    def balance(self, wallet_id: str) -> Balance:
        if not wallet_id:
            raise ValidationError("wallet_id must not be empty")
        return _parse_balance(wallet_id, self._get(f"/api/balance/{wallet_id}"))

    def transfer(self, from_wallet: str, to_wallet: str, amount: float, signature: str) -> TransferResult:
        if amount <= 0:
            raise ValidationError("amount must be positive")
        return _parse_transfer(self._post("/api/transfer", {
            "from": from_wallet, "to": to_wallet,
            "amount": amount, "signature": signature,
        }))

    def attestation_status(self, miner_id: str) -> AttestationStatus:
        if not miner_id:
            raise ValidationError("miner_id must not be empty")
        return _parse_attestation(miner_id, self._get(f"/api/attestation/{miner_id}"))

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.close()


class AsyncRustChainClient:
    """Async RustChain client using httpx.AsyncClient."""

    def __init__(self, node_url: str = DEFAULT_NODE, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._base = node_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self._base, timeout=timeout, verify=False)
        self.explorer = _AsyncExplorerMixin(self._get)

    async def _get(self, path: str, params: Optional[dict] = None) -> Any:
        try:
            r = await self._client.get(path, params=params)
        except httpx.ConnectError as e:
            raise ConnectionError(str(e)) from e
        except httpx.TimeoutException as e:
            raise TimeoutError(str(e)) from e
        if r.status_code >= 400:
            raise APIError(r.status_code, r.text[:500])
        return r.json()

    async def _post(self, path: str, json_body: dict) -> Any:
        try:
            r = await self._client.post(path, json=json_body)
        except httpx.ConnectError as e:
            raise ConnectionError(str(e)) from e
        except httpx.TimeoutException as e:
            raise TimeoutError(str(e)) from e
        if r.status_code >= 400:
            raise APIError(r.status_code, r.text[:500])
        return r.json()

    async def health(self) -> HealthStatus:
        return _parse_health(await self._get("/health"))

    async def epoch(self) -> EpochInfo:
        return _parse_epoch(await self._get("/epoch"))

    async def miners(self) -> list[Miner]:
        data = await self._get("/api/miners")
        items = data if isinstance(data, list) else data.get("miners", [])
        return [_parse_miner(m) for m in items]

    async def balance(self, wallet_id: str) -> Balance:
        if not wallet_id:
            raise ValidationError("wallet_id must not be empty")
        return _parse_balance(wallet_id, await self._get(f"/api/balance/{wallet_id}"))

    async def transfer(self, from_wallet: str, to_wallet: str, amount: float, signature: str) -> TransferResult:
        if amount <= 0:
            raise ValidationError("amount must be positive")
        return _parse_transfer(await self._post("/api/transfer", {
            "from": from_wallet, "to": to_wallet,
            "amount": amount, "signature": signature,
        }))

    async def attestation_status(self, miner_id: str) -> AttestationStatus:
        if not miner_id:
            raise ValidationError("miner_id must not be empty")
        return _parse_attestation(miner_id, await self._get(f"/api/attestation/{miner_id}"))

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        await self.close()
