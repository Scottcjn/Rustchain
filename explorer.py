"""Explorer sub-client for RustChain block and transaction browsing."""

from __future__ import annotations

from typing import Any

import httpx

from rustchain.models import (
    Block,
    BlockListResponse,
    Transaction,
    TransactionListResponse,
)
from rustchain.exceptions import APIError, NetworkError, RustChainError


class ExplorerClient:
    """Sub-client for RustChain explorer endpoints (blocks & transactions)."""

    def __init__(self, http_client: httpx.AsyncClient, base_url: str) -> None:
        self._http = http_client
        self._base = base_url.rstrip("/")

    async def blocks(
        self,
        *,
        page: int = 1,
        per_page: int = 20,
    ) -> BlockListResponse:
        """Fetch recent blocks from the explorer.

        Args:
            page: Page number (1-indexed).
            per_page: Number of results per page (max 100).

        Returns:
            BlockListResponse with a list of recent Block objects.
        """
        try:
            response = await self._http.get(
                f"{self._base}/explorer/blocks",
                params={"page": page, "per_page": min(per_page, 100)},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            # Normalise block dicts into Block models
            blocks = [Block(**b) for b in data.get("blocks", data)]
            total = data.get("total", len(blocks))
            page_num = data.get("page", page)
            per_p = data.get("per_page", per_page)

            return BlockListResponse(
                blocks=blocks,
                total=total,
                page=page_num,
                per_page=per_p,
            )
        except httpx.TimeoutException as e:
            raise NetworkError("Timeout fetching blocks from explorer") from e
        except httpx.HTTPStatusError as e:
            raise APIError(
                f"API error fetching blocks: {e.response.text}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise NetworkError(f"Network error fetching blocks: {e}") from e

    async def transactions(
        self,
        *,
        page: int = 1,
        per_page: int = 20,
    ) -> TransactionListResponse:
        """Fetch recent transactions from the explorer.

        Args:
            page: Page number (1-indexed).
            per_page: Number of results per page (max 100).

        Returns:
            TransactionListResponse with a list of recent Transaction objects.
        """
        try:
            response = await self._http.get(
                f"{self._base}/explorer/transactions",
                params={"page": page, "per_page": min(per_page, 100)},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            transactions = [
                Transaction(**t) for t in data.get("transactions", data)
            ]
            total = data.get("total", len(transactions))
            page_num = data.get("page", page)
            per_p = data.get("per_page", per_page)

            return TransactionListResponse(
                transactions=transactions,
                total=total,
                page=page_num,
                per_page=per_p,
            )
        except httpx.TimeoutException as e:
            raise NetworkError("Timeout fetching transactions from explorer") from e
        except httpx.HTTPStatusError as e:
            raise APIError(
                f"API error fetching transactions: {e.response.text}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise NetworkError(f"Network error fetching transactions: {e}") from e
