#!/usr/bin/env python3
"""RustChain CLI Monitor Tool"""
import argparse
import json
import requests
import time
from datetime import datetime

class RustChainMonitor:
    """RustChain Node Monitor"""
    
    def __init__(self, base_url="http://localhost:8080"):
        self.base_url = base_url
    
    def check_health(self):
        """Check node health"""
        try:
            r = requests.get(f"{self.base_url}/health", timeout=5)
            return r.status_code == 200
        except:
            return False
    
    def get_balance(self, address):
        """Get wallet balance"""
        try:
            r = requests.get(f"{self.base_url}/wallet/{address}/balance", timeout=5)
            if r.status_code == 200:
                return r.json()
        except:
            pass
        return None
    
    def get_latest_block(self):
        """Get latest block info"""
        try:
            r = requests.get(f"{self.base_url}/block/latest", timeout=5)
            if r.status_code == 200:
                return r.json()
        except:
            pass
        return None
    
    def monitor(self, interval=30):
        """Continuous monitoring"""
        print(f"Starting RustChain Monitor (interval: {interval}s)")
        print("-" * 50)
        while True:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            healthy = self.check_health()
            status = "✅ OK" if healthy else "❌ DOWN"
            print(f"[{now}] Node Status: {status}")
            time.sleep(interval)

def main():
    parser = argparse.ArgumentParser(description="RustChain CLI Monitor")
    parser.add_argument("--url", default="http://localhost:8080", help="Node URL")
    parser.add_argument("--balance", help="Check balance for address")
    parser.add_argument("--block", action="store_true", help="Get latest block")
    parser.add_argument("--monitor", action="store_true", help="Continuous monitor")
    parser.add_argument("--interval", type=int, default=30, help="Monitor interval")
    
    args = parser.parse_args()
    monitor = RustChainMonitor(args.url)
    
    if args.balance:
        result = monitor.get_balance(args.balance)
        print(json.dumps(result, indent=2) if result else "Failed to get balance")
    elif args.block:
        result = monitor.get_latest_block()
        print(json.dumps(result, indent=2) if result else "Failed to get block info")
    elif args.monitor:
        monitor.monitor(args.interval)
    else:
        healthy = monitor.check_health()
        print("✅ Node is healthy" if healthy else "❌ Node is down")

if __name__ == "__main__":
    main()

# Bounty wallet: RTC27a4b8256b4d3c63737b27e96b181223cc8774ae
