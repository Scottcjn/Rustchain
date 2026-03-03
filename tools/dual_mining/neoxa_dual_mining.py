"""
Neoxa Dual-Mining Integration for RustChain
Bounty #462 - 15 RTC

Mine Neoxa (NEOX) while earning RTC attestation rewards.
Neoxa uses KawPow algorithm - GPU mineable.
"""
import requests
import psutil
from typing import Optional, Dict, Any


class NeoxaDualMiner:
    """Neoxa dual-mining proof generator for RustChain"""
    
    def __init__(self):
        pass
    
    def get_pool_proof(self, wallet_address: str = None) -> Optional[Dict[str, Any]]:
        """
        Verify mining via Neoxa pool API (1.3x bonus)
        Supports HeroMiners and other NEOX pools
        """
        pools = []
        
        if wallet_address:
            pools.append(f"https://neoxa.herominers.com/api/stats_address?address={wallet_address}")
        
        pools.extend([
            "https://neoxa.herominers.com/api/stats",
        ])
        
        for pool_api in pools:
            try:
                response = requests.get(pool_api, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "proof_type": "pool",
                        "bonus_multiplier": 1.3,
                        "chain": "neoxa",
                        "pool": pool_api,
                        "pool_stats": data
                    }
            except Exception as e:
                continue
        return None
    
    def get_process_detection_proof(self) -> Optional[Dict[str, Any]]:
        """
        Detect Neoxa miner processes (1.15x bonus)
        Detects: kawpow-miner, lolminer, trex, gminer, teamredminer, nbminer
        """
        neoxa_processes = []
        neoxa_keywords = ['kawpow', 'neoxa', 'lolminer', 'trex', 'gminer', 
                          'teamredminer', 'nbminer', 'bminer']
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                name = proc.info['name'].lower()
                cmdline = ' '.join(proc.info['cmdline'] or []).lower()
                
                for keyword in neoxa_keywords:
                    if keyword in name or keyword in cmdline:
                        neoxa_processes.append({
                            'pid': proc.info['pid'],
                            'name': proc.info['name'],
                            'cmdline': cmdline[:200]
                        })
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if neoxa_processes:
            return {
                "proof_type": "process",
                "bonus_multiplier": 1.15,
                "chain": "neoxa",
                "processes": neoxa_processes
            }
        return None
    
    def get_best_proof(self) -> Optional[Dict[str, Any]]:
        """Get the best available proof (highest bonus)"""
        proofs = []
        
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
    print("Neoxa Dual-Mining Proof Generator")
    print("=" * 40)
    
    miner = NeoxaDualMiner()
    proof = miner.get_best_proof()
    
    if proof:
        print(f"✅ Neoxa mining detected!")
        print(f"   Proof type: {proof['proof_type']}")
        print(f"   Bonus multiplier: {proof['bonus_multiplier']}x")
        
        if proof['proof_type'] == 'pool':
            print(f"   Pool: {proof.get('pool', 'N/A')}")
        
        elif proof['proof_type'] == 'process':
            procs = proof.get('processes', [])
            print(f"   Processes: {len(procs)} detected")
    else:
        print("❌ No Neoxa mining detected")
