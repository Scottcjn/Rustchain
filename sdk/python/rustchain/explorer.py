"""
RustChain Explorer API Client
Provides access to block explorer and transaction data.
"""

import re
import ssl
import json
import time
import urllib.request
from typing import Any, Dict, List, Optional


class ExplorerClient:
    """
    RustChain Block Explorer API Client
    
    Access via RustChainClient.explorer or create standalone:
    
    >>> from rustchain.explorer import ExplorerClient
    >>> explorer = ExplorerClient("https://50.28.86.131")
    >>> blocks = explorer.blocks(limit=10)
    >>> txs = explorer.transactions(limit=5)
    """
    
    def __init__(
        self,
        base_url: str = "https://50.28.86.131",
        verify_ssl: bool = False,
        timeout: int = 30
    ):
        self.base_url = base_url.rstrip("/")
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        
        if not verify_ssl:
            self._ctx = ssl.create_default_context()
            self._ctx.check_hostname = False
            self._ctx.verify_mode = ssl.CERT_NONE
        else:
            self._ctx = None
    
    def _get(self, endpoint: str) -> Any:
        """Make GET request"""
        url = f"{self.base_url}{endpoint}"
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, context=self._ctx, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            raise ExplorerError(f"Request to {endpoint} failed: {e}")
    
    def blocks(self, limit: int = 20) -> Dict[str, Any]:
        """
        Get recent blocks from the RustChain network.
        
        Args:
            limit: Maximum number of blocks to return (default: 20)
        
        Returns:
            Dict with 'blocks' list and 'count' integer.
            Each block has: block_hash, block_index, miner, slot, 
            timestamp, previous_hash, signature, transactions.
        
        Example:
            >>> explorer.blocks(limit=5)
            {'blocks': [{'block_hash': '...', 'slot': 35, ...}, ...], 'count': 5}
        """
        data = self._get("/p2p/blocks")
        blocks = data.get("blocks", [])
        return {
            "blocks": blocks[:limit],
            "count": min(len(blocks), limit)
        }
    
    def transactions(self, limit: int = 20) -> Dict[str, Any]:
        """
        Get recent transactions from RustChain blocks.
        
        Note: RustChain uses a proof-of-antiquity consensus where 
        most "transactions" are miner messages. True token transfers
        use the /wallet/transfer endpoints.
        
        Args:
            limit: Maximum number of transactions to return
        
        Returns:
            Dict with 'transactions' list and 'count'.
        """
        data = self._get("/p2p/blocks")
        blocks = data.get("blocks", [])
        
        all_txs = []
        for block in blocks:
            txs = block.get("transactions", [])
            for tx in txs:
                tx["block_hash"] = block.get("block_hash")
                tx["block_slot"] = block.get("slot")
                all_txs.append(tx)
        
        return {
            "transactions": all_txs[:limit],
            "count": min(len(all_txs), limit)
        }
    
    def chain_tip(self) -> Dict[str, Any]:
        """
        Get the current chain tip (latest block header).
        
        Returns:
            Dict with miner, slot, signature_prefix, tip_age.
        
        Example:
            >>> explorer.chain_tip()
            {'miner': 'sophia-nas-c4130', 'slot': 2941199, ...}
        """
        return self._get("/headers/tip")
    
    def beacon_envelopes(self, limit: int = 50) -> Dict[str, Any]:
        """
        Get beacon envelopes (attestation records).
        
        Args:
            limit: Maximum number of envelopes
        
        Returns:
            Dict with 'envelopes' list and 'count'.
        """
        data = self._get("/beacon/envelopes")
        envelopes = data.get("envelopes", [])
        return {
            "envelopes": envelopes[:limit],
            "count": data.get("count", len(envelopes))
        }


class ExplorerError(Exception):
    """Exception for Explorer API errors"""
    pass
