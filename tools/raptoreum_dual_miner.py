#!/usr/bin/env python3
"""
Raptoreum Dual-Mining Integration for RustChain
Bounty #469 - 15 RTC
"""

import os
import json
import subprocess
import requests
from typing import Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class RaptoreumProof:
    method: str
    detected: bool
    multiplier: float
    details: Dict


class RaptoreumRPCClient:
    def __init__(self, host: str = "localhost", port: int = 10225,
                 username: str = None, password: str = None):
        self.url = f"http://{host}:{port}"
        self.auth = (username, password) if username and password else None
    
    def get_mining_info(self) -> Optional[Dict]:
        try:
            payload = {
                "jsonrpc": "1.0",
                "id": "rustchain",
                "method": "getmininginfo",
                "params": []
            }
            response = requests.post(self.url, json=payload, auth=self.auth, timeout=5)
            response.raise_for_status()
            return response.json().get('result')
        except Exception as e:
            print(f"RPC query failed: {e}")
            return None
    
    def verify(self) -> RaptoreumProof:
        info = self.get_mining_info()
        if info and info.get('generate', False):
            return RaptoreumProof(
                method="rpc",
                detected=True,
                multiplier=1.5,
                details={"blocks": info.get('blocks', 0)}
            )
        return RaptoreumProof(method="rpc", detected=False, multiplier=1.0, details={})


class ProcessDetector:
    MINING_PROCESSES = ["raptoreumd", "cpuminer-gr", "xmrig"]
    
    def detect(self) -> RaptoreumProof:
        detected = []
        try:
            result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
            for process in self.MINING_PROCESSES:
                if process in result.stdout:
                    detected.append(process)
        except Exception as e:
            print(f"Process detection failed: {e}")
        
        if detected:
            return RaptoreumProof(method="process", detected=True, multiplier=1.15, details={"processes": detected})
        return RaptoreumProof(method="process", detected=False, multiplier=1.0, details={})


class RaptoreumDualMiner:
    def __init__(self, rpc_user: str = None, rpc_pass: str = None):
        self.rpc = RaptoreumRPCClient(username=rpc_user, password=rpc_pass)
        self.process_detector = ProcessDetector()
    
    def verify_all(self) -> Tuple[RaptoreumProof, ...]:
        return (self.rpc.verify(), self.process_detector.detect())
    
    def get_attestation_bonus(self) -> Dict:
        proofs = self.verify_all()
        best = max(p.multiplier for p in proofs)
        return {
            "raptoreum_detected": any(p.detected for p in proofs),
            "bonus_multiplier": best,
            "proofs": [{"method": p.method, "detected": p.detected, "multiplier": p.multiplier} for p in proofs]
        }


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--rpc-user")
    parser.add_argument("--rpc-pass")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    
    miner = RaptoreumDualMiner(rpc_user=args.rpc_user, rpc_pass=args.rpc_pass)
    result = miner.get_attestation_bonus()
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Raptoreum Detected: {result['raptoreum_detected']}")
        print(f"Bonus Multiplier: {result['bonus_multiplier']}x")
