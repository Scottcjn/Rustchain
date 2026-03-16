"""RustChain API client."""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MinerInfo(BaseModel):
    miner: str
    last_attest: Optional[int] = None
    first_attest: Optional[int] = None
    entropy_score: float = 0.0
    device_arch: str = ""
    device_family: str = ""
    hardware_type: str = ""
    antiquity_multiplier: float = 1.0


class WalletBalance(BaseModel):
    miner_id: str
    amount_rtc: float
    amount_i64: int


class EpochInfo(BaseModel):
    epoch: int
    slot: int
    blocks_per_epoch: int
    enrolled_miners: int
    epoch_pot: float
    total_supply_rtc: int


class HealthInfo(BaseModel):
    ok: bool
    version: str = ""
    uptime_s: float = 0.0
    tip_age_slots: int = 0
    db_rw: bool = True
    backup_age_hours: float = 0.0


class RustChainClient:
    def __init__(self, base_url: str, verify_ssl: bool = False) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            verify=verify_ssl,
            timeout=15.0,
        )

    async def health(self) -> HealthInfo:
        resp = await self._client.get("/health")
        resp.raise_for_status()
        return HealthInfo(**resp.json())

    async def epoch(self) -> EpochInfo:
        resp = await self._client.get("/epoch")
        resp.raise_for_status()
        return EpochInfo(**resp.json())

    async def get_miners(self) -> list[MinerInfo]:
        resp = await self._client.get("/api/miners")
        resp.raise_for_status()
        return [MinerInfo(**m) for m in resp.json()]

    async def wallet_balance(self, miner_id: str) -> WalletBalance:
        resp = await self._client.get("/wallet/balance", params={"miner_id": miner_id})
        resp.raise_for_status()
        return WalletBalance(**resp.json())

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "RustChainClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()
