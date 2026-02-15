"""
RustChain Python SDK
Zero-dependency Python client for RustChain blockchain
"""

import requests
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime


__version__ = "0.1.0"
__author__ = "AI Bounty Hunter"


@dataclass
class NodeInfo:
    """Node information"""
    status: str
    timestamp: str
    
    def to_dict(self) -> Dict:
        return {
            'status': self.status,
            'timestamp': self.timestamp
        }


@dataclass
class Epoch:
    """Epoch information"""
    epoch_number: int
    start_time: str
    end_time: str
    total_attestations: int
    
    def to_dict(self) -> Dict:
        return {
            'epoch_number': self.epoch_number,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'total_attestations': self.total_attestations
        }


@dataclass
class Miner:
    """Miner information"""
    miner_id: str
    device_arch: str
    device_family: str
    antiquity_multiplier: float
    last_attest: int
    epochs_active: int
    
    def to_dict(self) -> Dict:
        return {
            'miner_id': self.miner_id,
            'device_arch': self.device_arch,
            'device_family': self.device_family,
            'antiquity_multiplier': self.antiquity_multiplier,
            'last_attest': self.last_attest,
            'epochs_active': self.epochs_active
        }


@dataclass
class WalletBalance:
    """Wallet balance information"""
    miner_id: str
    balance: float
    last_updated: str
    
    def to_dict(self) -> Dict:
        return {
            'miner_id': self.miner_id,
            'balance': self.balance,
            'last_updated': self.last_updated
        }


class RustChainClient:
    """
    Python client for RustChain blockchain
    
    Args:
        base_url: Base URL of RustChain node (default: https://50.28.86.131)
        verify_ssl: Whether to verify SSL certificates (default: False)
        timeout: Request timeout in seconds (default: 30)
    """
    
    def __init__(
        self,
        base_url: str = "https://50.28.86.131",
        verify_ssl: bool = False,
        timeout: int = 30
    ):
        self.base_url = base_url.rstrip('/')
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        
        self._session = requests.Session()
        self._session.verify = verify_ssl
        self._session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': f'rustchain-sdk/{__version__}'
        })
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make HTTP request to RustChain API"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        response = self._session.request(
            method=method,
            url=url,
            timeout=self.timeout,
            **kwargs
        )
        response.raise_for_status()
        
        return response.json() if response.text else {}
    
    # ============== Node Info ==============
    
    def health(self) -> NodeInfo:
        """Get node health status"""
        data = self._request('GET', '/health')
        return NodeInfo(
            status=data.get('status', 'unknown'),
            timestamp=data.get('timestamp', '')
        )
    
    def get_epoch(self) -> Epoch:
        """Get current epoch information"""
        data = self._request('GET', '/epoch')
        return Epoch(
            epoch_number=data.get('epoch', 0),
            start_time=data.get('start_time', ''),
            end_time=data.get('end_time', ''),
            total_attestations=data.get('total_attestations', 0)
        )
    
    def ready(self) -> Dict:
        """Check if node is ready"""
        return self._request('GET', '/ready')
    
    # ============== Miners ==============
    
    def get_miners(self) -> List[Miner]:
        """Get list of active miners"""
        data = self._request('GET', '/api/miners')
        
        miners = []
        for item in data if isinstance(data, list) else []:
            miners.append(Miner(
                miner_id=item.get('miner', ''),
                device_arch=item.get('device_arch', ''),
                device_family=item.get('device_family', ''),
                antiquity_multiplier=item.get('antiquity_multiplier', 1.0),
                last_attest=item.get('last_attest', 0),
                epochs_active=item.get('epochs_active', 0)
            ))
        
        return miners
    
    def get_miner(self, miner_id: str) -> Optional[Miner]:
        """Get specific miner information"""
        miners = self.get_miners()
        for miner in miners:
            if miner.miner_id == miner_id:
                return miner
        return None
    
    # ============== Wallet ==============
    
    def get_balance(self, miner_id: str) -> WalletBalance:
        """Get wallet balance"""
        data = self._request('GET', f'/wallet/balance?miner_id={miner_id}')
        return WalletBalance(
            miner_id=miner_id,
            balance=float(data.get('balance', 0)),
            last_updated=datetime.now().isoformat()
        )
    
    def transfer(
        self,
        from_address: str,
        to_address: str,
        amount: float,
        private_key: str
    ) -> Dict:
        """
        Transfer RTC tokens
        
        Args:
            from_address: Sender wallet address
            to_address: Recipient wallet address
            amount: Amount to transfer
            private_key: Private key for signing
        
        Returns:
            Transaction receipt
        """
        data = {
            'from': from_address,
            'to': to_address,
            'amount': amount
        }
        
        return self._request('POST', '/wallet/transfer/signed', json=data)
    
    def get_transaction(self, tx_hash: str) -> Dict:
        """Get transaction details"""
        return self._request('GET', f'/wallet/transaction/{tx_hash}')
    
    # ============== Attestation ==============
    
    def submit_attestation(self, payload: Dict) -> Dict:
        """Submit attestation proof"""
        return self._request('POST', '/attest/submit', json=payload)
    
    def get_attestation(self, attestation_id: str) -> Dict:
        """Get attestation details"""
        return self._request('GET', f'/attest/{attestation_id}')
    
    # ============== Utilities ==============
    
    def ping(self) -> bool:
        """Check if node is reachable"""
        try:
            self.health()
            return True
        except Exception:
            return False
    
    def __repr__(self) -> str:
        return f"<RustChainClient(base_url='{self.base_url}')>"


# Convenience function
def create_client(**kwargs) -> RustChainClient:
    """Create a new RustChain client"""
    return RustChainClient(**kwargs)


__all__ = [
    'RustChainClient',
    'create_client',
    'NodeInfo',
    'Epoch',
    'Miner',
    'WalletBalance'
]
