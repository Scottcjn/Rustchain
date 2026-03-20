# SPDX-License-Identifier: MIT

import json
import requests
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class NeoxaRPCClient:
    """RPC client for communicating with neoxad daemon"""

    def __init__(self, host='localhost', port=8788, username='', password='', timeout=30):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout
        self.url = f"http://{host}:{port}"

    def _make_request(self, method: str, params: list = None) -> Optional[Dict[str, Any]]:
        """Make RPC request to neoxad"""
        payload = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': method,
            'params': params or []
        }

        try:
            response = requests.post(
                self.url,
                json=payload,
                auth=(self.username, self.password) if self.username else None,
                timeout=self.timeout,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()

            data = response.json()
            if 'error' in data and data['error']:
                logger.error(f"Neoxa RPC error: {data['error']}")
                return None

            return data.get('result')

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to neoxad: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from neoxad: {e}")
            return None

    def get_info(self) -> Optional[Dict[str, Any]]:
        """Get basic node information"""
        return self._make_request('getinfo')

    def get_blockchain_info(self) -> Optional[Dict[str, Any]]:
        """Get blockchain information"""
        return self._make_request('getblockchaininfo')

    def get_network_info(self) -> Optional[Dict[str, Any]]:
        """Get network information"""
        return self._make_request('getnetworkinfo')

    def get_mining_info(self) -> Optional[Dict[str, Any]]:
        """Get mining information"""
        return self._make_request('getmininginfo')

    def get_block_count(self) -> Optional[int]:
        """Get current block height"""
        result = self._make_request('getblockcount')
        return result if result is not None else None

    def get_connection_count(self) -> Optional[int]:
        """Get number of peer connections"""
        result = self._make_request('getconnectioncount')
        return result if result is not None else None

    def get_difficulty(self) -> Optional[float]:
        """Get current network difficulty"""
        result = self._make_request('getdifficulty')
        return result if result is not None else None

    def get_hashrate(self) -> Optional[float]:
        """Get estimated network hashrate"""
        result = self._make_request('getnetworkhashps')
        return result if result is not None else None

    def is_connected(self) -> bool:
        """Check if node is reachable and synced"""
        try:
            info = self.get_info()
            if not info:
                return False

            # Check if node is reasonably synced
            block_count = info.get('blocks', 0)
            return block_count > 0

        except Exception:
            return False

    def get_wallet_info(self) -> Optional[Dict[str, Any]]:
        """Get wallet information if available"""
        return self._make_request('getwalletinfo')

    def get_balance(self) -> Optional[float]:
        """Get wallet balance"""
        result = self._make_request('getbalance')
        return result if result is not None else None

# Singleton instance
neoxa_client = NeoxaRPCClient()

def test_neoxa_connection():
    """Test connection to neoxad"""
    print("Testing Neoxa RPC connection...")

    if not neoxa_client.is_connected():
        print("❌ Cannot connect to neoxad at localhost:8788")
        return False

    info = neoxa_client.get_info()
    if info:
        print(f"✅ Connected to Neoxa node")
        print(f"   Version: {info.get('version', 'Unknown')}")
        print(f"   Blocks: {info.get('blocks', 0)}")
        print(f"   Connections: {info.get('connections', 0)}")
        return True

    return False

if __name__ == "__main__":
    test_neoxa_connection()
