import asyncio
import logging
import hashlib
import random
from providers.ergo_node import ErgoNodeClient
from providers.sqlite_db import BridgeStorage
from core.security import SecurityEngine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("RustchainBridge")

class ErgoBridgeService:
    """
    Main entry point for the bridge service.
    """
    def __init__(self, config: dict):
        self.node = ErgoNodeClient(config['node_url'], config['api_key'])
        self.storage = BridgeStorage(config['db_path'])
        self.security = SecurityEngine(self.node, self.storage)

    def generate_deterministic_id(self, source_tx: str, index: int) -> str:
        """
        Eliminate random UUIDs. Use hash of source event data.
        """
        payload = f"{source_tx}_{index}".encode()
        return hashlib.sha256(payload).hexdigest()

    async def scan_rustchain(self):
        """
        Simulates discovering new bridge requests from the source chain (Rustchain).
        Uses deterministic IDs.
        """
        if random.random() > 0.7:
            # Simulated source event data
            source_tx = f"rust-tx-{random.randint(1000, 9999)}"
            index = 0
            req_id = self.generate_deterministic_id(source_tx, index)
            
            user = "9f75...user"
            target = "9h42...target"
            amount = random.randint(100, 1000)
            
            await self.storage.add_bridge_request(req_id, user, target, amount)
            logger.info(f"Scanned new bridge request: {req_id} for {amount} nanoERG")

    async def recover_stale_broadcasts(self):
        """
        State-recovery mechanism:
        If a crash occurred after broadcast but before DB update, recover status.
        """
        broadcasting = await self.storage.get_broadcasting_requests()
        for req in broadcasting:
            req_id = req['id']
            ergo_tx_id = req.get('ergo_tx_id')
            
            if not ergo_tx_id:
                # If we don't even have the TX ID, we might need to re-broadcast or check mempool
                # For this logic, we assume the TX ID should be stored or we check status
                logger.warning(f"Request {req_id} stuck in Broadcasting without TX ID.")
                # Logic to recover TX ID or reset to Pending could go here
                continue

            status_info = await self.node.get_tx_status(ergo_tx_id)
            if status_info['status'] in ['InMempool', 'Confirmed']:
                logger.info(f"Recovered {req_id}: TX {ergo_tx_id} found on node. Marking Completed.")
                await self.storage.update_request_status(req_id, 'Completed', ergo_tx_id)
            elif status_info['status'] == 'NotFound':
                logger.warning(f"Recovered {req_id}: TX {ergo_tx_id} NOT found. Resetting to Pending.")
                await self.storage.update_request_status(req_id, 'Pending')

    async def process_approved_requests(self):
        """
        Ensures atomic transition from Broadcasting to Completed.
        """
        pending = await self.storage.get_pending_requests()
        
        if not pending:
            return

        logger.info(f"Processing {len(pending)} pending requests...")
        
        for req in pending:
            req_id = req['id']
            try:
                # Step 1: Pre-calculate the deterministic Ergo TX ID
                # In a real system, this would be derived from the signed transaction
                ergo_tx_id = f"ergo-tx-{hashlib.md5(req_id.encode()).hexdigest()}"

                # Step 2: Transition to Broadcasting with the TX ID (Atomic state update)
                # This ensures that if we crash after this, recover_stale_broadcasts can check the TX status
                await self.storage.update_request_status(req_id, 'Broadcasting', ergo_tx_id)
                logger.info(f"Request {req_id}: Status -> Broadcasting (TX: {ergo_tx_id})")

                # Step 3: Broadcast to Ergo
                # Mocking network delay / broadcast
                await asyncio.sleep(1)
                
                # Note: In a real impl, we'd call await self.node.broadcast_tx(signed_tx)
                # If the broadcast succeeds, we move to Completed.
                # If it fails, the retry/recovery logic will handle it.

                # Step 4: Transition to Completed (Atomic state update)
                await self.storage.update_request_status(req_id, 'Completed', ergo_tx_id)
                logger.info(f"Request {req_id}: Status -> Completed (Ergo TX: {ergo_tx_id})")

            except Exception as e:
                logger.error(f"Failed to process request {req_id}: {e}")
                # Transition back to Pending for retry
                await self.storage.update_request_status(req_id, 'Pending')

    async def run_loop(self):
        logger.info("Bridge Watcher Service (Python) Reworked started.")
        while True:
            try:
                # 1. Security Check (Sliding Window)
                if not await self.security.check_finality():
                    logger.warning("Safety check failed or node offline. Suspending bridge operations.")
                    await asyncio.sleep(60)
                    continue

                # 2. Recovery
                await self.recover_stale_broadcasts()

                # 3. Scanning
                await self.scan_rustchain()

                # 4. Processing
                await self.process_approved_requests()
                
                await asyncio.sleep(10)
            except Exception as e:
                logger.error(f"Loop error: {e}")
                await asyncio.sleep(10)

if __name__ == "__main__":
    import os
    db_path = "D:/code/rustchain-refactor-python/rustchain_v2.db"
    
    config = {
        "node_url": "http://localhost:9053",
        "api_key": "BE7YM1fYWrMQ9tSmxAc9jzLNw42nEXTX",
        "db_path": db_path
    }
    bridge = ErgoBridgeService(config)
    asyncio.run(bridge.run_loop())
