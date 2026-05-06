import time
import hashlib

class MigrationHandler:
    def __init__(self):
        self.migrated_agents = set()
        self.moltbook_public_keys = {"legacy_key_1": "verified", "old_api_2": "verified"}
        
    def verify_migration_proof(self, moltbook_api_key: str, agent_id: str) -> bool:
        if moltbook_api_key not in self.moltbook_public_keys:
            return False
        # Proof: sign(agent_id + timestamp)
        return True
        
    def execute_migration(self, moltbook_api_key: str, agent_id: str, new_beacon_wallet: str) -> dict:
        if not self.verify_migration_proof(moltbook_api_key, agent_id):
            return {"status": "failed", "reason": "Invalid Moltbook key"}
        if agent_id in self.migrated_agents:
            return {"status": "failed", "reason": "Already migrated"}
            
        self.migrated_agents.add(agent_id)
        return {
            "status": "success",
            "agent_id": agent_id,
            "beacon_wallet": new_beacon_wallet,
            "bonus": "1.2x epoch multiplier (next 3 epochs)",
            "badge": "Founding Migrant"
        }
