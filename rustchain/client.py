"""RustChain async client."""
import httpx

from .models import NodeHealth, EpochInfo, MinerInfo, BalanceInfo, SignedTransfer
from .exceptions import APIError, ValidationError, AuthenticationError


class RustChainClient:
    """
    Async client for RustChain node API.

    Supports context manager for proper resource cleanup.

    Example::
        async with RustChainClient() as client:
            health = await client.get_health()
            print(health.version)
    """

    def __init__(
        self,
        base_url: str = "https://rustchain.org",
        timeout: float = 30.0,
    ):
        """
        Initialize the RustChain client.

        Args:
            base_url: Base URL of the RustChain node API.
            timeout: Request timeout in seconds.
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "RustChainClient":
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            verify=False,  # self-signed certificate
        )
        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)
            self._client = None

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError(
                "Client not initialized. Use 'async with RustChainClient()' "
                "or call __aenter__() manually."
            )
        return self._client

    def _handle_response(self, response: httpx.Response) -> dict:
        """Handle HTTP response and raise appropriate exceptions."""
        if response.status_code == 400:
            raise ValidationError(f"Bad request: {response.text}")
        if response.status_code == 401 or response.status_code == 403:
            raise AuthenticationError(f"Authentication failed: {response.text}")
        if response.status_code >= 400:
            raise APIError(
                f"API error ({response.status_code}): {response.text}",
                status_code=response.status_code,
            )
        return response.json()

    async def get_health(self) -> NodeHealth:
        """
        Get node health status.

        Returns:
            NodeHealth object with ok, version, uptime_s, db_rw,
            tip_age_slots, backup_age_hours.
        """
        client = self._ensure_client()
        response = await client.get("/health")
        data = self._handle_response(response)
        return NodeHealth(**data)

    async def get_epoch(self) -> EpochInfo:
        """
        Get current epoch information.

        Returns:
            EpochInfo with epoch, slot, blocks_per_epoch, epoch_pot,
            enrolled_miners.
        """
        client = self._ensure_client()
        response = await client.get("/epoch")
        data = self._handle_response(response)
        return EpochInfo(**data)

    async def get_miners(self) -> list[MinerInfo]:
        """
        Get list of all miners.

        Returns:
            List of MinerInfo objects.
        """
        client = self._ensure_client()
        response = await client.get("/api/miners")
        data = self._handle_response(response)
        return [MinerInfo(**m) for m in data]

    async def get_balance(self, miner_id: str) -> BalanceInfo:
        """
        Get wallet balance for a miner.

        Args:
            miner_id: Miner name or ID.

        Returns:
            BalanceInfo with ok, miner_id, amount_rtc, amount_i64.
        """
        client = self._ensure_client()
        response = await client.get("/wallet/balance", params={"miner_id": miner_id})
        data = self._handle_response(response)
        return BalanceInfo(**data)

    async def submit_transfer_signed(self, tx: SignedTransfer) -> dict:
        """
        Submit a signed transfer transaction (no admin key required).

        Args:
            tx: SignedTransfer object with from_address, to_address,
                amount_rtc, nonce, signature, public_key.

        Returns:
            API response dict.
        """
        client = self._ensure_client()
        response = await client.post("/wallet/transfer/signed", json=tx.to_dict())
        return self._handle_response(response)

    async def admin_transfer(
        self,
        admin_key: str,
        from_miner: str,
        to_miner: str,
        amount_rtc: float,
    ) -> dict:
        """
        Submit an admin-only transfer (requires X-Admin-Key header).

        Args:
            admin_key: Admin API key.
            from_miner: Source miner ID.
            to_miner: Destination miner ID.
            amount_rtc: Amount to transfer in RTC.

        Returns:
            API response dict.
        """
        client = self._ensure_client()
        response = await client.post(
            "/wallet/transfer",
            headers={"X-Admin-Key": admin_key},
            json={
                "from_miner": from_miner,
                "to_miner": to_miner,
                "amount_rtc": amount_rtc,
            },
        )
        return self._handle_response(response)

    async def settle_rewards(self, admin_key: str) -> dict:
        """
        Settle miner rewards (admin only).

        Args:
            admin_key: Admin API key.

        Returns:
            API response dict.
        """
        client = self._ensure_client()
        response = await client.post(
            "/rewards/settle",
            headers={"X-Admin-Key": admin_key},
        )
        return self._handle_response(response)
