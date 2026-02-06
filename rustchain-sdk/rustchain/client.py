import httpx
from typing import List, Optional, Dict, Any, Union
from .models import (
    NodeHealth, EpochInfo, MinerInfo, WalletBalance, 
    TransferResult, AttestChallenge, AttestResult
)

class RustChainBase:
    DEFAULT_NODE = "https://50.28.86.131"
    
    def __init__(self, node_url: str = None, verify_ssl: bool = False, timeout: int = 30):
        self.node_url = (node_url or self.DEFAULT_NODE).rstrip('/')
        self.verify_ssl = verify_ssl
        self.timeout = timeout

class RustChainClient(RustChainBase):
    def __init__(self, node_url: str = None, verify_ssl: bool = False, timeout: int = 30):
        super().__init__(node_url, verify_ssl, timeout)
        self.client = httpx.Client(verify=self.verify_ssl, timeout=self.timeout)

    def close(self):
        self.client.close()
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def get_health(self) -> NodeHealth:
        """Check node health status."""
        resp = self.client.get(f"{self.node_url}/health")
        resp.raise_for_status()
        return NodeHealth.from_dict(resp.json())

    def get_epoch(self) -> EpochInfo:
        """Get current epoch information."""
        resp = self.client.get(f"{self.node_url}/epoch")
        resp.raise_for_status()
        return EpochInfo.from_dict(resp.json())

    def get_miners(self) -> List[MinerInfo]:
        """Get all active/enrolled miners."""
        resp = self.client.get(f"{self.node_url}/api/miners")
        resp.raise_for_status()
        return [MinerInfo.from_dict(m) for m in resp.json()]

    def get_miner(self, miner_id: str) -> Optional[MinerInfo]:
        """Get a specific miner by ID."""
        miners = self.get_miners()
        for m in miners:
            if m.miner == miner_id:
                return m
        return None

    def get_balance(self, miner_id: str) -> WalletBalance:
        """Get wallet balance."""
        resp = self.client.get(f"{self.node_url}/wallet/balance", params={"miner_id": miner_id})
        resp.raise_for_status()
        return WalletBalance.from_dict(resp.json())

    def attest_challenge(self) -> AttestChallenge:
        """Request a challenge nonce for hardware attestation."""
        resp = self.client.post(f"{self.node_url}/attest/challenge", json={})
        resp.raise_for_status()
        return AttestChallenge.from_dict(resp.json())

    def attest_submit(self, payload: Dict[str, Any]) -> AttestResult:
        """Submit hardware fingerprint for epoch enrollment."""
        resp = self.client.post(f"{self.node_url}/attest/submit", json=payload)
        # API might return 400 for failures but with JSON body
        if resp.is_error:
            try:
                return AttestResult.from_dict(resp.json())
            except:
                resp.raise_for_status()
        return AttestResult.from_dict(resp.json())

    def transfer(self, payload: Dict[str, Any]) -> TransferResult:
        """Transfer RTC tokens (requires signed payload)."""
        resp = self.client.post(f"{self.node_url}/wallet/transfer/signed", json=payload)
        if resp.is_error:
            try:
                return TransferResult.from_dict(resp.json())
            except:
                resp.raise_for_status()
        return TransferResult.from_dict(resp.json())

    def check_eligibility(self, miner_id: str) -> bool:
        """Check if a miner is eligible/enrolled (helper)."""
        return self.get_miner(miner_id) is not None


class AsyncRustChainClient(RustChainBase):
    def __init__(self, node_url: str = None, verify_ssl: bool = False, timeout: int = 30):
        super().__init__(node_url, verify_ssl, timeout)
        self.client = httpx.AsyncClient(verify=self.verify_ssl, timeout=self.timeout)

    async def close(self):
        await self.client.aclose()
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def get_health(self) -> NodeHealth:
        """Check node health status."""
        resp = await self.client.get(f"{self.node_url}/health")
        resp.raise_for_status()
        return NodeHealth.from_dict(resp.json())

    async def get_epoch(self) -> EpochInfo:
        """Get current epoch information."""
        resp = await self.client.get(f"{self.node_url}/epoch")
        resp.raise_for_status()
        return EpochInfo.from_dict(resp.json())

    async def get_miners(self) -> List[MinerInfo]:
        """Get all active/enrolled miners."""
        resp = await self.client.get(f"{self.node_url}/api/miners")
        resp.raise_for_status()
        return [MinerInfo.from_dict(m) for m in resp.json()]

    async def get_miner(self, miner_id: str) -> Optional[MinerInfo]:
        """Get a specific miner by ID."""
        miners = await self.get_miners()
        for m in miners:
            if m.miner == miner_id:
                return m
        return None

    async def get_balance(self, miner_id: str) -> WalletBalance:
        """Get wallet balance."""
        resp = await self.client.get(f"{self.node_url}/wallet/balance", params={"miner_id": miner_id})
        resp.raise_for_status()
        return WalletBalance.from_dict(resp.json())

    async def attest_challenge(self) -> AttestChallenge:
        """Request a challenge nonce for hardware attestation."""
        resp = await self.client.post(f"{self.node_url}/attest/challenge", json={})
        resp.raise_for_status()
        return AttestChallenge.from_dict(resp.json())

    async def attest_submit(self, payload: Dict[str, Any]) -> AttestResult:
        """Submit hardware fingerprint for epoch enrollment."""
        resp = await self.client.post(f"{self.node_url}/attest/submit", json=payload)
        if resp.is_error:
            try:
                return AttestResult.from_dict(resp.json())
            except:
                resp.raise_for_status()
        return AttestResult.from_dict(resp.json())

    async def transfer(self, payload: Dict[str, Any]) -> TransferResult:
        """Transfer RTC tokens (requires signed payload)."""
        resp = await self.client.post(f"{self.node_url}/wallet/transfer/signed", json=payload)
        if resp.is_error:
            try:
                return TransferResult.from_dict(resp.json())
            except:
                resp.raise_for_status()
        return TransferResult.from_dict(resp.json())

    async def check_eligibility(self, miner_id: str) -> bool:
        """Check if a miner is eligible/enrolled (helper)."""
        return (await self.get_miner(miner_id)) is not None
