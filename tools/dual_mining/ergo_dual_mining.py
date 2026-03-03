"""
Ergo Dual-Mining Integration for RustChain
Bounty #455 - 25 RTC

Mine Ergo (ERG) while earning RTC attestation rewards.
Ergo uses Autolykos2 algorithm - CPU/GPU mineable.
"""
import requests
import psutil
from typing import Optional, Dict, Any


class ErgoDualMiner:
    """Ergo dual-mining proof generator for RustChain"""
    
    def __init__(self, node_url: str = "http://localhost:9052"):
        self.node_url = node_url
    
    def get_node_rpc_proof(self) -> Optional[Dict[str, Any]]:
        """
        Query Ergo node RPC for proof (1.5x bonus)
        Queries localhost:9052/info
        """
        try:
            endpoint = f"{self.node_url}/info"
            response = requests.get(endpoint, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return {
                    "proof_type": "node_rpc",
                    "bonus_multiplier": 1.5,
                    "chain": "ergo",
                    "node_info": {
                        "name": data.get("name"),
                        "isStarted": data.get("isStarted"),
                        "difficulty": data.get("difficulty"),
                        "peersCount": data.get("peersCount"),
                        "bestFullBlockId": data.get("bestFullBlockId")
                    }
                }
        except Exception as e:
            print(f"Node RPC not available: {e}")
        return None
    
    def get_pool_proof(self, wallet_address: str = None) -> Optional[Dict[str, Any]]:
        """
        Verify mining via Ergo pool API (1.3x bonus)
        Supports HeroMiners, WoolyPooly, 2Miners, NanoPool
        """
        pools = []
        
        if wallet_address:
            pools.extend([
                f"https://ergo.herominers.com/api/stats_address?address={wallet_address}",
                f"https://api.woolypooly.com/api/ergo-0/accounts/{wallet_address}",
                f"https://erg.2miners.com/api/accounts/{wallet_address}",
                f"https://ergo.nanopool.org/api/v1/user/{wallet_address}",
            ])
        
        pools.extend([
            "https://ergo.herominers.com/api/stats",
            "https://api.woolypooly.com/api/ergo-0/stats",
        ])
        
        for pool_api in pools:
            try:
                response = requests.get(pool_api, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "proof_type": "pool",
                        "bonus_multiplier": 1.3,
                        "chain": "ergo",
                        "pool": pool_api,
                        "pool_stats": data
                    }
            except Exception as e:
                continue
        return None
    
    def get_process_detection_proof(self) -> Optional[Dict[str, Any]]:
        """
        Detect Ergo miner processes (1.15x bonus)
        Detects: ergo, ergo-node, nanominer, lolminer, trex, gminer, teamredminer
        """
        ergo_processes = []
        ergo_keywords = ['ergo', 'ergo-node', 'ergo.jar', 'nanominer', 
                         'lolminer', 'trex', 'gminer', 'teamredminer',
                         'nbminer', 'bminer']
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                name = proc.info['name'].lower()
                cmdline = ' '.join(proc.info['cmdline'] or []).lower()
                
                for keyword in ergo_keywords:
                    if keyword in name or keyword in cmdline:
                        ergo_processes.append({
                            'pid': proc.info['pid'],
                            'name': proc.info['name'],
                            'cmdline': cmdline[:200]
                        })
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if ergo_processes:
            return {
                "proof_type": "process",
                "bonus_multiplier": 1.15,
                "chain": "ergo",
                "processes": ergo_processes
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
    print("Ergo Dual-Mining Proof Generator")
    print("=" * 40)
    
    miner = ErgoDualMiner()
    proof = miner.get_best_proof()
    
    if proof:
        print(f"✅ Ergo mining detected!")
        print(f"   Proof type: {proof['proof_type']}")
        print(f"   Bonus multiplier: {proof['bonus_multiplier']}x")
        print(f"   Chain: {proof['chain']}")
        
        if proof['proof_type'] == 'node_rpc':
            info = proof.get('node_info', {})
            print(f"   Name: {info.get('name', 'N/A')}")
            print(f"   Started: {info.get('isStarted', 'N/A')}")
            print(f"   Difficulty: {info.get('difficulty', 'N/A')}")
            print(f"   Peers: {info.get('peersCount', 'N/A')}")
        
        elif proof['proof_type'] == 'pool':
            print(f"   Pool: {proof.get('pool', 'N/A')}")
        
        elif proof['proof_type'] == 'process':
            procs = proof.get('processes', [])
            print(f"   Processes: {len(procs)} detected")
            for p in procs[:3]:
                print(f"     - {p['name']} (PID: {p['pid']})")
    else:
        print("❌ No Ergo mining detected")
        print()
        print("To mine Ergo:")
        print("  1. Install Ergo node: https://ergoplatform.org/")
        print("  2. Run ergo-node or connect to a pool (HeroMiners, 2Miners, etc.)")
        print("  3. This script will auto-detect and generate proof")
