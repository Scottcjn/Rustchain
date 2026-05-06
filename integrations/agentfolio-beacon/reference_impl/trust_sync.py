import hashlib
import time
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class AgentTrustRecord:
    agent_id: str
    beacon_wallet: str
    on_chain_score: float  # 0.0 - 1.0
    off_chain_score: float # 0.0 - 1.0
    
    @property
    def dual_layer_score(self) -> float:
        return round(0.6 * self.on_chain_score + 0.4 * self.off_chain_score, 4)
        
    @property
    def trust_hash(self) -> str:
        h = hashlib.sha256(f"{self.agent_id}{self.dual_layer_score}{int(time.time()) // 86400}".encode()).hexdigest()
        return h

class TrustSyncEngine:
    def __init__(self):
        self.records: Dict[str, AgentTrustRecord] = {}
        
    def sync_agent(self, agent_id: str, beacon_wallet: str, on_chain: float, off_chain: float) -> AgentTrustRecord:
        record = AgentTrustRecord(agent_id, beacon_wallet, on_chain, off_chain)
        self.records[agent_id] = record
        return record
        
    def get_trust(self, agent_id: str) -> Optional[AgentTrustRecord]:
        return self.records.get(agent_id)
        
    def batch_sync(self, agents: list) -> list:
        return [self.sync_agent(**a) for a in agents]
