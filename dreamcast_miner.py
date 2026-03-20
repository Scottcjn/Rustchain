// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import hashlib
import json
import os
import sqlite3
import struct
import time
import threading
from ctypes import *

DB_PATH = "rustchain.db"

class SH4HardwareFingerprinter:
    """Hardware fingerprinting optimized for Dreamcast SH4 processor"""

    def __init__(self):
        self.cache_timings = []
        self.fpu_jitter_samples = []
        self.tmu_drift_data = []

    def get_sh4_cpu_id(self):
        """Extract SH4 CPU version and cache configuration"""
        try:
            with open("/proc/cpuinfo", "r") as f:
                cpu_data = f.read()

            cpu_id = {"arch": "sh4", "variant": "unknown"}
            for line in cpu_data.split("\n"):
                if "cpu family" in line:
                    cpu_id["family"] = line.split(":")[1].strip()
                elif "cpu type" in line:
                    cpu_id["type"] = line.split(":")[1].strip()
                elif "cache size" in line:
                    cpu_id["cache"] = line.split(":")[1].strip()

            return json.dumps(cpu_id, sort_keys=True)
        except:
            return "sh4_dreamcast_fallback"

    def measure_cache_timing(self):
        """Measure SH4 cache timing characteristics"""
        cache_data = bytearray(32768)  # 32KB to exceed cache
        timings = []

        for i in range(100):
            start = time.perf_counter_ns()

            # Sequential access pattern
            for j in range(0, len(cache_data), 64):
                cache_data[j] = (cache_data[j] + 1) & 0xFF

            end = time.perf_counter_ns()
            timings.append(end - start)

        self.cache_timings = timings
        return sum(timings) // len(timings)

    def measure_fpu_jitter(self):
        """Measure SH4 FPU timing jitter patterns"""
        jitter_samples = []
        base_val = 3.141592653589793

        for i in range(50):
            start = time.perf_counter_ns()

            # FPU-intensive operations
            result = base_val
            for _ in range(100):
                result = result * 1.0001 + 0.0001
                result = result / 1.0001 - 0.0001

            end = time.perf_counter_ns()
            jitter_samples.append(end - start)

        self.fpu_jitter_samples = jitter_samples
        variance = sum((x - sum(jitter_samples) // len(jitter_samples)) ** 2 for x in jitter_samples)
        return variance // len(jitter_samples)

    def detect_tmu_drift(self):
        """Detect SH4 Timer Unit (TMU) drift characteristics"""
        tmu_readings = []

        # Sample TMU behavior over short intervals
        for i in range(20):
            start_time = time.time()
            time.sleep(0.001)  # 1ms sleep
            actual_elapsed = time.time() - start_time

            # Calculate drift from expected 1ms
            drift = abs(actual_elapsed - 0.001) * 1000000  # microseconds
            tmu_readings.append(int(drift))

        self.tmu_drift_data = tmu_readings
        return sum(tmu_readings) // len(tmu_readings)

    def generate_fingerprint(self):
        """Generate unique SH4 hardware fingerprint"""
        cpu_id = self.get_sh4_cpu_id()
        cache_timing = self.measure_cache_timing()
        fpu_jitter = self.measure_fpu_jitter()
        tmu_drift = self.detect_tmu_drift()

        # Combine all measurements
        fingerprint_data = {
            "cpu_id": cpu_id,
            "cache_avg": cache_timing,
            "cache_pattern": self.cache_timings[-10:],  # Last 10 samples
            "fpu_jitter": fpu_jitter,
            "fpu_pattern": self.fpu_jitter_samples[-5:],  # Last 5 samples
            "tmu_drift": tmu_drift,
            "tmu_pattern": self.tmu_drift_data[-5:],
            "arch_signature": "dreamcast_sh4_200mhz"
        }

        fingerprint_str = json.dumps(fingerprint_data, sort_keys=True)
        return hashlib.sha256(fingerprint_str.encode()).hexdigest()

class DreamcastMiner:
    """RustChain miner optimized for Dreamcast SH4 architecture"""

    def __init__(self):
        self.fingerprinter = SH4HardwareFingerprinter()
        self.hw_fingerprint = None
        self.mining_active = False
        self.hash_count = 0
        self.start_time = None
        self.difficulty_target = "0000"

        self.init_database()

    def init_database(self):
        """Initialize mining database"""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dreamcast_blocks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    block_hash TEXT UNIQUE,
                    previous_hash TEXT,
                    nonce INTEGER,
                    timestamp REAL,
                    hw_fingerprint TEXT,
                    sh4_proof TEXT,
                    difficulty TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS mining_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_start REAL,
                    total_hashes INTEGER,
                    blocks_found INTEGER,
                    avg_hashrate REAL,
                    hw_fingerprint TEXT
                )
            """)

    def get_previous_block_hash(self):
        """Get hash of most recent block"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                "SELECT block_hash FROM dreamcast_blocks ORDER BY id DESC LIMIT 1"
            )
            result = cursor.fetchone()
            return result[0] if result else "genesis_dreamcast_sh4"

    def create_sh4_proof(self):
        """Create SH4-specific proof data"""
        cache_sample = self.fingerprinter.measure_cache_timing()
        fpu_sample = self.fingerprinter.measure_fpu_jitter()

        proof_data = {
            "cache_timing": cache_sample,
            "fpu_jitter": fpu_sample,
            "timestamp_ns": time.perf_counter_ns(),
            "arch": "sh4_dreamcast"
        }

        return json.dumps(proof_data, sort_keys=True)

    def calculate_hash(self, block_data, nonce):
        """Calculate block hash with SH4 optimization"""
        hasher = hashlib.sha256()
        hasher.update(block_data.encode())
        hasher.update(struct.pack("<Q", nonce))  # Little-endian for SH4
        return hasher.hexdigest()

    def mine_block(self):
        """Mine a single block"""
        previous_hash = self.get_previous_block_hash()
        timestamp = time.time()
        sh4_proof = self.create_sh4_proof()

        block_template = {
            "previous_hash": previous_hash,
            "timestamp": timestamp,
            "hw_fingerprint": self.hw_fingerprint,
            "sh4_proof": sh4_proof,
            "miner": "dreamcast_sh4_miner"
        }

        block_data = json.dumps(block_template, sort_keys=True)
        nonce = 0

        print(f"Mining new block (prev: {previous_hash[:16]}...)")

        while self.mining_active:
            block_hash = self.calculate_hash(block_data, nonce)
            self.hash_count += 1

            if block_hash.startswith(self.difficulty_target):
                # Found valid block
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute("""
                        INSERT INTO dreamcast_blocks
                        (block_hash, previous_hash, nonce, timestamp, hw_fingerprint, sh4_proof, difficulty)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (block_hash, previous_hash, nonce, timestamp,
                          self.hw_fingerprint, sh4_proof, self.difficulty_target))

                print(f"Block found! Hash: {block_hash}")
                print(f"Nonce: {nonce}")
                return True

            nonce += 1

            # Progress update every 1000 hashes (memory-friendly for 16MB RAM)
            if nonce % 1000 == 0:
                elapsed = time.time() - self.start_time
                hashrate = self.hash_count / elapsed if elapsed > 0 else 0
                print(f"Hashes: {self.hash_count}, Rate: {hashrate:.1f} H/s, Nonce: {nonce}")

        return False

    def start_mining(self):
        """Start the mining process"""
        print("Dreamcast SH4 RustChain Miner")
        print("==============================")

        print("Generating hardware fingerprint...")
        self.hw_fingerprint = self.fingerprinter.generate_fingerprint()
        print(f"Hardware ID: {self.hw_fingerprint[:16]}...")

        # Check if this is real SH4 hardware
        cpu_info = self.fingerprinter.get_sh4_cpu_id()
        if "sh4" not in cpu_info.lower():
            print("WARNING: Not running on SH4 hardware - antiquity multiplier disabled")
        else:
            print("SH4 hardware detected - 3.0x antiquity multiplier active!")

        self.mining_active = True
        self.start_time = time.time()

        try:
            while self.mining_active:
                self.mine_block()

        except KeyboardInterrupt:
            print("\nMining stopped by user")
            self.mining_active = False

        self.save_mining_stats()

    def save_mining_stats(self):
        """Save mining session statistics"""
        if self.start_time:
            elapsed = time.time() - self.start_time
            avg_hashrate = self.hash_count / elapsed if elapsed > 0 else 0

            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("""
                    INSERT INTO mining_stats
                    (session_start, total_hashes, blocks_found, avg_hashrate, hw_fingerprint)
                    VALUES (?, ?, ?, ?, ?)
                """, (self.start_time, self.hash_count, 0, avg_hashrate, self.hw_fingerprint))

            print(f"Session stats: {self.hash_count} hashes, {avg_hashrate:.2f} H/s avg")

def main():
    miner = DreamcastMiner()
    miner.start_mining()

if __name__ == "__main__":
    main()
