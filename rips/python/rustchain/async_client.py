import httpx
from typing import Dict, Any
from .models import Stats

class AsyncRustChainClient:
    def __init__(self, base_url: str, verify: bool = False):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(base_url=self.base_url, verify=verify)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def get_health(self) -> Dict[str, Any]:
        resp = await self.client.get("/health")
        resp.raise_for_status()
        return resp.json()

    async def get_stats(self) -> Stats:
        resp = await self.client.get("/api/stats")
        resp.raise_for_status()
        return Stats(**resp.json())

    async def get_balance(self, miner_id: str) -> float:
        resp = await self.client.get("/wallet/balance", params={"miner_id": miner_id})
        resp.raise_for_status()
        return resp.json().get("amount_rtc", 0.0)
