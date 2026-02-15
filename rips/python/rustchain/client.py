import httpx
from typing import Dict, Any, List, Optional
from .models import Stats, Miner, Epoch, AttestationResponse
from .identity import Identity

class RustChainClient:
    def __init__(self, base_url: str, identity: Optional[Identity] = None, verify: bool = False):
        self.base_url = base_url.rstrip("/")
        self.identity = identity
        self.client = httpx.Client(base_url=self.base_url, verify=verify)

    def get_health(self) -> Dict[str, Any]:
        resp = self.client.get("/health")
        resp.raise_for_status()
        return resp.json()

    def get_stats(self) -> Stats:
        resp = self.client.get("/api/stats")
        resp.raise_for_status()
        return Stats(**resp.json())

    def get_epoch(self) -> Epoch:
        resp = self.client.get("/epoch")
        resp.raise_for_status()
        return Epoch(**resp.json())

    def get_miners(self) -> List[Miner]:
        resp = self.client.get("/api/miners")
        resp.raise_for_status()
        return [Miner(**m) for m in resp.json()]

    def get_balance(self, miner_id: str) -> float:
        resp = self.client.get("/wallet/balance", params={"miner_id": miner_id})
        resp.raise_for_status()
        return resp.json().get("amount_rtc", 0.0)

    def get_nonce(self, address: str) -> int:
        # 假设 API 存在此端点，或从 stats/balance 中获取
        resp = self.client.get(f"/wallet/nonce/{address}")
        if resp.status_code == 404:
            return 0
        resp.raise_for_status()
        return resp.json().get("nonce", 0)

    def signed_transfer(self, to_address: str, amount_rtc: float, identity: Optional[Identity] = None) -> Dict[str, Any]:
        id_to_use = identity or self.identity
        if not id_to_use:
            raise ValueError("Identity required for signed transfer")

        nonce = self.get_nonce(id_to_use.address)
        payload = f"{id_to_use.address}{to_address}{amount_rtc}{nonce}".encode()
        signature = id_to_use.sign(payload)

        data = {
            "from_address": id_to_use.address,
            "to_address": to_address,
            "amount_rtc": amount_rtc,
            "nonce": nonce,
            "signature": signature,
            "public_key": id_to_use.address
        }
        resp = self.client.post("/wallet/transfer/signed", json=data)
        resp.raise_for_status()
        return resp.json()

    def submit_attestation(self, fingerprint: Dict[str, Any], identity: Optional[Identity] = None) -> AttestationResponse:
        id_to_use = identity or self.identity
        if not id_to_use:
            raise ValueError("Identity required for attestation")

        payload = str(fingerprint).encode()
        signature = id_to_use.sign(payload)

        data = {
            "miner_id": id_to_use.address,
            "fingerprint": fingerprint,
            "signature": signature
        }
        resp = self.client.post("/attest/submit", json=data)
        resp.raise_for_status()
        return AttestationResponse(**resp.json())
