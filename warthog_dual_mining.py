# SPDX-License-Identifier: MIT

import json
import logging
import psutil
import requests
import sqlite3
import subprocess
import time
from typing import Dict, List, Optional, Tuple

# Configuration
WARTHOG_RPC_PORTS = [3000, 3001]
WARTHOG_PROCESS_NAMES = ["wart-miner", "warthog-miner", "janushash"]
DB_PATH = "dual_mining.db"
FINGERPRINT_INTERVAL = 600  # 10 minutes
PROCESS_CHECK_INTERVAL = 30  # 30 seconds

# Pool APIs
WOOLYPOOLY_API = "https://api.woolypooly.com/api/warthog-{}/stats"
ACC_POOL_API = "https://acc-pool.pw/api/stats"

logger = logging.getLogger(__name__)


class WarthogDualMiner:
    def __init__(self):
        self.init_database()
        self.last_fingerprint = 0
        self.active_processes = []
        self.node_info = {}

    def init_database(self):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS warthog_mining (
                    timestamp INTEGER PRIMARY KEY,
                    process_count INTEGER,
                    node_height INTEGER,
                    node_hash TEXT,
                    pool_verified INTEGER,
                    cpu_usage REAL,
                    memory_mb INTEGER
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS mining_sessions (
                    session_id TEXT PRIMARY KEY,
                    start_time INTEGER,
                    end_time INTEGER,
                    total_hashes INTEGER,
                    avg_hashrate REAL,
                    rip_poa_fingerprints INTEGER
                )
            ''')
            conn.commit()

    def detect_warthog_processes(self) -> List[Dict]:
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_info']):
            try:
                proc_name = proc.info['name'].lower()
                cmdline = ' '.join(proc.info['cmdline'] or []).lower()

                is_warthog = any(name in proc_name for name in WARTHOG_PROCESS_NAMES)
                is_janushash = 'janushash' in cmdline or 'warthog' in cmdline

                if is_warthog or is_janushash:
                    processes.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'cmdline': proc.info['cmdline'],
                        'cpu_percent': proc.info['cpu_percent'],
                        'memory_mb': proc.info['memory_info'].rss / 1024 / 1024 if proc.info['memory_info'] else 0
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return processes

    def query_warthog_node(self) -> Optional[Dict]:
        for port in WARTHOG_RPC_PORTS:
            try:
                url = f"http://localhost:{port}/chain/head"
                response = requests.get(url, timeout=5)
                if response.ok:
                    data = response.json()
                    return {
                        'port': port,
                        'height': data.get('height', 0),
                        'hash': data.get('hash', ''),
                        'timestamp': int(time.time())
                    }
            except (requests.RequestException, json.JSONDecodeError):
                continue
        return None

    def verify_pool_account(self, wallet_address: str) -> Dict:
        verification = {
            'woolypooly': False,
            'acc_pool': False,
            'total_hashrate': 0,
            'worker_count': 0
        }

        # WoolyPooly verification
        try:
            url = WOOLYPOOLY_API.format(wallet_address)
            response = requests.get(url, timeout=10)
            if response.ok:
                data = response.json()
                verification['woolypooly'] = True
                verification['total_hashrate'] += data.get('hashrate', 0)
                verification['worker_count'] += len(data.get('workers', []))
        except:
            pass

        # ACC Pool verification
        try:
            response = requests.get(ACC_POOL_API, timeout=10)
            if response.ok:
                data = response.json()
                miners = data.get('miners', {})
                if wallet_address in miners:
                    verification['acc_pool'] = True
                    miner_data = miners[wallet_address]
                    verification['total_hashrate'] += miner_data.get('hashrate', 0)
                    verification['worker_count'] += miner_data.get('workers', 0)
        except:
            pass

        return verification

    def rip_poa_fingerprint(self) -> Dict:
        """Minimal CPU fingerprinting for RIP-PoA compliance"""
        start_time = time.time()

        fingerprint = {
            'timestamp': int(start_time),
            'cpu_count': psutil.cpu_count(),
            'cpu_freq': psutil.cpu_freq().current if psutil.cpu_freq() else 0,
            'memory_total': psutil.virtual_memory().total,
            'processes': len(self.active_processes),
            'node_height': self.node_info.get('height', 0)
        }

        # Quick CPU usage sample
        cpu_samples = []
        for _ in range(3):
            cpu_samples.append(psutil.cpu_percent(interval=0.1))

        fingerprint['cpu_avg'] = sum(cpu_samples) / len(cpu_samples)
        fingerprint['duration_ms'] = int((time.time() - start_time) * 1000)

        return fingerprint

    def log_mining_stats(self, processes: List[Dict], node_info: Optional[Dict],
                        pool_verified: bool):
        timestamp = int(time.time())
        total_cpu = sum(p['cpu_percent'] for p in processes)
        total_memory = sum(p['memory_mb'] for p in processes)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO warthog_mining
                (timestamp, process_count, node_height, node_hash, pool_verified,
                 cpu_usage, memory_mb)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                timestamp,
                len(processes),
                node_info['height'] if node_info else 0,
                node_info['hash'] if node_info else '',
                1 if pool_verified else 0,
                total_cpu,
                total_memory
            ))
            conn.commit()

    def get_mining_stats(self, hours: int = 24) -> Dict:
        cutoff = int(time.time()) - (hours * 3600)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT
                    COUNT(*) as records,
                    AVG(process_count) as avg_processes,
                    MAX(node_height) as max_height,
                    AVG(cpu_usage) as avg_cpu,
                    AVG(memory_mb) as avg_memory,
                    SUM(pool_verified) as pool_verified_count
                FROM warthog_mining
                WHERE timestamp > ?
            ''', (cutoff,))

            row = cursor.fetchone()
            return {
                'records': row[0],
                'avg_processes': row[1] or 0,
                'max_height': row[2] or 0,
                'avg_cpu_usage': row[3] or 0,
                'avg_memory_mb': row[4] or 0,
                'pool_verified_ratio': (row[5] or 0) / max(row[0], 1)
            }

    def run_monitoring_loop(self, wallet_address: str = None):
        """Main monitoring loop"""
        logger.info("Starting Warthog dual-mining monitor")

        while True:
            try:
                # Detect active processes
                self.active_processes = self.detect_warthog_processes()

                # Query local node
                self.node_info = self.query_warthog_node()

                # Pool verification (if wallet provided)
                pool_verified = False
                if wallet_address and self.active_processes:
                    pool_data = self.verify_pool_account(wallet_address)
                    pool_verified = pool_data['woolypooly'] or pool_data['acc_pool']

                # RIP-PoA fingerprinting
                current_time = time.time()
                if current_time - self.last_fingerprint > FINGERPRINT_INTERVAL:
                    fingerprint = self.rip_poa_fingerprint()
                    logger.info(f"RIP-PoA fingerprint: {fingerprint['duration_ms']}ms, "
                              f"CPU avg: {fingerprint['cpu_avg']:.1f}%")
                    self.last_fingerprint = current_time

                # Log stats
                if self.active_processes or self.node_info:
                    self.log_mining_stats(self.active_processes, self.node_info, pool_verified)

                    logger.info(f"Warthog mining: {len(self.active_processes)} processes, "
                              f"node height: {self.node_info.get('height', 'N/A')}, "
                              f"pool verified: {pool_verified}")

                time.sleep(PROCESS_CHECK_INTERVAL)

            except KeyboardInterrupt:
                logger.info("Shutting down Warthog dual-mining monitor")
                break
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                time.sleep(PROCESS_CHECK_INTERVAL)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Warthog dual-mining monitor")
    parser.add_argument('--wallet', help='Warthog wallet address for pool verification')
    parser.add_argument('--stats', action='store_true', help='Show mining stats and exit')
    parser.add_argument('--hours', type=int, default=24, help='Stats timeframe in hours')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO,
                          format='%(asctime)s - %(levelname)s - %(message)s')

    miner = WarthogDualMiner()

    if args.stats:
        stats = miner.get_mining_stats(args.hours)
        print(f"Warthog Mining Stats ({args.hours}h):")
        print(f"  Records: {stats['records']}")
        print(f"  Avg Processes: {stats['avg_processes']:.1f}")
        print(f"  Max Chain Height: {stats['max_height']}")
        print(f"  Avg CPU Usage: {stats['avg_cpu_usage']:.1f}%")
        print(f"  Avg Memory: {stats['avg_memory_mb']:.1f} MB")
        print(f"  Pool Verified: {stats['pool_verified_ratio']:.1%}")
    else:
        miner.run_monitoring_loop(args.wallet)


if __name__ == '__main__':
    main()
