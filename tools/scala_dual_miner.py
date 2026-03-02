#!/usr/bin/env python3
"""
Scala Dual-Mining Integration for RustChain
Bounty #473 - 10 RTC

Detects Scala (XLA) mining and provides attestation bonuses.
"""

import json
import subprocess
import requests
from typing import Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ScalaProof:
    method: str
    detected: bool
    multiplier: float
    details: Dict


class ScalaRPCClient:
    """Scala daemon RPC client."""
    
    def __init__(self, host: str = "localhost", port: int = 11812,
                 username: str = None, password: str = None):
        self.url = f"http://{host}:{port}/json_rpc"
        self.auth = (username, password) if username and password else None
    
    def get_mining_info(self) -> Optional[Dict]:
        """Query getmininginfo from scala daemon."""
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": "rustchain",
                "method": "getmininginfo",
                "params": {}
            }
            response = requests.post(self.url, json=payload, auth=self.auth, timeout=5)
            response.raise_for_status()
            return response.json().get('result')
        except Exception as e:
            print(f"RPC query failed: {e}")
            return None
    
    def verify(self) -> ScalaProof:
        """Verify local Scala node mining."""
        info = self.get_mining_info()
        if info and info.get('active', False):
            return ScalaProof(
                method="rpc",
                detected=True,
                multiplier=1.5,
                details={"difficulty": info.get('difficulty', 0)}
            )
        return ScalaProof(method="rpc", detected=False, multiplier=1.0, details={})


class ScalaProcessDetector:
    """Detect Scala mining processes."""
    
    MINING_PROCESSES = ["scala", "xmrig", "xla-miner"]
    
    def detect(self) -> ScalaProof:
        """Detect mining processes."""
        detected = []
        try:
            result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
            for process in self.MINING_PROCESSES:
                if process in result.stdout:
                    detected.append(process)
        except Exception as e:
            print(f"Process detection failed: {e}")
        
        if detected:
            return ScalaProof(
                method="process",
                detected=True,
                multiplier=1.15,
                details={"processes": detected}
            )
        return ScalaProof(method="process", detected=False, multiplier=1.0, details={})


class ScalaDualMiner:
    """Main dual-mining integration."""
    
    def __init__(self, rpc_user: str = None, rpc_pass: str = None):
        self.rpc = ScalaRPCClient(username=rpc_user, password=rpc_pass)
        self.process_detector = ScalaProcessDetector()
    
    def verify_all(self) -> Tuple[ScalaProof, ...]:
        """Run all verification methods."""
        return (self.rpc.verify(), self.process_detector.detect())
    
    def get_attestation_bonus(self) -> Dict:
        """Get attestation bonus for RustChain."""
        proofs = self.verify_all()
        best = max(p.multiplier for p in proofs)
        return {
            "scala_detected": any(p.detected for p in proofs),
            "bonus_multiplier": best,
            "proofs": [{"method": p.method, "detected": p.detected, "multiplier": p.multiplier} for p in proofs]
        }


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Scala Dual-Mining Verification")
    parser.add_argument("--rpc-user")
    parser.add_argument("--rpc-pass")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    
    miner = ScalaDualMiner(rpc_user=args.rpc_user, rpc_pass=args.rpc_pass)
    result = miner.get_attestation_bonus()
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Scala Detected: {result['scala_detected']}")
        print(f"Bonus Multiplier: {result['bonus_multiplier']}x")
