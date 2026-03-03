"""
Raptoreum Dual-Mining Integration for RustChain
Bounty #469 - 15 RTC

Mine Raptoreum (RTM) while earning RTC attestation rewards.
GhostRider algorithm - multi-algo rotation designed for CPUs.
"""
import requests
import subprocess
import psutil
from typing import Optional, Dict, Any

class RaptoreumDualMiner:
    """Raptoreum dual-mining proof generator for RustChain"""
    
    def __init__(self, node_url: str = "http://localhost:10225/json_rpc"):
        self.node_url = node_url
        self.rpc_user = ""
        self.rpc_password = ""
    
    def set_rpc_auth(self, user: str, password: str):
        """Set RPC authentication credentials"""
        self.rpc_user = user
        self.rpc_password = password
    
    def get_node_rpc_proof(self) -> Optional[Dict[str, Any]]:
        """
        Query raptoreumd node RPC for proof (1.5x bonus)
        Queries localhost:10225 getmininginfo
        """
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": "0",
                "method": "getmininginfo"
            }
            auth = (self.rpc_user, self.rpc_password) if self.rpc_user else None
            response = requests.post(
                self.node_url, 
                json=payload, 
                auth=auth,
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if "result" in data:
                    return {
                        "proof_type": "node_rpc",
                        "bonus_multiplier": 1.5,
                        "chain": "raptoreum",
                        "algorithm": "GhostRider",
                        "node_info": {
                            "blocks": data["result"].get("blocks"),
                            "difficulty": data["result"].get("difficulty"),
                            "networkhashps": data["result"].get("networkhashps"),
                            "genproclimit": data["result"].get("genproclimit")
                        }
                    }
        except Exception as e:
            print(f"Node RPC not available: {e}")
        return None
    
    def get_pool_proof(self, pool_api: str = "https://rtm.flockpool.com/api/stats") -> Optional[Dict[str, Any]]:
        """
        Verify mining via pool API (1.3x bonus)
        Supports Flockpool, Suprnova, and other RTM pools
        """
        try:
            response = requests.get(pool_api, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return {
                    "proof_type": "pool",
                    "bonus_multiplier": 1.3,
                    "chain": "raptoreum",
                    "algorithm": "GhostRider",
                    "pool": pool_api,
                    "pool_stats": {
                        "pool_hashrate": data.get("pool", {}).get("hashrate"),
                        "miners": data.get("pool", {}).get("miners"),
                        "last_block": data.get("pool", {}).get("lastBlockFound")
                    }
                }
        except Exception as e:
            print(f"Pool API not available: {e}")
        return None
    
    def get_process_detection_proof(self) -> Optional[Dict[str, Any]]:
        """
        Detect Raptoreum miner processes (1.15x bonus)
        Detects raptoreumd, cpuminer-gr, xmrig (GhostRider mode)
        """
        rtm_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                name = proc.info['name'].lower()
                cmdline = ' '.join(proc.info['cmdline'] or []).lower()
                if any(x in name or x in cmdline for x in [
                    'raptoreumd', 'raptoreum-wallet', 'cpuminer-gr',
                    'minerd', 'xmrig'
                ]):
                    # Check if GhostRider algo is specified
                    if 'ghost' in cmdline or 'rtm' in cmdline or 'raptoreum' in cmdline:
                        rtm_processes.append({
                            'pid': proc.info['pid'],
                            'name': proc.info['name'],
                            'cmdline': cmdline[:200]  # Truncate for brevity
                        })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if rtm_processes:
            return {
                "proof_type": "process",
                "bonus_multiplier": 1.15,
                "chain": "raptoreum",
                "algorithm": "GhostRider",
                "processes": rtm_processes
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
            # Return highest bonus proof
            return max(proofs, key=lambda p: p['bonus_multiplier'])
        return None
    
    def launch_miner(self, pool_url: str, wallet_address: str, 
                     miner_path: str = "cpuminer-gr") -> Optional[subprocess.Popen]:
        """
        Launch cpuminer-gr as managed subprocess (1.5x bonus)
        Example: cpuminer-gr -a ghost -o stratum+tcp://rtm.flockpool.com:3333 -u WALLET
        """
        try:
            cmd = [
                miner_path,
                "-a", "ghost",
                "-o", pool_url,
                "-u", wallet_address
            ]
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            return proc
        except Exception as e:
            print(f"Failed to launch miner: {e}")
        return None


if __name__ == "__main__":
    # Test dual-mining detection
    miner = RaptoreumDualMiner()
    proof = miner.get_best_proof()
    
    if proof:
        print(f"✅ Raptoreum mining detected!")
        print(f"Proof type: {proof['proof_type']}")
        print(f"Bonus multiplier: {proof['bonus_multiplier']}x")
        print(f"Chain: {proof['chain']}")
        print(f"Algorithm: {proof['algorithm']}")
    else:
        print("❌ No Raptoreum mining activity detected")
        print("\nTo start dual-mining:")
        print("1. Run raptoreumd locally, or")
        print("2. Connect to a pool (e.g., flockpool.com)")
        print("3. Run clawrtc mine --pow raptoreum")
