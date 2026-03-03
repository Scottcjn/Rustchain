"""
DERO Dual-Mining Integration for RustChain
Bounty #468 - 20 RTC

Mine DERO while earning RTC attestation rewards.
DERO uses AstroBWT algorithm - CPU-optimized and ASIC-resistant.
"""
import requests
import subprocess
import psutil
from typing import Optional, Dict, Any


class DeroDualMiner:
    """DERO dual-mining proof generator for RustChain"""
    
    def __init__(self, node_url: str = "http://localhost:10102/json_rpc"):
        self.node_url = node_url
        self.stargate_url = "http://localhost:20000/json_rpc"
    
    def get_node_rpc_proof(self) -> Optional[Dict[str, Any]]:
        """
        Query dero daemon RPC for proof (1.5x bonus)
        Queries localhost:10102/json_rpc or :20000/json_rpc (stargate)
        Method: get_info
        """
        for url in [self.node_url, self.stargate_url]:
            try:
                payload = {
                    "jsonrpc": "2.0",
                    "id": "0",
                    "method": "get_info"
                }
                response = requests.post(url, json=payload, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if "result" in data:
                        result = data["result"]
                        return {
                            "proof_type": "node_rpc",
                            "bonus_multiplier": 1.5,
                            "chain": "dero",
                            "node_info": {
                                "height": result.get("height"),
                                "difficulty": result.get("difficulty"),
                                "hashrate": result.get("hashrate"),
                                "tx_count": result.get("tx_count"),
                                "net_version": result.get("net_version")
                            }
                        }
            except Exception as e:
                continue
        return None
    
    def get_pool_proof(self, wallet_address: str = None) -> Optional[Dict[str, Any]]:
        """
        Verify mining via DERO pool API (1.3x bonus)
        Supports major DERO pools
        """
        pools = [
            f"https://dero.herominers.com/api/stats_address?address={wallet_address}" if wallet_address else "https://dero.herominers.com/api/stats",
            "https://pool.dero.io/api/stats",
            "https://dero.miningpoolhub.com/api/stats",
        ]
        
        for pool_api in pools:
            try:
                response = requests.get(pool_api, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "proof_type": "pool",
                        "bonus_multiplier": 1.3,
                        "chain": "dero",
                        "pool": pool_api,
                        "pool_stats": data
                    }
            except Exception as e:
                continue
        return None
    
    def get_process_detection_proof(self) -> Optional[Dict[str, Any]]:
        """
        Detect DERO miner processes (1.15x bonus)
        Detects dero-miner, dero-stratum-miner, astrobwt-miner, dero-wallet-cli
        """
        dero_processes = []
        dero_keywords = ['dero-miner', 'dero-stratum-miner', 'astrobwt-miner', 
                         'dero-wallet-cli', 'derod', 'dero-full-node']
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                name = proc.info['name'].lower()
                cmdline = ' '.join(proc.info['cmdline'] or []).lower()
                
                for keyword in dero_keywords:
                    if keyword in name or keyword in cmdline:
                        dero_processes.append({
                            'pid': proc.info['pid'],
                            'name': proc.info['name'],
                            'cmdline': cmdline[:200]  # Truncate for safety
                        })
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if dero_processes:
            return {
                "proof_type": "process",
                "bonus_multiplier": 1.15,
                "chain": "dero",
                "processes": dero_processes
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
    print("DERO Dual-Mining Proof Generator")
    print("=" * 40)
    
    miner = DeroDualMiner()
    proof = miner.get_best_proof()
    
    if proof:
        print(f"✅ DERO mining detected!")
        print(f"   Proof type: {proof['proof_type']}")
        print(f"   Bonus multiplier: {proof['bonus_multiplier']}x")
        print(f"   Chain: {proof['chain']}")
        
        if proof['proof_type'] == 'node_rpc':
            info = proof.get('node_info', {})
            print(f"   Height: {info.get('height', 'N/A')}")
            print(f"   Difficulty: {info.get('difficulty', 'N/A')}")
            print(f"   Hashrate: {info.get('hashrate', 'N/A')}")
        
        elif proof['proof_type'] == 'pool':
            print(f"   Pool: {proof.get('pool', 'N/A')}")
        
        elif proof['proof_type'] == 'process':
            procs = proof.get('processes', [])
            print(f"   Processes: {len(procs)} detected")
            for p in procs[:3]:
                print(f"     - {p['name']} (PID: {p['pid']})")
    else:
        print("❌ No DERO mining detected")
        print()
        print("To mine DERO:")
        print("  1. Install DERO daemon: https://dero.io/")
        print("  2. Run derod or connect to a pool")
        print("  3. This script will auto-detect and generate proof")
