"""
RustChain Explorer API
Access block and transaction data from the RustChain explorer.
"""

from typing import Any, Dict, List, Optional

import aiohttp
import httpx

from .exceptions import APIError, ConnectionError, TimeoutError


class Explorer:
    """
    RustChain block explorer API access.

    Example:
        client = RustChainClient()
        blocks = client.explorer.blocks(limit=10)
        txs = client.explorer.transactions(limit=50)
    """

    def __init__(
        self,
        base_url: str = "https://50.28.86.131",
        timeout: int = 30,
        verify_ssl: bool = False,
        _session: Optional[Any] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self._session = _session  # shared session for async

    # ─── Blocks ───────────────────────────────────────────────────────────────

    def blocks(self, *, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """
        Fetch recent blocks from the explorer.

        Args:
            limit: Number of blocks to return (max 100).
            offset: Pagination offset.

        Returns:
            Dict with 'blocks' list and pagination metadata.

        Example:
            >>> client.explorer.blocks(limit=10)
            {'blocks': [{'height': 1234, 'hash': '...', 'epoch': 5, ...}], 'total': 500}
        """
        return self._sync_request(
            "GET",
            "/blocks",
            params={"limit": limit, "offset": offset},
        )

    def block_by_height(self, height: int) -> Dict[str, Any]:
        """Get a single block by its height."""
        return self._sync_request("GET", f"/blocks/{height}")

    def block_by_hash(self, block_hash: str) -> Dict[str, Any]:
        """Get a single block by its hash."""
        return self._sync_request("GET", f"/blocks/hash/{block_hash}")

    # ─── Transactions ─────────────────────────────────────────────────────────

    def transactions(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        wallet_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch recent transactions from the explorer.

        Args:
            limit: Number of transactions to return (max 100).
            offset: Pagination offset.
            wallet_id: Filter transactions for a specific wallet.

        Returns:
            Dict with 'transactions' list and pagination metadata.

        Example:
            >>> client.explorer.transactions(limit=50)
            {'transactions': [{'hash': '...', 'from': 'a', 'to': 'b', 'amount': 100}], 'total': 200}
        """
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if wallet_id:
            params["wallet_id"] = wallet_id
        return self._sync_request("GET", "/api/transactions", params=params)

    def transaction_by_hash(self, tx_hash: str) -> Dict[str, Any]:
        """Get a single transaction by its hash."""
        return self._sync_request("GET", f"/api/transactions/{tx_hash}")

    # ─── Sync helper ────────────────────────────────────────────────────────────

    def _sync_request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            import urllib.request
            import urllib.error
            import ssl
            import json as _json

            url = f"{self.base_url}{path}"
            data = _json.dumps(json).encode() if json else None

            ctx = ssl.create_default_context()
            if not self.verify_ssl:
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE

            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                method=method,
            )

            with urllib.request.urlopen(req, context=ctx, timeout=self.timeout) as resp:
                return _json.loads(resp.read())

        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            raise APIError(
                f"HTTP {e.code} on {path}: {body}",
                status_code=e.code,
                details={"path": path},
            )
        except TimeoutError:
            raise TimeoutError(f"Request to {path} timed out after {self.timeout}s")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to explorer: {e}", details={"path": path})

    # ─── Async helpers (called by AsyncRustChainClient) ────────────────────────

    async def _async_request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        ssl_ctx = None
        if not self.verify_ssl:
            import ssl as ssl_module
            ssl_ctx = ssl_module.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl_module.CERT_NONE

        timeout = aiohttp.ClientTimeout(total=self.timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(
                method,
                f"{self.base_url}{path}",
                params=params,
                json=json,
                ssl=ssl_ctx if ssl_ctx else None,
            ) as resp:
                resp.raise_for_status()
                return await resp.json()
