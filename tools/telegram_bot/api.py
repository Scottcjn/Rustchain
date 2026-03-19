"""
RustChain API client for the Telegram bot.
Provides typed access to the RustChain REST API.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import aiohttp

log = logging.getLogger(__name__)

# Default RustChain node (from bounty spec)
DEFAULT_BASE_URL = "https://explorer.rustchain.org"
FALLBACK_BASE_URL = "https://rustchain.org"


@dataclass
class NetworkStats:
    miners_total: int
    miners_active: int
    current_epoch: int
    total_supply_rtc: float
    avg_antiquity: float
    epoch_end: Optional[str] = None


@dataclass
class MinerInfo:
    miner_id: str
    architecture: str
    status: str
    antiquity: float
    blocks_mined: int
    balance: float
    last_attestation: int


@dataclass
class EpochInfo:
    number: int
    start_time: str
    end_time: str
    reward_per_block: float
    total_blocks: int
    active_miners: int


@dataclass
class HealthInfo:
    healthy: bool
    message: Optional[str]
    uptime_secs: int
    peers: int
    block_height: int


class RustChainAPI:
    """Async client for the RustChain REST API."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None
        self._stats_cache: dict = {}

    async def _get(self, path: str) -> dict:
        if self._session is None:
            self._session = aiohttp.ClientSession()
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            async with self._session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 404 and self.base_url != FALLBACK_BASE_URL:
                    # Retry with fallback
                    self.base_url = FALLBACK_BASE_URL
                    url = f"{self.base_url}/{path.lstrip('/')}"
                    async with self._session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r2:
                        r2.raise_for_status()
                        return await r2.json()
                resp.raise_for_status()
                return await resp.json()
        except aiohttp.ClientError as e:
            log.error(f"API request failed: {url} → {e}")
            raise RustChainAPIError(f"Failed to fetch {url}: {e}")

    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None

    # ── Balance ──────────────────────────────────────────────────────────────

    async def get_balance(self, wallet: str) -> float:
        """Get RTC balance for a wallet address."""
        try:
            data = await self._get(f"balance/{wallet}")
            return _float_field(data, "balance", "amount", "rtc_balance")
        except Exception:
            # Try query param
            try:
                data = await self._get(f"balance?wallet={wallet}")
                return _float_field(data, "balance", "amount")
            except Exception:
                return 0.0

    # ── Miners ──────────────────────────────────────────────────────────────

    async def get_miners(self, limit: int = 20) -> list[dict]:
        """Get active miners list."""
        data = await self._get(f"api/miners?limit={limit}")
        return data.get("miners") or data.get("data") or data or []

    async def get_miner_count(self) -> tuple[int, int]:
        """Returns (active, total) miner counts."""
        data = await self._get("api/stats")
        active = _int_field(data, "miners_active", "active_miners")
        total = _int_field(data, "miners_total", "total_miners")
        return active or 0, total or 0

    async def get_network_stats(self) -> NetworkStats:
        """Get comprehensive network stats."""
        data = await self._get("api/stats")
        return NetworkStats(
            miners_total=_int_field(data, "miners_total"),
            miners_active=_int_field(data, "miners_active"),
            current_epoch=_int_field(data, "current_epoch"),
            total_supply_rtc=_float_field(data, "total_supply_rtc"),
            avg_antiquity=_float_field(data, "avg_antiquity"),
            epoch_end=data.get("epoch_end"),
        )

    # ── Epoch ───────────────────────────────────────────────────────────────

    async def get_epoch(self) -> EpochInfo:
        """Get current epoch information."""
        data = await self._get("epoch")
        return EpochInfo(
            number=_int_field(data, "number", "epoch"),
            start_time=data.get("start_time", ""),
            end_time=data.get("end_time", ""),
            reward_per_block=_float_field(data, "reward_per_block"),
            total_blocks=_int_field(data, "total_blocks"),
            active_miners=_int_field(data, "active_miners"),
        )

    # ── Health ──────────────────────────────────────────────────────────────

    async def get_health(self) -> HealthInfo:
        """Check node health."""
        data = await self._get("health")
        return HealthInfo(
            healthy=data.get("healthy", True),
            message=data.get("message"),
            uptime_secs=_int_field(data, "uptime_secs", "uptime"),
            peers=_int_field(data, "peers"),
            block_height=_int_field(data, "block_height"),
        )

    # ── Price (Raydium) ─────────────────────────────────────────────────────

    async def get_wrsc_price(self) -> Optional[float]:
        """Get wrapped RTC price from Raydium (approximation)."""
        # Raydium API for wrapped token price
        try:
            import aiohttp
            url = "https://api.raydium.io/v2/main/price"
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.ok:
                        data = await resp.json()
                        # Try common wRTC/SOL pair
                        return data.get("wRTC") or data.get("wrtc_usd")
        except Exception:
            pass
        return None


class RustChainAPIError(Exception):
    """Raised when the RustChain API returns an error."""
    pass


def _float_field(data: dict, *keys) -> float:
    for k in keys:
        if k in data and data[k] is not None:
            try:
                return float(data[k])
            except (ValueError, TypeError):
                pass
    return 0.0


def _int_field(data: dict, *keys) -> int:
    for k in keys:
        if k in data and data[k] is not None:
            try:
                return int(data[k])
            except (ValueError, TypeError):
                pass
    return 0
