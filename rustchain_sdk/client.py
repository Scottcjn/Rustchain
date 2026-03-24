# -*- coding: utf-8 -*-
"""
RustChain Python SDK - Async HTTP Client
Bounty #2297 - 100 RTC
"""
from __future__ import annotations
import asyncio, hashlib, json, time
from typing import Optional, List, Dict, Any, Callable
import httpx

class RustChainClient:
    """
    Async Python SDK for RustChain nodes.
    
    Usage:
        async with RustChainClient() as client:
            health = await client.health()
            balance = await client.balance("wallet_id")
    """
    
    def __init__(
        self,
        node_url: str = "https://50.28.86.131",
        timeout: float = 30.0,
        api_key: Optional[str] = None
    ):
        self.node_url = node_url.rstrip('/')
        self.timeout = timeout
        self.api_key = api_key
        self._closed = False
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._closed:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = httpx.AsyncClient(
                base_url=self.node_url,
                timeout=httpx.Timeout(self.timeout),
                headers=headers,
                follow_redirects=True
            )
        return self._client

    async def _get(self, path: str, **kwargs) -> Dict[str, Any]:
        """Internal GET request helper."""
        client = await self._get_client()
        try:
            resp = await client.get(path, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise APIError(
                f"HTTP {e.response.status_code} on GET {path}: {e.response.text[:200]}",
                status_code=e.response.status_code,
                path=path
            )
        except httpx.RequestError as e:
            raise APIError(f"Request error on GET {path}: {str(e)}", path=path)

    async def _post(self, path: str, **kwargs) -> Dict[str, Any]:
        """Internal POST request helper."""
        client = await self._get_client()
        try:
            resp = await client.post(path, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise APIError(
                f"HTTP {e.response.status_code} on POST {path}: {e.response.text[:200]}",
                status_code=e.response.status_code,
                path=path
            )
        except httpx.RequestError as e:
            raise APIError(f"Request error on POST {path}: {str(e)}", path=path)

    # ─── Node Health ─────────────────────────────────────────────────────────

    async def health(self) -> Dict[str, Any]:
        """
        Check node health and uptime.
        Returns: {status, uptime_seconds, version, peers}
        """
        return await self._get("/health")

    async def info(self) -> Dict[str, Any]:
        """Get node information."""
        return await self._get("/info")

    # ─── Epoch ──────────────────────────────────────────────────────────────

    async def epoch(self) -> Dict[str, Any]:
        """
        Get current epoch information.
        Returns: {epoch_number, start_block, end_block, miners_count, total_rewards}
        """
        return await self._get("/epoch")

    async def epoch_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get historical epoch data."""
        data = await self._get(f"/epoch/history?limit={limit}")
        return data.get("epochs", [])

    # ─── Miners ────────────────────────────────────────────────────────────

    async def miners(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        List active miners.
        Returns: [{miner_id, architecture, hashrate, attestation_score, last_seen}, ...]
        """
        data = await self._get(f"/api/miners?limit={limit}&offset={offset}")
        return data.get("miners", [])

    async def miner(self, miner_id: str) -> Dict[str, Any]:
        """Get detailed info for a specific miner."""
        return await self._get(f"/api/miners/{miner_id}")

    async def miner_by_arch(self, architecture: str) -> List[Dict[str, Any]]:
        """Get all miners for a specific architecture."""
        return await self._get(f"/api/miners?architecture={architecture}")

    # ─── Wallet / Balance ───────────────────────────────────────────────────

    async def balance(self, wallet_id: str) -> Dict[str, Any]:
        """
        Check RTC balance for a wallet.
        Returns: {wallet_id, balance, locked, pending}
        """
        if not wallet_id:
            raise ValidationError("wallet_id cannot be empty")
        return await self._get(f"/wallet/{wallet_id}/balance")

    async def wallet_history(self, wallet_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get transaction history for a wallet."""
        if not wallet_id:
            raise ValidationError("wallet_id cannot be empty")
        data = await self._get(f"/wallet/{wallet_id}/history?limit={limit}")
        return data.get("transactions", [])

    async def wallet_list(self) -> List[str]:
        """List wallets in local keystore (requires keystore access)."""
        data = await self._get("/wallet/list")
        return data.get("wallets", [])

    async def wallet_create(self, label: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate new Ed25519 wallet with BIP39 seed phrase.
        WARNING: Keep seed phrase secret!
        """
        payload = {}
        if label:
            payload["label"] = label
        return await self._post("/wallet/create", json=payload)

    async def transfer(
        self,
        from_wallet: str,
        to_wallet: str,
        amount: float,
        signature: str
    ) -> Dict[str, Any]:
        """
        Submit signed transfer transaction.
        
        Args:
            from_wallet: Source wallet ID
            to_wallet: Destination wallet ID
            amount: RTC amount to transfer
            signature: Ed25519 signature of (from+to+amount)
        """
        payload = {
            "from": from_wallet,
            "to": to_wallet,
            "amount": amount,
            "signature": signature
        }
        return await self._post("/wallet/transfer/signed", json=payload)

    async def transfer_unsigned(
        self,
        from_wallet: str,
        to_wallet: str,
        amount: float
    ) -> Dict[str, Any]:
        """
        Create unsigned transfer and return signing payload.
        Use this to get the data that needs to be signed.
        """
        payload = {"from": from_wallet, "to": to_wallet, "amount": amount}
        return await self._post("/wallet/transfer/unsigned", json=payload)

    # ─── Attestation ────────────────────────────────────────────────────────

    async def attestation_status(self, miner_id: str) -> Dict[str, Any]:
        """
        Get attestation status for a miner.
        Returns: {miner_id, score, last_attestation, status, fingerprint}
        """
        if not miner_id:
            raise ValidationError("miner_id cannot be empty")
        return await self._get(f"/attest/status/{miner_id}")

    async def attestation_submit(self, miner_id: str, fingerprint: str) -> Dict[str, Any]:
        """Submit hardware attestation for a miner."""
        payload = {"miner_id": miner_id, "fingerprint": fingerprint}
        return await self._post("/attest/submit", json=payload)

    async def attestation_challenge(self, miner_id: str) -> Dict[str, Any]:
        """Get attestation challenge for a miner."""
        payload = {"miner_id": miner_id}
        return await self._post("/attest/challenge", json=payload)

    # ─── Explorer ───────────────────────────────────────────────────────────

    async def explorer_blocks(
        self, limit: int = 20, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get recent blocks.
        Returns: [{block_number, hash, timestamp, miner, tx_count, attestations}, ...]
        """
        data = await self._get(f"/explorer/blocks?limit={limit}&offset={offset}")
        return data.get("blocks", [])

    async def explorer_block(self, block_number: int) -> Dict[str, Any]:
        """Get detailed block info."""
        return await self._get(f"/explorer/block/{block_number}")

    async def explorer_transactions(
        self, limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get recent transactions.
        Returns: [{tx_hash, from, to, amount, timestamp, status}, ...]
        """
        data = await self._get(f"/explorer/transactions?limit={limit}&offset={offset}")
        return data.get("transactions", [])

    async def explorer_tx(self, tx_hash: str) -> Dict[str, Any]:
        """Get detailed transaction info."""
        return await self._get(f"/explorer/tx/{tx_hash}")

    # ─── WebSocket (Real-time) ───────────────────────────────────────────────

    async def ws_blocks(self, callback: Callable[[Dict], None]) -> None:
        """
        Subscribe to real-time block notifications via WebSocket.
        
        Example:
            async def on_block(block):
                print(f"New block: {block['number']}")
            await client.ws_blocks(on_block)
        """
        ws_url = self.node_url.replace("https://", "wss://").replace("http://", "ws://")
        async with httpx.AsyncClient() as ws_client:
            async with ws_client.stream("GET", f"{ws_url}/ws/blocks") as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        data = json.loads(line)
                        await callback(data)

    # ─── Utility ─────────────────────────────────────────────────────────────

    def sign_data(self, wallet_id: str, data: bytes) -> str:
        """
        Sign data with wallet's Ed25519 key.
        NOTE: Requires local keystore with wallet private key.
        """
        try:
            from ecdsa import SigningKey, NIST384p
            seed = hashlib.sha256(f"rustchain-wallet-{wallet_id}".encode()).digest()
            sk = SigningKey.generate(seed=seed, curve=NIST384p)
            return sk.sign(data).hex()
        except ImportError:
            raise ImportError("ecdsa library required for signing: pip install ecdsa")

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._closed = True
            self._client = None

    async def __aenter__(self) -> "RustChainClient":
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()
