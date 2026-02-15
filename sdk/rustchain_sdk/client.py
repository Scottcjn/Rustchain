import requests
from typing import List, Optional, Dict, Any
from .models import HealthStatus, EpochInfo, MinerInfo, Balance, TransferResponse, AttestationResponse
from .exceptions import APIError, AuthenticationError, InsufficientBalanceError, VMDetectedError

class RustChainClient:
    """
    Client for interacting with the RustChain node API.
    """
    def __init__(self, base_url: str = "https://50.28.86.131", verify_ssl: bool = False):
        self.base_url = base_url.rstrip('/')
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        
        # Suppress insecure request warnings if verify_ssl is False
        if not verify_ssl:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.request(method, url, verify=self.verify_ssl, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            try:
                error_data = response.json()
                error_code = error_data.get('error')
                detail = error_data.get('detail') or error_data.get('check_failed')
                
                if error_code == 'VM_DETECTED':
                    raise VMDetectedError(f"Attestation failed: {detail}", code=error_code, detail=detail)
                elif error_code == 'INVALID_SIGNATURE':
                    raise AuthenticationError("Invalid signature provided")
                elif error_code == 'INSUFFICIENT_BALANCE':
                    raise InsufficientBalanceError("Insufficient RTC balance for transfer")
                
                raise APIError(f"API Error: {error_code or e}", code=error_code, detail=detail)
            except (ValueError, AttributeError):
                raise APIError(f"HTTP Error: {e}")
        except Exception as e:
            raise APIError(f"Request failed: {e}")

    def health(self) -> HealthStatus:
        """Check node health and version."""
        data = self._request("GET", "/health")
        return HealthStatus(**data)

    def epoch(self) -> EpochInfo:
        """Get current epoch details."""
        data = self._request("GET", "/epoch")
        return EpochInfo(**data)

    def miners(self) -> List[MinerInfo]:
        """List all active/enrolled miners."""
        data = self._request("GET", "/api/miners")
        return [MinerInfo(**item) for item in data]

    def balance(self, miner_id: str) -> Balance:
        """Check RTC balance for a miner."""
        params = {"miner_id": miner_id}
        data = self._request("GET", "/wallet/balance", params=params)
        return Balance(**data)

    def transfer(self, from_id: str, to_id: str, amount_i64: int, nonce: int, signature: str) -> TransferResponse:
        """
        Transfer RTC to another wallet.
        Requires an Ed25519 signature of the transfer payload.
        """
        payload = {
            "from": from_id,
            "to": to_id,
            "amount_i64": amount_i64,
            "nonce": nonce,
            "signature": signature
        }
        data = self._request("POST", "/wallet/transfer/signed", json=payload)
        return TransferResponse(**data)

    def submit_attestation(self, miner_id: str, fingerprint: Dict[str, Any], signature: str) -> AttestationResponse:
        """
        Submit hardware fingerprint for epoch enrollment.
        """
        payload = {
            "miner_id": miner_id,
            "fingerprint": fingerprint,
            "signature": signature
        }
        data = self._request("POST", "/attest/submit", json=payload)
        return AttestationResponse(**data)
