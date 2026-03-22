"""Explorer sub-client for block/transaction queries."""

from typing import Any, Dict, List


class ExplorerClient:
    """Provides access to the RustChain block explorer endpoints."""

    def __init__(self, parent: Any) -> None:
        self._parent = parent

    async def blocks(self) -> List[Dict[str, Any]]:
        """Return recent blocks from the explorer.

        Returns:
            list: Recent block records.
        """
        return await self._parent._get("/api/explorer/blocks")

    async def transactions(self) -> List[Dict[str, Any]]:
        """Return recent transactions from the explorer.

        Returns:
            list: Recent transaction records.
        """
        return await self._parent._get("/api/explorer/transactions")
