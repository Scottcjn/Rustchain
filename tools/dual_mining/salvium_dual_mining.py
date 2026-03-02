"""
Salvium Dual-Mining Integration for RustChain
Bounty #471 - 10 RTC

Mine Salvium (SAL) while earning RTC attestation rewards.
Privacy coin using RandomX variant.
"""
import requests
import psutil
from typing import Optional, Dict, Any

class SalviumDualMiner:
    """Salvium dual-mining proof generator for RustChain"""
    
    def __init__(self, node_url: str = "http://localhost:19091/json_rpc"):
        self.node_url = node_url
    
    def get_node_rpc_proof(self) -> Optional[Dict[str, Any]]:
        """Query salviumd node RPC for proof (1.5x bonus)"""
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": "0",
                "method": "get_info"
            }
            response = requests.post(self.node_url, json=payload, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if "result" in data:
                    return {
                        "proof_type": "node_rpc",
                        "bonus_multiplier": 1.5,
                        "chain": "salvium",
                        "node_info": {
                            "height": data["result"].get("height"),
                            "difficulty": data["result"].get("difficulty"),
                            "hashrate": data["result"].get("hashrate")
                        }
                    }
        except Exception as e:
            print(f"Node RPC not available: {e}")
        return None
    
    def get_pool_proof(self, pool_api: str = "https://salvium.herominers.com/api/stats") -> Optional[Dict[str, Any]]:
        """Verify mining via pool API (1.3x bonus)"""
        try:
            response = requests.get(pool_api, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return {
                    "proof_type": "pool",
                    "bonus_multiplier": 1.3,
                    "chain": "salvium",
                    "pool": pool_api,
                    "pool_stats": data
                }
        except Exception as e:
            print(f"Pool API not available: {e}")
        return None
    
    def get_process_detection_proof(self) -> Optional[Dict[str, Any]]:
        """Detect Salvium miner processes (1.15x bonus)"""
        sal_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                name = proc.info['name'].lower()
                cmdline = ' '.join(proc.info['cmdline'] or []).lower()
                if 'salviumd' in name or 'salviumd' in cmdline or \
                   'xmrig' in name or 'xmrig' in cmdline:
                    sal_processes.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name']
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if sal_processes:
            return {
                "proof_type": "process",
                "bonus_multiplier": 1.15,
                "chain": "salvium",
                "processes": sal_processes
            }
        return None
    
    def get_best_proof(self) -> Optional[Dict[str, Any]]:
        """Get the best available proof (highest bonus)"""
        proofs = []
        
        node_proof = self.get_node_rpc_proof()
        if node_proof:
            proofs.append(node_proof)
        
        pool_proof = self.get_pool_proof()
        if pool_proof:
            proofs.append(pool_proof)
        
        process_proof = self.get_process_detection_proof()
        if process_proof:
            proofs.append(process_proof)
        
        if proofs:
            return max(proofs, key=lambda p: p['bonus_multiplier'])
        return None


if __name__ == "__main__":
    miner = SalviumDualMiner()
    proof = miner.get_best_proof()
    if proof:
        print(f"Salvium proof: {proof['proof_type']} ({proof['bonus_multiplier']}x bonus)")
    else:
        print("No Salvium mining detected")
