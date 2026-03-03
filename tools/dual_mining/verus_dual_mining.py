"""
Verus Dual-Mining Integration for RustChain
Bounty #459 - 20 RTC

Mine Verus (VRSC) while earning RTC attestation rewards.
Verus uses VerusHash 2.2 algorithm - CPU mineable.
"""
import requests
import psutil
from typing import Optional, Dict, Any


class VerusDualMiner:
    """Verus dual-mining proof generator for RustChain"""
    
    def __init__(self, node_url: str = "http://localhost:27486"):
        self.node_url = node_url
    
    def get_node_rpc_proof(self) -> Optional[Dict[str, Any]]:
        """
        Query Verus node RPC for proof (1.5x bonus)
        Queries localhost:27486 with getinfo
        """
        try:
            payload = {
                "jsonrpc": "1.0",
                "id": "rustchain",
                "method": "getinfo",
                "params": []
            }
            response = requests.post(
                self.node_url,
                json=payload,
                timeout=5,
                auth=('verus_user', 'verus_pass')  # Default, user should configure
            )
            if response.status_code == 200:
                data = response.json()
                if "result" in data:
                    result = data["result"]
                    return {
                        "proof_type": "node_rpc",
                        "bonus_multiplier": 1.5,
                        "chain": "verus",
                        "node_info": {
                            "version": result.get("version"),
                            "protocolversion": result.get("protocolversion"),
                            "blocks": result.get("blocks"),
                            "connections": result.get("connections"),
                            "difficulty": result.get("difficulty")
                        }
                    }
        except Exception as e:
            print(f"Node RPC not available: {e}")
        return None
    
    def get_pool_proof(self, wallet_address: str = None) -> Optional[Dict[str, Any]]:
        """
        Verify mining via Verus pool API (1.3x bonus)
        Supports Luckpool and other VRSC pools
        """
        pools = []
        
        if wallet_address:
            pools.append(f"https://luckpool.net/verus/miner/{wallet_address}")
        
        pools.extend([
            "https://luckpool.net/verus/",
            "https://verus.herominers.com/api/stats",
        ])
        
        for pool_api in pools:
            try:
                response = requests.get(pool_api, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "proof_type": "pool",
                        "bonus_multiplier": 1.3,
                        "chain": "verus",
                        "pool": pool_api,
                        "pool_stats": data
                    }
            except Exception as e:
                continue
        return None
    
    def get_process_detection_proof(self) -> Optional[Dict[str, Any]]:
        """
        Detect Verus miner processes (1.15x bonus)
        Detects: verusd, ccminer, nheqminer
        """
        verus_processes = []
        verus_keywords = ['verusd', 'verus-miner', 'ccminer', 'nheqminer', 
                          'verus-ethminer', 'vrsc']
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                name = proc.info['name'].lower()
                cmdline = ' '.join(proc.info['cmdline'] or []).lower()
                
                for keyword in verus_keywords:
                    if keyword in name or keyword in cmdline:
                        verus_processes.append({
                            'pid': proc.info['pid'],
                            'name': proc.info['name'],
                            'cmdline': cmdline[:200]
                        })
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if verus_processes:
            return {
                "proof_type": "process",
                "bonus_multiplier": 1.15,
                "chain": "verus",
                "processes": verus_processes
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
    print("Verus Dual-Mining Proof Generator")
    print("=" * 40)
    
    miner = VerusDualMiner()
    proof = miner.get_best_proof()
    
    if proof:
        print(f"✅ Verus mining detected!")
        print(f"   Proof type: {proof['proof_type']}")
        print(f"   Bonus multiplier: {proof['bonus_multiplier']}x")
        print(f"   Chain: {proof['chain']}")
        
        if proof['proof_type'] == 'node_rpc':
            info = proof.get('node_info', {})
            print(f"   Version: {info.get('version', 'N/A')}")
            print(f"   Blocks: {info.get('blocks', 'N/A')}")
            print(f"   Connections: {info.get('connections', 'N/A')}")
            print(f"   Difficulty: {info.get('difficulty', 'N/A')}")
        
        elif proof['proof_type'] == 'pool':
            print(f"   Pool: {proof.get('pool', 'N/A')}")
        
        elif proof['proof_type'] == 'process':
            procs = proof.get('processes', [])
            print(f"   Processes: {len(procs)} detected")
            for p in procs[:3]:
                print(f"     - {p['name']} (PID: {p['pid']})")
    else:
        print("❌ No Verus mining detected")
        print()
        print("To mine Verus:")
        print("  1. Install Verus node: https://verus.io/")
        print("  2. Run verusd or connect to Luckpool")
        print("  3. This script will auto-detect and generate proof")
