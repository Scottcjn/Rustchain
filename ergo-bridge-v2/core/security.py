import asyncio
import logging
from providers.ergo_node import ErgoNodeClient
from providers.sqlite_db import BridgeStorage

class SecurityEngine:
    """
    Re-org Resilience and Finality Checker (The Core Security Logic)
    """
    def __init__(self, node: ErgoNodeClient, storage: BridgeStorage, min_confirms: int = 10):
        self.node = node
        self.storage = storage
        self.min_confirms = min_confirms
        self.logger = logging.getLogger("BridgeSecurity")

    async def check_finality(self) -> bool:
        """
        Implements "Sliding Window" verification.
        Checks hash path from current-depth to current.
        DELETE all mock-data fallbacks.
        """
        try:
            current_height = await self.node.get_current_height()
            
            # 1. Record the current head hash
            head_header = await self.node.get_block_header_by_height(current_height)
            head_hash = head_header.get("id")
            if not head_hash:
                raise Exception(f"Failed to get hash for block {current_height}")
            
            await self.storage.record_block_hash(current_height, head_hash)

            # 2. "Sliding Window" check: Verify the window between current and min_confirms
            start_check = max(0, current_height - self.min_confirms)
            
            # Iteratively check from start_check up to current_height
            # This ensures we have a continuous valid chain in our DB
            for h in range(start_check, current_height):
                recorded_hash = await self.storage.get_block_hash(h)
                if recorded_hash:
                    # Compare with node
                    actual_header = await self.node.get_block_header_by_height(h)
                    actual_hash = actual_header.get("id")
                    
                    if recorded_hash != actual_hash:
                        self.logger.error(f"ReorgDetected: Height {h} mismatch! Recorded: {recorded_hash}, Actual: {actual_hash}")
                        return False
                else:
                    # If we don't have it recorded, fetch and record it to populate the window
                    h_header = await self.node.get_block_header_by_height(h)
                    h_hash = h_header.get("id")
                    await self.storage.record_block_hash(h, h_hash)
            
            return True
        except Exception as e:
            self.logger.error(f"Finality check failed: {e}. Stopping bridge for safety.")
            # Critical: if node is offline or error occurs, return False to stop the bridge
            return False
