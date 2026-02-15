import httpx
from typing import Dict, Any, Optional
from .models import Stats, Miner
from .identity import Identity

class RustChainClient:
    def __init__(self, base_url: str, verify: bool = False, identity: Optional[Identity] = None):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(base_url=self.base_url, verify=verify)
        self.identity = identity

    def get_health(self) -> Dict[str, Any]:
        resp = self.client.get("/health")
        resp.raise_for_status()
        return resp.json()

    def get_stats(self) -> Stats:
        resp = self.client.get("/api/stats")
        resp.raise_for_status()
        return Stats(**resp.json())

    def get_balance(self, miner_id: str) -> float:
        resp = self.client.get("/wallet/balance", params={"miner_id": miner_id})
        resp.raise_for_status()
        return resp.json().get("amount_rtc", 0.0)

    def get_nonce(self, address: str) -> int:
        resp = self.client.get(f"/wallet/nonce/{address}")
        resp.raise_for_status()
        return resp.json().get("nonce", 0)

    def signed_transfer(self, to_address: str, amount_rtc: float, identity: Optional[Identity] = None):
        id_to_use = identity or self.identity
        if not id_to_use:
            raise ValueError("Identity required for signed transfer")

        nonce = self.get_nonce(id_to_use.address)

        # 构建负载并签名
        payload = f"{id_to_use.address}{to_address}{amount_rtc}{nonce}".encode()
        signature = id_to_use.sign(payload)

        # 提交请求
        data = {
            "from_address": id_to_use.address,
            "to_address": to_address,
            "amount_rtc": amount_rtc,
            "nonce": nonce,
            "signature": signature,
            "public_key": id_to_use.address # 在 Ed25519 中公钥即地址
        }
        return self.client.post("/wallet/transfer/signed", json=data).json()
