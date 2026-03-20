# SPDX-License-Identifier: MIT

import json
import subprocess
import time
import sqlite3
import logging
from datetime import datetime
import requests
from contextlib import contextmanager

DB_PATH = 'rustchain.db'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@contextmanager
def get_db():
    """Database connection context manager."""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()

class NeoxaDualMiner:
    def __init__(self):
        self.neoxad_rpc_host = 'localhost'
        self.neoxad_rpc_port = 8788
        self.rpc_user = 'user'
        self.rpc_password = 'pass'
        self.supported_miners = ['neoxad', 'trex', 't-rex', 'gminer', 'nbminer']
        self.last_check_time = 0
        self.check_interval = 30

    def setup_database(self):
        """Initialize neoxa dual mining tables."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS neoxa_dual_mining (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    block_height INTEGER,
                    block_hash TEXT,
                    miner_process TEXT,
                    hashrate REAL,
                    rtc_earned REAL DEFAULT 0.0
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS neoxa_mining_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_start TEXT NOT NULL,
                    session_end TEXT,
                    total_blocks INTEGER DEFAULT 0,
                    total_rtc_earned REAL DEFAULT 0.0,
                    active INTEGER DEFAULT 1
                )
            ''')
            conn.commit()

    def query_neoxad_rpc(self, method, params=None):
        """Query neoxad RPC endpoint."""
        if params is None:
            params = []

        rpc_url = f'http://{self.neoxad_rpc_host}:{self.neoxad_rpc_port}'
        headers = {'Content-Type': 'application/json'}

        payload = {
            'jsonrpc': '2.0',
            'method': method,
            'params': params,
            'id': 1
        }

        try:
            auth = (self.rpc_user, self.rpc_password)
            response = requests.post(rpc_url, json=payload, headers=headers,
                                   auth=auth, timeout=10)
            response.raise_for_status()

            result = response.json()
            if 'error' in result and result['error']:
                logger.error(f"RPC error: {result['error']}")
                return None

            return result.get('result')

        except requests.RequestException as e:
            logger.error(f"Failed to query neoxad RPC: {e}")
            return None

    def get_mining_info(self):
        """Get current mining information from neoxad."""
        info = self.query_neoxad_rpc('getmininginfo')
        if info:
            return {
                'block_height': info.get('blocks', 0),
                'difficulty': info.get('difficulty', 0),
                'networkhashps': info.get('networkhashps', 0),
                'chain': info.get('chain', 'unknown')
            }
        return None

    def get_best_block_hash(self):
        """Get the hash of the current best block."""
        return self.query_neoxad_rpc('getbestblockhash')

    def detect_mining_processes(self):
        """Detect running mining processes."""
        detected_miners = []

        try:
            if hasattr(subprocess, 'STARTUPINFO'):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                result = subprocess.run(['tasklist'], capture_output=True,
                                      text=True, startupinfo=startupinfo)
                processes = result.stdout
            else:
                result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
                processes = result.stdout

            for miner in self.supported_miners:
                if miner.lower() in processes.lower():
                    detected_miners.append(miner)

        except subprocess.SubprocessError as e:
            logger.error(f"Failed to detect processes: {e}")

        return detected_miners

    def calculate_rtc_reward(self, hashrate, blocks_found=0):
        """Calculate RTC reward based on mining activity."""
        base_reward = 0.1
        hashrate_bonus = min(hashrate / 1000000, 10) * 0.05
        block_bonus = blocks_found * 2.0

        return base_reward + hashrate_bonus + block_bonus

    def start_mining_session(self):
        """Start a new mining session."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO neoxa_mining_sessions
                (session_start) VALUES (?)
            ''', (datetime.now().isoformat(),))
            conn.commit()
            return cursor.lastrowid

    def end_mining_session(self, session_id, total_blocks, total_rtc):
        """End a mining session."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE neoxa_mining_sessions
                SET session_end = ?, total_blocks = ?,
                    total_rtc_earned = ?, active = 0
                WHERE id = ?
            ''', (datetime.now().isoformat(), total_blocks, total_rtc, session_id))
            conn.commit()

    def record_mining_data(self, block_height, block_hash, miner_process,
                          hashrate=0.0, rtc_earned=0.0):
        """Record mining data to database."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO neoxa_dual_mining
                (timestamp, block_height, block_hash, miner_process,
                 hashrate, rtc_earned)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (datetime.now().isoformat(), block_height, block_hash,
                  miner_process, hashrate, rtc_earned))
            conn.commit()

    def monitor_dual_mining(self):
        """Main monitoring loop for Neoxa dual mining."""
        current_time = time.time()

        if current_time - self.last_check_time < self.check_interval:
            return

        self.last_check_time = current_time

        mining_info = self.get_mining_info()
        if not mining_info:
            logger.warning("Could not retrieve mining info from neoxad")
            return

        detected_miners = self.detect_mining_processes()
        if not detected_miners:
            logger.info("No supported mining processes detected")
            return

        block_hash = self.get_best_block_hash()
        if not block_hash:
            logger.warning("Could not retrieve best block hash")
            return

        logger.info(f"Neoxa mining active - Block: {mining_info['block_height']}")
        logger.info(f"Detected miners: {', '.join(detected_miners)}")

        estimated_hashrate = mining_info.get('networkhashps', 0) * 0.001
        rtc_reward = self.calculate_rtc_reward(estimated_hashrate)

        primary_miner = detected_miners[0] if detected_miners else 'unknown'

        self.record_mining_data(
            block_height=mining_info['block_height'],
            block_hash=block_hash,
            miner_process=primary_miner,
            hashrate=estimated_hashrate,
            rtc_earned=rtc_reward
        )

        logger.info(f"Recorded dual mining data - RTC earned: {rtc_reward:.4f}")

    def get_mining_stats(self):
        """Get mining statistics."""
        with get_db() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT COUNT(*) as total_records,
                       SUM(rtc_earned) as total_rtc,
                       AVG(hashrate) as avg_hashrate,
                       MAX(block_height) as latest_block
                FROM neoxa_dual_mining
            ''')

            stats = cursor.fetchone()
            if stats:
                return {
                    'total_records': stats[0] or 0,
                    'total_rtc_earned': stats[1] or 0.0,
                    'average_hashrate': stats[2] or 0.0,
                    'latest_block': stats[3] or 0
                }

        return {}

def initialize_neoxa_dual_mining():
    """Initialize Neoxa dual mining system."""
    miner = NeoxaDualMiner()
    miner.setup_database()
    return miner

if __name__ == '__main__':
    neoxa_miner = initialize_neoxa_dual_mining()

    logger.info("Starting Neoxa dual mining monitor...")

    try:
        while True:
            neoxa_miner.monitor_dual_mining()
            time.sleep(30)
    except KeyboardInterrupt:
        logger.info("Neoxa dual mining monitor stopped")
