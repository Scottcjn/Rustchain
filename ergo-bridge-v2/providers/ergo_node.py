import httpx
import asyncio
import logging
import functools
from typing import List, Dict, Any, Optional

def retry_on_failure(retries: int = 5, backoff_factor: float = 0.5):
    """
    Decorator for retrying async functions with exponential backoff.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for i in range(retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    wait_time = backoff_factor * (2 ** i)
                    logging.warning(f"Retrying {func.__name__} in {wait_time:.2f}s (Attempt {i+1}/{retries}) due to: {e}")
                    await asyncio.sleep(wait_time)
            logging.error(f"Max retries reached for {func.__name__}")
            raise last_exception
        return wrapper
    return decorator

class ErgoNodeClient:
    """
    Async Ergo Node Adapter (Ported from reqwest client in Rust)
    """
    def __init__(self, base_url: str, api_key: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip('/')
        self.headers = {
            "api_key": api_key,
            "Content-Type": "application/json"
        }
        self.timeout = httpx.Timeout(timeout)
    
    @retry_on_failure()
    async def _request(self, method: str, path: str, **kwargs) -> Any:
        """
        Helper method to perform HTTP requests with robust error handling.
        """
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.request(method, url, headers=self.headers, **kwargs)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            raise Exception(f"Ergo Node API error ({e.response.status_code}): {e.response.text}")
        except httpx.RequestError as e:
            logging.error(f"An error occurred while requesting {e.request.url!r}: {e}")
            raise Exception(f"Ergo Node network error: {e}")

    async def get_current_height(self) -> int:
        """
        Get the current height of the blockchain.
        
        Returns:
            int: The height of the last block.
        """
        data = await self._request("GET", "/blocks/lastHeaders/1")
        return data[0]['height']

    async def get_block_header_by_height(self, height: int) -> Dict[str, Any]:
        """
        Get block header at a specific height.
        """
        data = await self._request("GET", f"/blocks/at/{height}")
        # /blocks/at/{height} returns a list of block IDs at that height
        if not data:
            raise Exception(f"No block found at height {height}")
        block_id = data[0]
        return await self._request("GET", f"/blocks/{block_id}/header")

    async def fetch_utxos(self, address: str) -> List[Dict[str, Any]]:
        """
        Get unspent boxes for a given address.
        
        Args:
            address: Ergo address (P2PK or P2S).
            
        Returns:
            List of box objects.
        """
        return await self._request("GET", f"/boxes/unspent/byAddress/{address}")

    async def get_box_by_id(self, box_id: str) -> Dict[str, Any]:
        """
        Get a box by its identifier.
        
        Args:
            box_id: The ID of the box to retrieve.
            
        Returns:
            The box object if found.
            
        Ref: /utxo/byId/{boxId}
        """
        return await self._request("GET", f"/utxo/byId/{box_id}")

    async def get_mempool_txs(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get unconfirmed transactions from the mempool.
        
        Args:
            limit: Maximum number of transactions to return.
            offset: Number of transactions to skip.
            
        Returns:
            List of unconfirmed transaction objects.
            
        Ref: /transactions/unconfirmed
        """
        params = {"limit": limit, "offset": offset}
        return await self._request("GET", "/transactions/unconfirmed", params=params)

    async def sign_transaction_proxy(self, unsigned_tx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sign an unsigned transaction using the node's wallet.
        
        Args:
            unsigned_tx: The unsigned transaction object to sign.
            
        Returns:
            The signed transaction object.
            
        Ref: /wallet/transaction/sign
        """
        return await self._request("POST", "/wallet/transaction/sign", json=unsigned_tx)

    async def broadcast_tx(self, signed_tx: Dict[str, Any]) -> str:
        """
        Broadcast a signed transaction to the network.
        
        Args:
            signed_tx: The signed transaction object.
            
        Returns:
            str: The transaction ID.
            
        Ref: /transactions
        """
        data = await self._request("POST", "/transactions", json=signed_tx)
        return data.get("id")

    async def get_tx_status(self, tx_id: str) -> Dict[str, Any]:
        """
        Get transaction status (mempool or confirmed).
        """
        try:
            # Check mempool
            mempool_tx = await self._request("GET", f"/transactions/unconfirmed/byTransactionId/{tx_id}")
            if mempool_tx:
                return {"status": "InMempool", "confirmations": 0}
        except:
            pass
        
        try:
            # Check blockchain
            tx_info = await self._request("GET", f"/blockchain/transactionById/{tx_id}")
            if tx_info:
                return {"status": "Confirmed", "confirmations": tx_info.get("numConfirmations", 1)}
        except:
            pass

        return {"status": "NotFound"}
