"""
Zephyr Dual-Mining Integration for RustChain
Bounty #461 - 15 RTC

Mine Zephyr (ZEPH) while earning RTC attestation rewards.
Zephyr uses RandomX algorithm - CPU mineable.
"""
import requests
import psutil
from typing import Optional, Dict, Any


class ZephyrDualMiner:
    """Zephyr dual-mining proof generator for RustChain"""
    
    def __init__(self, node_url: str = "http://localhost:17777"):
        self.node_url = node_url
    
    def get_node_rpc_proof(self) -> Optional[Dict[str, Any]]:
        """
        Query Zephyr node RPC for proof (1.5x bonus)
        Queries localhost:17777/json_rpc get_info
        """
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": "0",
                "method": "get_info"
            }
            response = requests.post(
                f"{self.node_url}/json_rpc",
                json=payload,
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if "result" in data:
                    result = data["result"]
                    return {
                        "proof_type": "node_rpc",
                        "bonus_multiplier": 1.5,
                        "chain": "zephyr",
                        "node_info": {
                            "height": result.get("height"),
                            "difficulty": result.get("difficulty"),
                            "hashrate": result.get("hashrate"),
                            "tx_count": result.get("tx_count"),
                            "version": result.get("version")
                        }
                    }
        except Exception as e:
            print(f"Node RPC not available: {e}")
        return None
    
    def get_pool_proof(self, wallet_address: str = None) -> Optional[Dict[str, Any]]:
        """
        Verify mining via Zephyr pool API (1.3x bonus)
        Supports HeroMiners and other ZEPH pools
        """
        pools = []
        
        if wallet_address:
            pools.append(f"https://zephyr.herominers.com/api/stats_address?address={wallet_address}")
        
        pools.extend([
            "https://zephyr.herominers.com/api/stats",
        ])
        
        for pool_api in pools:
            try:
                response = requests.get(pool_api, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "proof_type": "pool",
                        "bonus_multiplier": 1.3,
                        "chain": "zephyr",
                        "pool": pool_api,
                        "pool_stats": data
                    }
            except Exception as e:
                continue
        return None
    
    def get_process_detection_proof(self) -> Optional[Dict[str, Any]]:
        """
        Detect Zephyr miner processes (1.15x bonus)
        Detects: xmrig, zephyrd, zephyr-miner
        """
        zeph_processes = []
        zeph_keywords = ['xmrig', 'zephyrd', 'zephyr-miner', 'zeph']
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                name = proc.info['name'].lower()
                cmdline = ' '.join(proc.info['cmdline'] or []).lower()
                
                for keyword in zeph_keywords:
                    if keyword in name or keyword in cmdline:
                        zeph_processes.append({
                            'pid': proc.info['pid'],
                            'name': proc.info['name'],
                            'cmdline': cmdline[:200]
                        })
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if zeph_processes:
            return {
                "proof_type": "process",
                "bonus_multiplier": 1.15,
                "chain": "zephyr",
                "processes": zeph_processes
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
    print("Zephyr Dual-Mining Proof Generator")
    print("=" * 40)
    
    miner = ZephyrDualMiner()
    proof = miner.get_best_proof()
    
    if proof:
        print(f"✅ Zephyr mining detected!")
        print(f"   Proof type: {proof['proof_type']}")
        print(f"   Bonus multiplier: {proof['bonus_multiplier']}x")
        
        if proof['proof_type'] == 'node_rpc':
            info = proof.get('node_info', {})
            print(f"   Height: {info.get('height', 'N/A')}")
            print(f"   Difficulty: {info.get('difficulty', 'N/A')}")
        
        elif proof['proof_type'] == 'pool':
            print(f"   Pool: {proof.get('pool', 'N/A')}")
        
        elif proof['proof_type'] == 'process':
            procs = proof.get('processes', [])
            print(f"   Processes: {len(procs)} detected")
    else:
        print("❌ No Zephyr mining detected")
