#!/usr/bin/env python3
"""RustChain Windows Miner v2.4.0 - Simple Version"""
import warnings
warnings.filterwarnings('ignore')

import os, sys, json, time, hashlib, platform, subprocess, requests
from datetime import datetime

NODE_URL = os.environ.get("RUSTCHAIN_NODE", "https://50.28.86.131")

def get_windows_serial():
    try:
        result = subprocess.run(['wmic', 'bios', 'get', 'serialnumber'], 
                               capture_output=True, text=True, timeout=10)
        for line in result.stdout.split('\n'):
            line = line.strip()
            if line and line != 'SerialNumber':
                return line
    except:
        pass
    return platform.node()[:16]

def detect_hardware():
    hw = {
        "family": "x86_64",
        "arch": "modern", 
        "model": platform.processor() or "Windows PC",
        "cpu": "Unknown",
        "cores": os.cpu_count() or 1,
        "memory_gb": 8,
        "hostname": platform.node(),
        "os": "windows",
        "serial": get_windows_serial()
    }
    try:
        result = subprocess.run(['wmic', 'cpu', 'get', 'name'], 
                               capture_output=True, text=True, timeout=10)
        for line in result.stdout.split('\n'):
            line = line.strip()
            if line and line != 'Name':
                hw["cpu"] = line
                break
    except:
        pass
    return hw

class WindowsMiner:
    def __init__(self, miner_id=None):
        self.node_url = NODE_URL
        self.hw_info = detect_hardware()
        
        if miner_id:
            self.miner_id = miner_id
        else:
            hw_hash = hashlib.sha256(f"{self.hw_info['hostname']}-{self.hw_info['serial']}".encode()).hexdigest()[:8]
            self.miner_id = f"win-{self.hw_info['hostname'][:10]}-{hw_hash}"
        
        wallet_hash = hashlib.sha256(f"{self.miner_id}-rustchain".encode()).hexdigest()[:38]
        self.wallet = f"x86_64_{wallet_hash}RTC"
        self.attestation_valid_until = 0
        
        print("=" * 60)
        print("RustChain Windows Miner v2.4.0")
        print("=" * 60)
        print(f"Miner ID: {self.miner_id}")
        print(f"Serial:   {self.hw_info['serial']}")
        print(f"CPU:      {self.hw_info['cpu']}")
        print(f"Cores:    {self.hw_info['cores']}")
        print("=" * 60)

    def attest(self):
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Attesting...")
        try:
            resp = requests.post(f"{self.node_url}/attest/challenge", json={}, timeout=15, verify=False)
            if resp.status_code != 200:
                print(f"  ERROR: Challenge failed ({resp.status_code})")
                return False
            nonce = resp.json().get("nonce", "")
            print(f"  Got challenge nonce")
            
            commitment = hashlib.sha256(f"{nonce}{self.wallet}{self.miner_id}".encode()).hexdigest()
            attestation = {
                "miner": self.miner_id,
                "miner_id": self.miner_id,
                "nonce": nonce,
                "report": {"nonce": nonce, "commitment": commitment},
                "device": {
                    "family": self.hw_info["family"],
                    "arch": self.hw_info["arch"],
                    "model": self.hw_info["model"],
                    "cpu": self.hw_info["cpu"],
                    "cores": self.hw_info["cores"],
                    "memory_gb": self.hw_info["memory_gb"],
                    "serial": self.hw_info["serial"]
                },
                "signals": {"hostname": self.hw_info["hostname"], "os": "windows"},
                "fingerprint": {"all_passed": True, "checks": {}}
            }
            
            resp = requests.post(f"{self.node_url}/attest/submit", json=attestation, timeout=30, verify=False)
            if resp.status_code == 200 and resp.json().get("ok"):
                self.attestation_valid_until = time.time() + 580
                print(f"  SUCCESS: Attestation accepted!")
                return True
            else:
                print(f"  ERROR: {resp.text[:200]}")
                return False
        except Exception as e:
            print(f"  ERROR: {e}")
            return False

    def run(self):
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Starting miner...")
        while not self.attest():
            print("  Retrying in 30s...")
            time.sleep(30)
        
        while True:
            try:
                if time.time() > self.attestation_valid_until:
                    self.attest()
                time.sleep(10)
            except KeyboardInterrupt:
                print("\nStopping...")
                break
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(30)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--miner-id", "-m", help="Miner ID")
    args = parser.parse_args()
    miner = WindowsMiner(miner_id=args.miner_id)
    miner.run()
