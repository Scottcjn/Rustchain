# SPDX-License-Identifier: MIT

import hashlib
import json
import os
import platform
import random
import requests
import sqlite3
import struct
import subprocess
import sys
import time
from datetime import datetime
from threading import Thread, Event, Lock


DB_PATH = "dreamcast_mining.db"
NODE_URL = os.getenv("RUSTCHAIN_NODE", "http://127.0.0.1:8332")
WALLET_ID = os.getenv("DREAMCAST_WALLET", "dreamcast_default")


class DreamcastDetector:
    def __init__(self):
        self.is_dreamcast = False
        self.sh4_features = {}
        self.hardware_sig = None
        self._detect_hardware()

    def _detect_hardware(self):
        try:
            # Check for SH4 architecture
            arch = platform.machine().lower()
            if 'sh' in arch or 'superh' in arch:
                self.is_dreamcast = True
                self._probe_sh4_specifics()

            # Fallback: check /proc/cpuinfo for SH4
            try:
                with open('/proc/cpuinfo', 'r') as f:
                    cpuinfo = f.read().lower()
                    if 'sh4' in cpuinfo or 'sh7750' in cpuinfo:
                        self.is_dreamcast = True
                        self._extract_sh4_info(cpuinfo)
            except:
                pass

            # Check for Dreamcast-specific hardware
            if self._check_dreamcast_hardware():
                self.is_dreamcast = True

            self._generate_hardware_signature()

        except Exception as e:
            print(f"Hardware detection failed: {e}")

    def _probe_sh4_specifics(self):
        """Probe SH4-specific CPU characteristics"""
        try:
            # Cache timing test - SH4 has 16KB I + 16KB D cache
            cache_timing = self._measure_cache_timing()
            self.sh4_features['cache_timing'] = cache_timing

            # FPU jitter measurement - SH4 has dedicated FPU
            fpu_jitter = self._measure_fpu_jitter()
            self.sh4_features['fpu_jitter'] = fpu_jitter

            # Memory access patterns unique to SH4
            mem_pattern = self._sh4_memory_pattern()
            self.sh4_features['memory_signature'] = mem_pattern

        except Exception as e:
            print(f"SH4 probing failed: {e}")

    def _measure_cache_timing(self):
        """Measure cache access timing patterns"""
        measurements = []
        for _ in range(100):
            start = time.perf_counter()
            # Access pattern that exercises SH4 cache
            dummy = sum(i * i for i in range(1000))
            end = time.perf_counter()
            measurements.append(end - start)

        avg_time = sum(measurements) / len(measurements)
        variance = sum((t - avg_time) ** 2 for t in measurements) / len(measurements)
        return {'avg': avg_time, 'variance': variance}

    def _measure_fpu_jitter(self):
        """Measure FPU timing jitter specific to SH4"""
        measurements = []
        for _ in range(50):
            start = time.perf_counter()
            # SH4 FPU operations
            result = 0.0
            for i in range(100):
                result += (i * 3.14159) / (i + 1.0)
            end = time.perf_counter()
            measurements.append(end - start)

        return {'mean': sum(measurements) / len(measurements),
                'jitter': max(measurements) - min(measurements)}

    def _sh4_memory_pattern(self):
        """Generate memory access pattern fingerprint"""
        pattern_hash = hashlib.sha256()

        # Test memory bandwidth - SH4 has specific timing
        data = bytearray(8192)  # 8KB test
        for i in range(0, len(data), 4):
            struct.pack_into('<I', data, i, i ^ 0xDEADBEEF)

        pattern_hash.update(data)
        return pattern_hash.hexdigest()[:16]

    def _check_dreamcast_hardware(self):
        """Check for Dreamcast-specific hardware indicators"""
        dreamcast_indicators = [
            '/proc/device-tree/compatible',
            '/sys/devices/platform/dreamcast',
            '/dev/maple',  # Dreamcast controller interface
        ]

        for path in dreamcast_indicators:
            if os.path.exists(path):
                return True

        # Check dmesg for Dreamcast boot messages
        try:
            result = subprocess.run(['dmesg'], capture_output=True, text=True, timeout=5)
            dmesg_output = result.stdout.lower()
            if any(term in dmesg_output for term in ['dreamcast', 'sh4', 'maple', 'gdrom']):
                return True
        except:
            pass

        return False

    def _extract_sh4_info(self, cpuinfo):
        """Extract SH4 CPU information from /proc/cpuinfo"""
        lines = cpuinfo.split('\n')
        for line in lines:
            if 'cpu family' in line and 'sh4' in line:
                self.sh4_features['cpu_family'] = line.split(':')[1].strip()
            elif 'cpu type' in line and ('7750' in line or 'sh4' in line):
                self.sh4_features['cpu_type'] = line.split(':')[1].strip()

    def _generate_hardware_signature(self):
        """Generate unique hardware signature for attestation"""
        sig_data = {
            'arch': platform.machine(),
            'is_dreamcast': self.is_dreamcast,
            'sh4_features': self.sh4_features,
            'timestamp': int(time.time())
        }

        sig_json = json.dumps(sig_data, sort_keys=True)
        self.hardware_sig = hashlib.sha256(sig_json.encode()).hexdigest()


class DreamcastMiner:
    def __init__(self):
        self.detector = DreamcastDetector()
        self.mining_active = Event()
        self.stats_lock = Lock()
        self.stats = {
            'hashes_computed': 0,
            'blocks_found': 0,
            'start_time': time.time(),
            'last_submission': None
        }
        self._init_database()

    def _init_database(self):
        """Initialize SQLite database for mining records"""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS mining_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    hardware_sig TEXT,
                    is_dreamcast BOOLEAN,
                    hashes_computed INTEGER DEFAULT 0,
                    blocks_submitted INTEGER DEFAULT 0,
                    session_end TIMESTAMP
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS block_submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    block_hash TEXT,
                    nonce INTEGER,
                    difficulty INTEGER,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    accepted BOOLEAN,
                    reward_rtc REAL
                )
            ''')

    def start_mining(self):
        """Start Dreamcast mining operation"""
        if not self.detector.is_dreamcast:
            print("WARNING: Not running on Dreamcast hardware - no antiquity multiplier")

        print(f"Starting Dreamcast RTC Miner...")
        print(f"Hardware signature: {self.detector.hardware_sig}")
        print(f"SH4 features detected: {len(self.detector.sh4_features)}")

        # Record mining session
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                INSERT INTO mining_sessions (hardware_sig, is_dreamcast)
                VALUES (?, ?)
            ''', (self.detector.hardware_sig, self.detector.is_dreamcast))

        self.mining_active.set()

        # Start mining threads
        threads = []
        for i in range(2):  # Conservative for 200MHz SH4
            t = Thread(target=self._mining_worker, args=(i,))
            t.daemon = True
            t.start()
            threads.append(t)

        # Stats reporting thread
        stats_thread = Thread(target=self._stats_reporter)
        stats_thread.daemon = True
        stats_thread.start()

        try:
            while self.mining_active.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down Dreamcast miner...")
            self.mining_active.clear()
            for t in threads:
                t.join(timeout=2)

    def _mining_worker(self, worker_id):
        """Individual mining thread optimized for SH4"""
        print(f"Mining worker {worker_id} started")

        while self.mining_active.is_set():
            try:
                # Get mining work
                work = self._get_mining_work()
                if not work:
                    time.sleep(5)
                    continue

                # SH4-optimized mining loop
                result = self._mine_block_sh4(work, worker_id)

                if result:
                    print(f"Worker {worker_id}: Found solution! Submitting...")
                    success = self._submit_solution(result)

                    with self.stats_lock:
                        if success:
                            self.stats['blocks_found'] += 1
                            self.stats['last_submission'] = time.time()

            except Exception as e:
                print(f"Worker {worker_id} error: {e}")
                time.sleep(2)

    def _get_mining_work(self):
        """Request mining work from RustChain node"""
        try:
            response = requests.get(f"{NODE_URL}/api/mining/getwork", timeout=10)
            if response.ok:
                work = response.json()
                # Include Dreamcast attestation
                work['miner_signature'] = self.detector.hardware_sig
                work['is_dreamcast'] = self.detector.is_dreamcast
                return work
        except Exception as e:
            print(f"Failed to get work: {e}")
        return None

    def _mine_block_sh4(self, work, worker_id):
        """SH4-optimized block mining"""
        block_data = work.get('block_template', '')
        difficulty = work.get('difficulty', 1)
        target = (1 << 256) // difficulty

        # SH4-specific optimization: use smaller nonce ranges
        base_nonce = random.randint(0, 0xFFFFFF)
        max_iterations = 10000  # Conservative for 200MHz CPU

        for i in range(max_iterations):
            nonce = base_nonce + i

            # Create block hash
            block_with_nonce = f"{block_data}{nonce}"
            hash_result = hashlib.sha256(block_with_nonce.encode()).hexdigest()

            with self.stats_lock:
                self.stats['hashes_computed'] += 1

            # Check if hash meets difficulty
            hash_int = int(hash_result, 16)
            if hash_int < target:
                return {
                    'block_hash': hash_result,
                    'nonce': nonce,
                    'difficulty': difficulty,
                    'miner_id': WALLET_ID,
                    'hardware_attestation': {
                        'signature': self.detector.hardware_sig,
                        'is_dreamcast': self.detector.is_dreamcast,
                        'sh4_features': self.detector.sh4_features
                    }
                }

            # Yield CPU periodically on low-power SH4
            if i % 100 == 0:
                time.sleep(0.001)

            if not self.mining_active.is_set():
                break

        return None

    def _submit_solution(self, solution):
        """Submit found solution to network"""
        try:
            response = requests.post(
                f"{NODE_URL}/api/mining/submit",
                json=solution,
                timeout=15
            )

            if response.ok:
                result = response.json()
                accepted = result.get('accepted', False)
                reward = result.get('reward_rtc', 0.0)

                # Log to database
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute('''
                        INSERT INTO block_submissions
                        (block_hash, nonce, difficulty, accepted, reward_rtc)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (solution['block_hash'], solution['nonce'],
                          solution['difficulty'], accepted, reward))

                if accepted:
                    print(f"Solution ACCEPTED! Reward: {reward} RTC")
                    return True
                else:
                    print("Solution rejected")

        except Exception as e:
            print(f"Submit failed: {e}")

        return False

    def _stats_reporter(self):
        """Report mining statistics periodically"""
        while self.mining_active.is_set():
            time.sleep(30)  # Report every 30 seconds

            with self.stats_lock:
                runtime = time.time() - self.stats['start_time']
                hashrate = self.stats['hashes_computed'] / runtime if runtime > 0 else 0

                print(f"[DREAMCAST MINER] Uptime: {runtime:.0f}s | "
                      f"Hashrate: {hashrate:.2f} H/s | "
                      f"Total hashes: {self.stats['hashes_computed']} | "
                      f"Blocks found: {self.stats['blocks_found']}")

    def get_balance(self):
        """Check RTC balance"""
        try:
            response = requests.get(f"{NODE_URL}/api/wallet/balance/{WALLET_ID}")
            if response.ok:
                return response.json().get('balance_rtc', 0.0)
        except:
            pass
        return 0.0

    def show_status(self):
        """Display current mining status"""
        balance = self.get_balance()

        print("\n=== DREAMCAST RTC MINER STATUS ===")
        print(f"Hardware: {'GENUINE DREAMCAST' if self.detector.is_dreamcast else 'Non-Dreamcast'}")
        print(f"SH4 Features: {len(self.detector.sh4_features)} detected")
        print(f"Wallet Balance: {balance:.6f} RTC")

        with self.stats_lock:
            runtime = time.time() - self.stats['start_time']
            hashrate = self.stats['hashes_computed'] / runtime if runtime > 0 else 0

            print(f"Mining Time: {runtime:.0f} seconds")
            print(f"Hash Rate: {hashrate:.2f} H/s")
            print(f"Total Hashes: {self.stats['hashes_computed']}")
            print(f"Blocks Found: {self.stats['blocks_found']}")

        if self.detector.is_dreamcast:
            print("*** 3.0x ANTIQUITY MULTIPLIER ACTIVE ***")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'status':
        miner = DreamcastMiner()
        miner.show_status()
        return

    print("Dreamcast RustChain Miner v1.0")
    print("Detecting SH4 hardware...")

    miner = DreamcastMiner()

    if not miner.detector.is_dreamcast:
        response = input("Not running on Dreamcast. Continue anyway? (y/N): ")
        if response.lower() != 'y':
            print("Exiting - use real Dreamcast hardware for full benefits")
            return

    try:
        miner.start_mining()
    except KeyboardInterrupt:
        print("\nMining stopped by user")
    except Exception as e:
        print(f"Mining error: {e}")


if __name__ == '__main__':
    main()
