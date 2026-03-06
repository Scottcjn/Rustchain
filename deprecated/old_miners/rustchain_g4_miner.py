#!/usr/bin/env python3
"""
RustChain PowerPC G4 Miner - Persistent
Simulates PowerPC G4 hardware for RustChain v2.2.1
"""
import os, sys, json, time, hashlib, uuid, requests
from datetime import datetime

NODE_URL = "http://localhost:8088"
BLOCK_TIME = 600  # 10 minutes

class G4Miner:
    def __init__(self, miner_id="dual-g4-125", wallet=None):
        self.node_url = NODE_URL
        self.miner_id = miner_id
        self.wallet = wallet or f"ppc_g4_{hashlib.sha256(f'{miner_id}-{time.time()}'.encode()).hexdigest()[:38]}RTC"
        self.enrolled = False
        self.attestation_valid_until = 0

        # PowerPC G4 hardware profile
        self.hw_info = {
            "family": "PowerPC",
            "arch": "G4",
            "model": "PowerMac3,6",
            "cpu": "PowerPC G4 (7447A)",
            "cores": 2,
            "memory_gb": 2,
            "mac": "00:0d:93:12:34:56",  # Classic Mac Pro MAC format
            "hostname": f"powermac-{miner_id}"
        }

        print("="*70)
        print("RustChain PowerPC G4 Miner - v2.2.1")
        print("="*70)
        print(f"Miner ID: {self.miner_id}")
        print(f"Wallet: {self.wallet}")
        print(f"Hardware: {self.hw_info['cpu']}")
        print(f"Expected Weight: 2.5x (PowerPC/G4)")
        print("="*70)

    def attest(self):
        """Complete hardware attestation"""
        print(f"\n🔐 [{datetime.now().strftime('%H:%M:%S')}] Attesting as PowerPC G4...")

        try:
            # Step 1: Get challenge
            resp = requests.post(f"{self.node_url}/attest/challenge", json={}, timeout=10)
            if resp.status_code != 200:
                print(f"❌ Challenge failed: {resp.status_code}")
                return False

            challenge = resp.json()
            nonce = challenge.get("nonce")
            print(f"✅ Got challenge nonce")

        except Exception as e:
            print(f"❌ Challenge error: {e}")
            return False

        # Step 2: Submit attestation
        attestation = {
            "miner": self.wallet,
            "miner_id": self.miner_id,
            "nonce": nonce,
            "report": {
                "nonce": nonce,
                "commitment": hashlib.sha256(f"{nonce}{self.wallet}".encode()).hexdigest()
            },
            "device": {
                "family": self.hw_info["family"],
                "arch": self.hw_info["arch"],
                "model": self.hw_info["model"],
                "cpu": self.hw_info["cpu"],
                "cores": self.hw_info["cores"],
                "memory_gb": self.hw_info["memory_gb"]
            },
            "signals": {
                "macs": [self.hw_info["mac"]],
                "hostname": self.hw_info["hostname"]
            }
        }

        try:
            resp = requests.post(f"{self.node_url}/attest/submit",
                               json=attestation, timeout=30)

            if resp.status_code == 200:
                result = resp.json()
                if result.get("ok"):
                    self.attestation_valid_until = time.time() + 580
                    print(f"✅ Attestation accepted!")
                    print(f"   Hardware: PowerPC G4")
                    print(f"   Expected Weight: 2.5x")
                    return True
                else:
                    print(f"❌ Rejected: {result}")
            else:
                print(f"❌ HTTP {resp.status_code}: {resp.text[:200]}")

        except Exception as e:
            print(f"❌ Error: {e}")

        return False

    def enroll(self):
        """Enroll in current epoch"""
        # Check attestation validity
        if time.time() >= self.attestation_valid_until:
            print(f"📝 Attestation expired, re-attesting...")
            if not self.attest():
                return False

        print(f"\n📝 [{datetime.now().strftime('%H:%M:%S')}] Enrolling in epoch...")

        payload = {
            "miner_pubkey": self.wallet,
            "miner_id": self.miner_id,
            "device": {
                "family": self.hw_info["family"],
                "arch": self.hw_info["arch"]
            }
        }

        try:
            resp = requests.post(f"{self.node_url}/epoch/enroll",
                                json=payload, timeout=30)

            if resp.status_code == 200:
                result = resp.json()
                if result.get("ok"):
                    self.enrolled = True
                    weight = result.get('weight', 1.0)
                    print(f"✅ Enrolled successfully!")
                    print(f"   Epoch: {result.get('epoch')}")
                    print(f"   Weight: {weight}x {'✅' if weight >= 2.5 else '⚠️'}")
                    return True
                else:
                    print(f"❌ Failed: {result}")
            else:
                error_data = resp.json() if resp.headers.get('content-type') == 'application/json' else {}
                print(f"❌ HTTP {resp.status_code}: {error_data.get('error', resp.text[:200])}")

        except Exception as e:
            print(f"❌ Error: {e}")

        return False

    def check_balance(self):
        """Check balance"""
        try:
            resp = requests.get(f"{self.node_url}/balance/{self.wallet}", timeout=10)
            if resp.status_code == 200:
                result = resp.json()
                balance = result.get('balance_rtc', 0)
                print(f"\n💰 Balance: {balance} RTC")
                return balance
        except:
            pass
        return 0

    def mine_forever(self):
        """Keep mining continuously"""
        print(f"\n⛏️  Starting continuous mining...")
        print(f"Press Ctrl+C to stop\n")

        cycle = 0

        try:
            while True:
                cycle += 1
                print(f"\n{'='*70}")
                print(f"Cycle #{cycle} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{'='*70}")

                # Enroll (handles attestation automatically)
                if self.enroll():
                    print(f"⏳ Mining for {BLOCK_TIME//60} minutes...")

                    # Wait for block with progress updates
                    for i in range(BLOCK_TIME // 30):
                        time.sleep(30)
                        elapsed = (i + 1) * 30
                        remaining = BLOCK_TIME - elapsed
                        print(f"   ⏱️  {elapsed}s elapsed, {remaining}s remaining...")

                    # Check balance
                    self.check_balance()

                else:
                    print("❌ Enrollment failed. Retrying in 60s...")
                    time.sleep(60)

        except KeyboardInterrupt:
            print(f"\n\n⛔ Mining stopped")
            print(f"   Wallet: {self.wallet}")
            self.check_balance()

def main():
    import argparse
    parser = argparse.ArgumentParser(description="RustChain G4 Miner")
    parser.add_argument("--id", default="dual-g4-125", help="Miner ID")
    parser.add_argument("--wallet", help="Wallet address")
    args = parser.parse_args()

    miner = G4Miner(miner_id=args.id, wallet=args.wallet)
    miner.mine_forever()

if __name__ == "__main__":
    main()
