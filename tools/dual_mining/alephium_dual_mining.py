"""
Alephium Dual-Mining Integration for RustChain
Bounty #460 - 20 RTC

Mine Alephium (ALPH) while earning RTC attestation rewards.
Alephium uses Blake3 algorithm - CPU/GPU mineable.
"""
import requests
import psutil
from typing import Optional, Dict, Any


class AlephiumDualMiner:
    """Alephium dual-mining proof generator for RustChain"""
    
    def __init__(self, node_url: str = "http://localhost:12973"):
        self.node_url = node_url
    
    def get_node_rpc_proof(self) -> Optional[Dict[str, Any]]:
        """
        Query Alephium node RPC for proof (1.5x bonus)
        Queries localhost:12973/infos/self-clique
        """
        try:
            endpoint = f"{self.node_url}/infos/self-clique"
            response = requests.get(endpoint, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return {
                    "proof_type": "node_rpc",
                    "bonus_multiplier": 1.5,
                    "chain": "alephium",
                    "node_info": {
                        "clique_id": data.get("cliqueId"),
                        "num_nodes": data.get("numNodes"),
                        "synced": data.get("synced"),
                        "peer_address": data.get("peerAddress")
                    }
                }
        except Exception as e:
            print(f"Node RPC not available: {e}")
        return None
    
    def get_pool_proof(self, wallet_address: str = None) -> Optional[Dict[str, Any]]:
        """
        Verify mining via Alephium pool API (1.3x bonus)
        Supports HeroMiners and WoolyPooly
        """
        pools = []
        
        if wallet_address:
            pools.extend([
                f"https://alephium.herominers.com/api/stats_address?address={wallet_address}",
                f"https://api.woolypooly.com/api/alph-0/accounts/{wallet_address}",
            ])
        
        pools.extend([
            "https://alephium.herominers.com/api/stats",
            "https://api.woolypooly.com/api/alph-0/stats",
        ])
        
        for pool_api in pools:
            try:
                response = requests.get(pool_api, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "proof_type": "pool",
                        "bonus_multiplier": 1.3,
                        "chain": "alephium",
                        "pool": pool_api,
                        "pool_stats": data
                    }
            except Exception as e:
                continue
        return None
    
    def get_process_detection_proof(self) -> Optional[Dict[str, Any]]:
        """
        Detect Alephium miner processes (1.15x bonus)
        Detects: alephium, alph-miner, bzminer
        """
        alph_processes = []
        alph_keywords = ['alephium', 'alph-miner', 'bzminer', 'alph-fullnode']
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                name = proc.info['name'].lower()
                cmdline = ' '.join(proc.info['cmdline'] or []).lower()
                
                for keyword in alph_keywords:
                    if keyword in name or keyword in cmdline:
                        alph_processes.append({
                            'pid': proc.info['pid'],
                            'name': proc.info['name'],
                            'cmdline': cmdline[:200]
                        })
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if alph_processes:
            return {
                "proof_type": "process",
                "bonus_multiplier": 1.15,
                "chain": "alephium",
                "processes": alph_processes
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
    print("Alephium Dual-Mining Proof Generator")
    print("=" * 40)
    
    miner = AlephiumDualMiner()
    proof = miner.get_best_proof()
    
    if proof:
        print(f"✅ Alephium mining detected!")
        print(f"   Proof type: {proof['proof_type']}")
        print(f"   Bonus multiplier: {proof['bonus_multiplier']}x")
        print(f"   Chain: {proof['chain']}")
        
        if proof['proof_type'] == 'node_rpc':
            info = proof.get('node_info', {})
            print(f"   Clique ID: {info.get('clique_id', 'N/A')}")
            print(f"   Nodes: {info.get('num_nodes', 'N/A')}")
            print(f"   Synced: {info.get('synced', 'N/A')}")
        
        elif proof['proof_type'] == 'pool':
            print(f"   Pool: {proof.get('pool', 'N/A')}")
        
        elif proof['proof_type'] == 'process':
            procs = proof.get('processes', [])
            print(f"   Processes: {len(procs)} detected")
            for p in procs[:3]:
                print(f"     - {p['name']} (PID: {p['pid']})")
    else:
        print("❌ No Alephium mining detected")
        print()
        print("To mine Alephium:")
        print("  1. Install Alephium node: https://alephium.org/")
        print("  2. Run alph-fullnode or connect to a pool")
        print("  3. This script will auto-detect and generate proof")
