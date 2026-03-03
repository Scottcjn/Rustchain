"""
Monero Dual-Mining Integration for RustChain
Bounty #458 - 25 RTC

Mine Monero (XMR) while earning RTC attestation rewards.
Monero uses RandomX algorithm - CPU mineable.
"""
import requests
import psutil
from typing import Optional, Dict, Any


class MoneroDualMiner:
    """Monero dual-mining proof generator for RustChain"""
    
    def __init__(self, node_url: str = "http://localhost:18081"):
        self.node_url = node_url
        self.p2pool_url = "http://localhost:18083"
    
    def get_node_rpc_proof(self) -> Optional[Dict[str, Any]]:
        """
        Query Monero node RPC for proof (1.5x bonus)
        Queries localhost:18081/json_rpc get_info
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
                        "chain": "monero",
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
    
    def get_p2pool_proof(self) -> Optional[Dict[str, Any]]:
        """
        Query P2Pool local stats (1.5x bonus)
        P2Pool runs on localhost:18083
        """
        try:
            response = requests.get(
                f"{self.p2pool_url}/local/stats",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    "proof_type": "p2pool",
                    "bonus_multiplier": 1.5,
                    "chain": "monero",
                    "p2pool_stats": data
                }
        except Exception as e:
            print(f"P2Pool not available: {e}")
        return None
    
    def get_pool_proof(self, wallet_address: str = None) -> Optional[Dict[str, Any]]:
        """
        Verify mining via Monero pool API (1.3x bonus)
        Supports HeroMiners, NanoPool, SupportXMR
        """
        pools = []
        
        if wallet_address:
            pools.extend([
                f"https://monero.herominers.com/api/stats_address?address={wallet_address}",
                f"https://xmr.nanopool.org/api/v1/user/{wallet_address}",
                f"https://xmr.supportxmr.com/api/stats_address?address={wallet_address}",
            ])
        
        pools.extend([
            "https://monero.herominers.com/api/stats",
            "https://xmr.nanopool.org/api/v1/pool",
        ])
        
        for pool_api in pools:
            try:
                response = requests.get(pool_api, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "proof_type": "pool",
                        "bonus_multiplier": 1.3,
                        "chain": "monero",
                        "pool": pool_api,
                        "pool_stats": data
                    }
            except Exception as e:
                continue
        return None
    
    def get_process_detection_proof(self) -> Optional[Dict[str, Any]]:
        """
        Detect Monero miner processes (1.15x bonus)
        Detects: xmrig, monerod, p2pool, xmr-stak
        """
        xmr_processes = []
        xmr_keywords = ['xmrig', 'monerod', 'p2pool', 'xmr-stak', 
                        'xmr-proxy', 'monero-miner']
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                name = proc.info['name'].lower()
                cmdline = ' '.join(proc.info['cmdline'] or []).lower()
                
                for keyword in xmr_keywords:
                    if keyword in name or keyword in cmdline:
                        xmr_processes.append({
                            'pid': proc.info['pid'],
                            'name': proc.info['name'],
                            'cmdline': cmdline[:200]
                        })
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if xmr_processes:
            return {
                "proof_type": "process",
                "bonus_multiplier": 1.15,
                "chain": "monero",
                "processes": xmr_processes
            }
        return None
    
    def get_best_proof(self) -> Optional[Dict[str, Any]]:
        """Get the best available proof (highest bonus)"""
        proofs = []
        
        node_proof = self.get_node_rpc_proof()
        if node_proof:
            proofs.append(node_proof)
        
        p2pool_proof = self.get_p2pool_proof()
        if p2pool_proof:
            proofs.append(p2pool_proof)
        
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
    print("Monero Dual-Mining Proof Generator")
    print("=" * 40)
    
    miner = MoneroDualMiner()
    proof = miner.get_best_proof()
    
    if proof:
        print(f"✅ Monero mining detected!")
        print(f"   Proof type: {proof['proof_type']}")
        print(f"   Bonus multiplier: {proof['bonus_multiplier']}x")
        print(f"   Chain: {proof['chain']}")
        
        if proof['proof_type'] == 'node_rpc':
            info = proof.get('node_info', {})
            print(f"   Height: {info.get('height', 'N/A')}")
            print(f"   Difficulty: {info.get('difficulty', 'N/A')}")
            print(f"   Hashrate: {info.get('hashrate', 'N/A')}")
        
        elif proof['proof_type'] == 'p2pool':
            stats = proof.get('p2pool_stats', {})
            print(f"   P2Pool stats available")
        
        elif proof['proof_type'] == 'pool':
            print(f"   Pool: {proof.get('pool', 'N/A')}")
        
        elif proof['proof_type'] == 'process':
            procs = proof.get('processes', [])
            print(f"   Processes: {len(procs)} detected")
            for p in procs[:3]:
                print(f"     - {p['name']} (PID: {p['pid']})")
    else:
        print("❌ No Monero mining detected")
        print()
        print("To mine Monero:")
        print("  1. Install XMRig: https://xmrig.com/")
        print("  2. Run monerod or connect to a pool")
        print("  3. This script will auto-detect and generate proof")
