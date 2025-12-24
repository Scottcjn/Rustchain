#!/usr/bin/env python3
"""
RustChain PowerPC G4 Miner - FIXED VERSION WITH HEADER SUBMISSION
Includes proper lottery checking and header submission flow
"""
import os, sys, json, time, hashlib, uuid, requests
from datetime import datetime

NODE_URL = "http://50.28.86.131:8088"
BLOCK_TIME = 600  # 10 minutes
LOTTERY_CHECK_INTERVAL = 10  # Check every 10 seconds

class G4Miner:
    def __init__(self, miner_id="dual-g4-125", wallet=None):
        self.node_url = NODE_URL
        self.miner_id = miner_id
        self.wallet = wallet or f"ppc_g4_{hashlib.sha256(f'{miner_id}-{time.time()}'.encode()).hexdigest()[:38]}RTC"
        self.enrolled = False
        self.attestation_valid_until = 0
        self.shares_submitted = 0
        self.shares_accepted = 0

        # PowerPC G4 hardware profile
        self.hw_info = {
            "family": "PowerPC",
            "arch": "G4",
            "model": "PowerMac3,6",
            "cpu": "PowerPC G4 (7447A)",
            "cores": 2,
            "memory_gb": 2,
            "mac": "00:0d:93:12:34:56",
            "hostname": f"powermac-{miner_id}"
        }

        print("="*70)
        print("RustChain PowerPC G4 Miner - v2.2.1 FIXED")
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
                    print(f"✅ Attestation accepted! Valid for 580 seconds")
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

    def check_lottery(self):
        """Check if eligible to submit header"""
        try:
            resp = requests.get(
                f"{self.node_url}/lottery/eligibility",
                params={"miner_id": self.miner_id},
                timeout=5
            )

            if resp.status_code == 200:
                result = resp.json()
                return result.get("eligible", False), result

        except Exception as e:
            # Silently fail - lottery checks happen frequently
            pass

        return False, {}

    def submit_header(self, slot):
        """Submit block header when lottery eligible"""
        # Generate mock signature (testnet mode allows this)
        message = f"{slot}{self.miner_id}{time.time()}"
        message_hash = hashlib.sha256(message.encode()).hexdigest()

        # Mock signature for testnet
        mock_signature = "0" * 128  # Testnet mode accepts this

        header = {
            "miner_id": self.miner_id,
            "slot": slot,
            "message": message_hash,
            "signature": mock_signature,
            "pubkey": self.wallet[:64]  # Inline pubkey (testnet mode)
        }

        try:
            resp = requests.post(
                f"{self.node_url}/headers/ingest_signed",
                json=header,
                timeout=10
            )

            self.shares_submitted += 1

            if resp.status_code == 200:
                result = resp.json()
                if result.get("ok"):
                    self.shares_accepted += 1
                    print(f"   ✅ Header accepted! (Slot {slot})")
                    print(f"   📊 Stats: {self.shares_accepted}/{self.shares_submitted} accepted")
                    return True
                else:
                    print(f"   ❌ Header rejected: {result.get('error', 'unknown')}")
            else:
                print(f"   ❌ HTTP {resp.status_code}: {resp.text[:100]}")

        except Exception as e:
            print(f"   ❌ Submit error: {e}")

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
        """Keep mining continuously with lottery checking"""
        print(f"\n⛏️  Starting continuous mining with lottery checking...")
        print(f"Checking lottery every {LOTTERY_CHECK_INTERVAL} seconds")
        print(f"Press Ctrl+C to stop\n")

        # Initial enrollment
        if not self.enroll():
            print("❌ Initial enrollment failed. Exiting.")
            return

        last_balance_check = 0
        re_enroll_interval = 3600  # Re-enroll every hour
        last_enroll = time.time()

        try:
            while True:
                # Re-enroll periodically
                if time.time() - last_enroll > re_enroll_interval:
                    print(f"\n🔄 Re-enrolling (periodic)...")
                    self.enroll()
                    last_enroll = time.time()

                # Check lottery eligibility
                eligible, info = self.check_lottery()

                if eligible:
                    slot = info.get("slot", 0)
                    print(f"\n🎰 LOTTERY WIN! Slot {slot}")
                    self.submit_header(slot)

                # Check balance every 5 minutes
                if time.time() - last_balance_check > 300:
                    self.check_balance()
                    last_balance_check = time.time()
                    print(f"📊 Mining stats: {self.shares_accepted}/{self.shares_submitted} headers accepted")

                time.sleep(LOTTERY_CHECK_INTERVAL)

        except KeyboardInterrupt:
            print(f"\n\n⛔ Mining stopped")
            print(f"   Wallet: {self.wallet}")
            print(f"   Headers: {self.shares_accepted}/{self.shares_submitted} accepted")
            self.check_balance()

def main():
    import argparse
    parser = argparse.ArgumentParser(description="RustChain G4 Miner - FIXED")
    parser.add_argument("--id", default="dual-g4-125", help="Miner ID")
    parser.add_argument("--wallet", help="Wallet address")
    args = parser.parse_args()

    miner = G4Miner(miner_id=args.id, wallet=args.wallet)
    miner.mine_forever()

if __name__ == "__main__":
    main()
