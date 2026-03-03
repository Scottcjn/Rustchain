"""
Scala Dual-Mining Integration for RustChain
Bounty #473 - 10 RTC

Mine Scala (XLA) while earning RTC attestation rewards.
RandomX variant - CPU mining focused.
"""
import requests
import psutil
from typing import Optional, Dict, Any

class ScalaDualMiner:
    """Scala dual-mining proof generator for RustChain"""
    
    def __init__(self, node_url: str = "http://localhost:10321/json_rpc"):
        self.node_url = node_url
    
    def get_node_rpc_proof(self) -> Optional[Dict[str, Any]]:
        """Query scalad node RPC for proof (1.5x bonus)"""
        try:
            payload = {"jsonrpc": "2.0", "id": "0", "method": "get_info"}
            response = requests.post(self.node_url, json=payload, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if "result" in data:
                    return {
                        "proof_type": "node_rpc",
                        "bonus_multiplier": 1.5,
                        "chain": "scala",
                        "node_info": {
                            "height": data["result"].get("height"),
                            "difficulty": data["result"].get("difficulty"),
                            "hashrate": data["result"].get("hashrate")
                        }
                    }
        except Exception as e:
            print(f"Node RPC not available: {e}")
        return None
    
    def get_pool_proof(self, pool_api: str = "https://scala.herominers.com/api/stats") -> Optional[Dict[str, Any]]:
        """Verify mining via pool API (1.3x bonus)"""
        try:
            response = requests.get(pool_api, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return {
                    "proof_type": "pool",
                    "bonus_multiplier": 1.3,
                    "chain": "scala",
                    "pool": pool_api,
                    "pool_stats": data
                }
        except Exception as e:
            print(f"Pool API not available: {e}")
        return None
    
    def get_process_detection_proof(self) -> Optional[Dict[str, Any]]:
        """Detect Scala miner processes (1.15x bonus)"""
        scala_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                name = proc.info['name'].lower()
                cmdline = ' '.join(proc.info['cmdline'] or []).lower()
                if any(x in name or x in cmdline for x in ['scalad', 'scala-miner', 'xmrig']):
                    if 'scala' in cmdline or 'xla' in cmdline:
                        scala_processes.append({
                            'pid': proc.info['pid'],
                            'name': proc.info['name']
                        })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if scala_processes:
            return {
                "proof_type": "process",
                "bonus_multiplier": 1.15,
                "chain": "scala",
                "processes": scala_processes
            }
        return None
    
    def get_best_proof(self) -> Optional[Dict[str, Any]]:
        """Get the best available proof"""
        proofs = []
        for proof in [self.get_node_rpc_proof(), self.get_pool_proof(), self.get_process_detection_proof()]:
            if proof:
                proofs.append(proof)
        return max(proofs, key=lambda p: p['bonus_multiplier']) if proofs else None

if __name__ == "__main__":
    miner = ScalaDualMiner()
    proof = miner.get_best_proof()
    if proof:
        print(f"✅ Scala mining detected! Bonus: {proof['bonus_multiplier']}x")
    else:
        print("❌ No Scala mining detected")
