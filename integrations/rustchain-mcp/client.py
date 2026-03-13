#!/usr/bin/env python3
"""
RustChain MCP - API Client

Async HTTP client for RustChain blockchain API endpoints.
Handles health checks, epoch info, wallet balances, and generic queries.
"""

import asyncio
import logging
import os
from typing import Any, Optional

import aiohttp

try:
    from .schemas import (
        APIError,
        EpochInfo,
        HealthStatus,
        MinerInfo,
        NetworkStats,
        QueryResult,
        WalletBalance,
    )
except ImportError:
    from schemas import (
        APIError,
        EpochInfo,
        HealthStatus,
        MinerInfo,
        NetworkStats,
        QueryResult,
        WalletBalance,
    )

logger = logging.getLogger(__name__)

# Default configuration
RUSTCHAIN_API_BASE = os.getenv("RUSTCHAIN_API_BASE", "https://50.28.86.131")
RUSTCHAIN_NODE_URL = os.getenv("RUSTCHAIN_NODE_URL", "https://50.28.86.131:5000")
REQUEST_TIMEOUT = int(os.getenv("RUSTCHAIN_TIMEOUT", "30"))
RETRY_COUNT = int(os.getenv("RUSTCHAIN_RETRY", "2"))


class RustChainClient:
    """Async client for RustChain blockchain API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        node_url: Optional[str] = None,
        timeout: int = REQUEST_TIMEOUT,
        retry_count: int = RETRY_COUNT,
        session: Optional[aiohttp.ClientSession] = None,
    ):
        """
        Initialize RustChain client.

        Args:
            base_url: Base API URL (default: from env or https://50.28.86.131)
            node_url: Node RPC URL (default: from env)
            timeout: Request timeout in seconds
            retry_count: Number of retries on failure
            session: Optional existing aiohttp session
        """
        self.base_url = (base_url or RUSTCHAIN_API_BASE).rstrip("/")
        self.node_url = (node_url or RUSTCHAIN_NODE_URL).rstrip("/")
        self.timeout = timeout
        self.retry_count = retry_count
        self._session = session
        self._owns_session = session is None

    async def __aenter__(self) -> "RustChainClient":
        """Async context manager entry."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    async def _ensure_session(self) -> None:
        """Ensure HTTP session exists."""
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers={
                    "User-Agent": "RustChain-MCP-Client/1.0",
                    "Accept": "application/json",
                },
            )
            self._owns_session = True

    async def close(self) -> None:
        """Close HTTP session if owned."""
        if self._owns_session and self._session:
            await self._session.close()
            self._session = None

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Make HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Optional query parameters
            json_data: Optional JSON body

        Returns:
            Parsed JSON response

        Raises:
            APIError: On API error or connection failure
        """
        await self._ensure_session()
        url = f"{self.base_url}{endpoint}"

        last_error: Optional[Exception] = None
        for attempt in range(self.retry_count + 1):
            try:
                async with self._session.request(
                    method,
                    url,
                    params=params,
                    json=json_data,
                    ssl=False,  # Self-signed cert
                ) as resp:
                    if resp.status >= 400:
                        error_body = await resp.json()
                        raise APIError.from_response(resp.status, error_body)
                    return await resp.json()
            except aiohttp.ClientError as e:
                last_error = e
                logger.warning(f"Request failed (attempt {attempt + 1}): {e}")
                if attempt < self.retry_count:
                    await asyncio.sleep(0.5 * (attempt + 1))
            except APIError:
                raise

        raise APIError(
            code="CONNECTION_FAILED",
            message=f"Failed after {self.retry_count + 1} attempts: {last_error}",
            status_code=503,
        )

    async def health(self) -> HealthStatus:
        """
        Check API health status.

        Returns:
            HealthStatus with service health information
        """
        data = await self._request("GET", "/api/health")
        return HealthStatus.from_dict(data)

    async def epoch(self, epoch_number: Optional[int] = None) -> EpochInfo:
        """
        Get epoch information.

        Args:
            epoch_number: Specific epoch (optional, defaults to current)

        Returns:
            EpochInfo with epoch details
        """
        if epoch_number is None:
            endpoint = "/epoch"
        else:
            endpoint = f"/api/epochs/{epoch_number}"

        data = await self._request("GET", endpoint)
        return EpochInfo.from_dict(data)

    async def balance(self, miner_id: str) -> WalletBalance:
        """
        Get wallet balance for a miner.

        Args:
            miner_id: Miner ID or wallet name

        Returns:
            WalletBalance with balance information
        """
        data = await self._request(
            "GET", "/wallet/balance", params={"miner_id": miner_id}
        )
        return WalletBalance.from_dict(data)

    async def query(
        self,
        query_type: str,
        params: Optional[dict[str, Any]] = None,
        limit: int = 50,
    ) -> QueryResult:
        """
        Execute a generic query.

        Args:
            query_type: Type of query (miners, blocks, transactions, etc.)
            params: Query-specific parameters
            limit: Maximum results to return

        Returns:
            QueryResult with query data
        """
        query_params = {"type": query_type, "limit": limit}
        if params:
            query_params.update(params)

        data = await self._request("GET", "/api/query", params=query_params)
        return QueryResult.from_dict(data)

    async def miners(
        self,
        limit: int = 50,
        hardware_type: Optional[str] = None,
        min_score: Optional[float] = None,
    ) -> list[MinerInfo]:
        """
        Get list of miners.

        Args:
            limit: Maximum miners to return
            hardware_type: Filter by hardware type
            min_score: Minimum score threshold

        Returns:
            List of MinerInfo
        """
        params = {"limit": limit}
        data = await self._request("GET", "/api/miners", params=params)

        miners_data = data.get("miners", [])
        miners = [MinerInfo.from_dict(m) for m in miners_data]

        if hardware_type:
            miners = [
                m for m in miners if hardware_type.lower() in m.hardware.lower()
            ]
        if min_score is not None:
            miners = [m for m in miners if m.score >= min_score]

        return miners

    async def stats(self) -> NetworkStats:
        """
        Get network statistics.

        Returns:
            NetworkStats with network-wide metrics
        """
        data = await self._request("GET", "/api/stats")
        return NetworkStats.from_dict(data)

    async def ping(self) -> bool:
        """
        Quick connectivity check.

        Returns:
            True if API is reachable
        """
        try:
            await self.health()
            return True
        except Exception:
            return False


# Convenience functions for simple usage

async def get_health(base_url: Optional[str] = None) -> HealthStatus:
    """Get API health status."""
    async with RustChainClient(base_url=base_url) as client:
        return await client.health()


async def get_epoch(
    epoch_number: Optional[int] = None, base_url: Optional[str] = None
) -> EpochInfo:
    """Get epoch information."""
    async with RustChainClient(base_url=base_url) as client:
        return await client.epoch(epoch_number)


async def get_balance(
    miner_id: str, base_url: Optional[str] = None
) -> WalletBalance:
    """Get wallet balance."""
    async with RustChainClient(base_url=base_url) as client:
        return await client.balance(miner_id)


async def run_query(
    query_type: str,
    params: Optional[dict[str, Any]] = None,
    limit: int = 50,
    base_url: Optional[str] = None,
) -> QueryResult:
    """Execute a query."""
    async with RustChainClient(base_url=base_url) as client:
        return await client.query(query_type, params, limit)
