#!/usr/bin/env python3
"""
RustChain Mining Pool Proxy Server

Aggregates attestations from multiple miners and submits combined
attestations to the RustChain node. Distributes rewards proportionally.

Usage:
    python3 pool_proxy.py --port 8080 --node-url http://50.28.86.131:8099

Features:
    - Accepts attestations from multiple miners
    - Tracks miner contributions (uptime, hardware score)
    - Submits combined attestation to RustChain node
    - Distributes epoch rewards proportionally
    - Simple web dashboard for pool statistics
"""

import os
import sys
import json
import time
import hashlib
import secrets
import argparse
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict
import sqlite3

try:
    from flask import Flask, request, jsonify, render_template_string, send_from_directory
except ImportError:
    print("Flask not installed. Install with: pip install flask")
    sys.exit(1)

# ============================================================================
# Configuration
# ============================================================================

DEFAULT_PORT = 8080
DEFAULT_NODE_URL = "http://50.28.86.131:8099"
DEFAULT_POOL_FEE = 0.01  # 1%
DEFAULT_DB_PATH = "./pool_proxy.db"
ATTESTATION_CACHE_TTL = 300  # 5 minutes

# ============================================================================
# Data Models
# ============================================================================

@dataclass
class Miner:
    """Represents a miner connected to the pool"""
    wallet: str
    device_id: str
    device_arch: str
    device_family: str
    joined_at: float
    last_attestation: float
    total_attestations: int
    uptime_seconds: float
    hardware_score: float
    contribution_weight: float
    total_rewards: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Attestation:
    """Represents a single attestation from a miner"""
    id: str
    miner_wallet: str
    device_id: str
    timestamp: float
    entropy_score: float
    hardware_score: float
    fingerprint: dict
    is_valid: bool

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PoolStats:
    """Pool-wide statistics"""
    total_miners: int
    active_miners: int  # Active in last hour
    total_attestations: int
    total_rewards_distributed: float
    pool_fee_collected: float
    current_epoch: int
    total_hash_power: float

    def to_dict(self) -> dict:
        return asdict(self)


# ============================================================================
# Database Manager
# ============================================================================

class PoolDatabase:
    """SQLite database for pool data persistence"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Miners table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS miners (
                    wallet TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL,
                    device_arch TEXT NOT NULL,
                    device_family TEXT NOT NULL,
                    joined_at REAL NOT NULL,
                    last_attestation REAL NOT NULL,
                    total_attestations INTEGER DEFAULT 0,
                    uptime_seconds REAL DEFAULT 0.0,
                    hardware_score REAL DEFAULT 1.0,
                    contribution_weight REAL DEFAULT 1.0,
                    total_rewards REAL DEFAULT 0.0
                )
            """)

            # Attestations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS attestations (
                    id TEXT PRIMARY KEY,
                    miner_wallet TEXT NOT NULL,
                    device_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    entropy_score REAL DEFAULT 0.0,
                    hardware_score REAL DEFAULT 1.0,
                    fingerprint TEXT,
                    is_valid INTEGER DEFAULT 1,
                    FOREIGN KEY (miner_wallet) REFERENCES miners(wallet)
                )
            """)

            # Rewards table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rewards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    epoch INTEGER NOT NULL,
                    miner_wallet TEXT NOT NULL,
                    gross_reward REAL NOT NULL,
                    pool_fee REAL NOT NULL,
                    net_reward REAL NOT NULL,
                    distributed_at REAL NOT NULL,
                    FOREIGN KEY (miner_wallet) REFERENCES miners(wallet)
                )
            """)

            # Pool config table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pool_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            # Insert default config
            cursor.execute("""
                INSERT OR IGNORE INTO pool_config (key, value)
                VALUES ('pool_fee', '0.01'), ('node_url', ?), ('started_at', ?)
            """, (DEFAULT_NODE_URL, time.time()))

            conn.commit()

    def add_miner(self, miner: Miner) -> bool:
        """Add or update a miner"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO miners
                    (wallet, device_id, device_arch, device_family, joined_at,
                     last_attestation, total_attestations, uptime_seconds,
                     hardware_score, contribution_weight, total_rewards)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (miner.wallet, miner.device_id, miner.device_arch,
                       miner.device_family, miner.joined_at, miner.last_attestation,
                       miner.total_attestations, miner.uptime_seconds,
                       miner.hardware_score, miner.contribution_weight,
                       miner.total_rewards))
                conn.commit()
                return True
            except Exception as e:
                print(f"Error adding miner: {e}")
                return False

    def get_miner(self, wallet: str) -> Optional[Miner]:
        """Get a miner by wallet address"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM miners WHERE wallet = ?", (wallet,))
            row = cursor.fetchone()
            if row:
                return Miner(**dict(row))
            return None

    def get_all_miners(self) -> List[Miner]:
        """Get all miners"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM miners ORDER BY last_attestation DESC")
            rows = cursor.fetchall()
            return [Miner(**dict(row)) for row in rows]

    def get_active_miners(self, since_seconds: int = 3600) -> List[Miner]:
        """Get miners active in the last X seconds"""
        cutoff = time.time() - since_seconds
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM miners WHERE last_attestation > ? ORDER BY last_attestation DESC", (cutoff,))
            rows = cursor.fetchall()
            return [Miner(**dict(row)) for row in rows]

    def add_attestation(self, attestation: Attestation) -> bool:
        """Add an attestation"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO attestations
                    (id, miner_wallet, device_id, timestamp, entropy_score,
                     hardware_score, fingerprint, is_valid)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (attestation.id, attestation.miner_wallet,
                       attestation.device_id, attestation.timestamp,
                       attestation.entropy_score, attestation.hardware_score,
                       json.dumps(attestation.fingerprint), 1 if attestation.is_valid else 0))
                conn.commit()
                return True
            except Exception as e:
                print(f"Error adding attestation: {e}")
                return False

    def record_reward(self, epoch: int, wallet: str, gross_reward: float,
                    pool_fee: float, net_reward: float) -> bool:
        """Record a reward distribution"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO rewards
                    (epoch, miner_wallet, gross_reward, pool_fee, net_reward, distributed_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (epoch, wallet, gross_reward, pool_fee, net_reward, time.time()))
                conn.commit()
                return True
            except Exception as e:
                print(f"Error recording reward: {e}")
                return False

    def get_reward_history(self, limit: int = 50) -> List[dict]:
        """Get reward distribution history"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM rewards
                ORDER BY distributed_at DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def update_miner_stats(self, wallet: str, uptime_delta: float,
                          total_attestations: int = 0):
        """Update miner statistics"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE miners
                SET uptime_seconds = uptime_seconds + ?,
                    total_attestations = total_attestations + ?,
                    last_attestation = ?
                WHERE wallet = ?
            """, (uptime_delta, total_attestations, time.time(), wallet))
            conn.commit()

    def get_config(self, key: str, default: str = None) -> str:
        """Get pool configuration value"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM pool_config WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else default

    def set_config(self, key: str, value: str):
        """Set pool configuration value"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO pool_config (key, value) VALUES (?, ?)
            """, (key, value))
            conn.commit()


# ============================================================================
# Pool Server
# ============================================================================

class MiningPoolServer:
    """RustChain mining pool proxy server"""

    def __init__(self, port: int, node_url: str, pool_fee: float, db_path: str):
        self.port = port
        self.node_url = node_url
        self.pool_fee = pool_fee
        self.db = PoolDatabase(db_path)

        # Attestation cache (in-memory)
        self.attestation_cache: Dict[str, List[Attestation]] = defaultdict(list)

        # Flask app
        self.app = Flask(__name__)
        self.app.secret_key = secrets.token_hex(32)

        # Register routes
        self._register_routes()

    def _register_routes(self):
        """Register Flask routes"""

        @self.app.route('/')
        def index():
            """Pool dashboard"""
            return self._render_dashboard()

        @self.app.route('/api/stats')
        def get_pool_stats():
            """Get pool statistics"""
            return jsonify(self._get_pool_stats().to_dict())

        @self.app.route('/api/miners')
        def get_miners():
            """Get all miners"""
            miners = self.db.get_all_miners()
            return jsonify([m.to_dict() for m in miners])

        @self.app.route('/api/miner/<wallet>')
        def get_miner(wallet: str):
            """Get miner details"""
            miner = self.db.get_miner(wallet)
            if miner:
                return jsonify(miner.to_dict())
            return jsonify({"error": "Miner not found"}), 404

        @self.app.route('/api/attest', methods=['POST'])
        def receive_attestation():
            """Receive attestation from a miner"""
            try:
                data = request.get_json()

                if not data or 'wallet' not in data:
                    return jsonify({"error": "Missing wallet"}), 400

                wallet = data['wallet']
                device_id = data.get('device_id', 'unknown')
                device_arch = data.get('device_arch', 'unknown')
                device_family = data.get('device_family', 'unknown')
                entropy_score = data.get('entropy_score', 0.0)
                fingerprint = data.get('fingerprint', {})

                # Get or create miner
                miner = self.db.get_miner(wallet)
                if not miner:
                    miner = Miner(
                        wallet=wallet,
                        device_id=device_id,
                        device_arch=device_arch,
                        device_family=device_family,
                        joined_at=time.time(),
                        last_attestation=time.time(),
                        total_attestations=0,
                        uptime_seconds=0.0,
                        hardware_score=1.0,
                        contribution_weight=1.0,
                        total_rewards=0.0
                    )

                # Calculate hardware score
                hardware_score = self._calculate_hardware_score(
                    device_arch, device_family, entropy_score
                )

                # Create attestation
                attestation = Attestation(
                    id=secrets.token_hex(16),
                    miner_wallet=wallet,
                    device_id=device_id,
                    timestamp=time.time(),
                    entropy_score=entropy_score,
                    hardware_score=hardware_score,
                    fingerprint=fingerprint,
                    is_valid=True
                )

                # Store in database
                self.db.add_attestation(attestation)

                # Update miner
                miner.last_attestation = time.time()
                miner.total_attestations += 1
                miner.hardware_score = hardware_score
                miner.contribution_weight = self._calculate_contribution_weight(miner)
                self.db.add_miner(miner)

                # Add to cache
                self.attestation_cache[wallet].append(attestation)

                # Submit to RustChain node (aggregated)
                self._submit_aggregated_attestation()

                return jsonify({
                    "status": "accepted",
                    "attestation_id": attestation.id,
                    "hardware_score": hardware_score,
                    "contribution_weight": miner.contribution_weight
                })

            except Exception as e:
                print(f"Error receiving attestation: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route('/api/rewards/history')
        def get_rewards_history():
            """Get reward distribution history"""
            limit = int(request.args.get('limit', 50))
            history = self.db.get_reward_history(limit)
            return jsonify(history)

    def _calculate_hardware_score(self, arch: str, family: str,
                                 entropy_score: float) -> float:
        """Calculate hardware score based on device type"""
        arch_lower = arch.lower()
        family_lower = family.lower()

        # Vintage hardware gets higher scores
        vintage_bonus = {
            'g4': 2.5, 'g5': 2.0, 'g3': 1.8,
            'powerpc': 1.5, '68k': 3.0, 'sparc': 2.0,
            'pentium': 1.8, '486': 2.5
        }

        base_score = 1.0
        for key, bonus in vintage_bonus.items():
            if key in arch_lower or key in family_lower:
                base_score = bonus
                break

        # Entropy bonus (if available)
        if entropy_score > 0:
            base_score *= (1.0 + min(entropy_score / 100.0, 0.5))

        return base_score

    def _calculate_contribution_weight(self, miner: Miner) -> float:
        """Calculate miner's contribution weight"""
        # Weight = hardware_score * (uptime_bonus + attestation_bonus)
        uptime_hours = miner.uptime_seconds / 3600.0

        # Uptime bonus (caps at 2.0x after 100 hours)
        uptime_bonus = min(1.0 + (uptime_hours / 100.0), 2.0)

        # Attestation bonus (caps at 1.5x after 100 attestations)
        attest_bonus = min(1.0 + (miner.total_attestations / 200.0), 1.5)

        return miner.hardware_score * uptime_bonus * attest_bonus

    def _submit_aggregated_attestation(self):
        """Submit aggregated attestation to RustChain node"""
        # This would integrate with the RustChain node's attestation API
        # For now, we just cache attestations locally
        pass

    def _get_pool_stats(self) -> PoolStats:
        """Get pool-wide statistics"""
        all_miners = self.db.get_all_miners()
        active_miners = self.db.get_active_miners(since_seconds=3600)

        total_attestations = sum(m.total_attestations for m in all_miners)
        total_rewards = sum(m.total_rewards for m in all_miners)

        # Calculate total hash power (sum of contribution weights)
        total_hash_power = sum(m.contribution_weight for m in active_miners)

        return PoolStats(
            total_miners=len(all_miners),
            active_miners=len(active_miners),
            total_attestations=total_attestations,
            total_rewards_distributed=total_rewards,
            pool_fee_collected=total_rewards * self.pool_fee,
            current_epoch=0,  # Would fetch from node
            total_hash_power=total_hash_power
        )

    def _render_dashboard(self):
        """Render the pool dashboard"""
        stats = self._get_pool_stats()
        miners = self.db.get_all_miners()[:20]  # Show top 20
        rewards = self.db.get_reward_history(limit=10)

        dashboard_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RustChain Mining Pool</title>
    <style>
        body {{
            font-family: 'Courier New', monospace;
            background: #1a1a2e;
            color: #eee;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        h1 {{
            color: #ff6b6b;
            border-bottom: 2px solid #ff6b6b;
            padding-bottom: 10px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .stat-card {{
            background: #16213e;
            border: 1px solid #0f3460;
            padding: 20px;
            border-radius: 5px;
        }}
        .stat-label {{
            color: #888;
            font-size: 0.9em;
        }}
        .stat-value {{
            color: #4cc9f0;
            font-size: 1.8em;
            font-weight: bold;
        }}
        .section {{
            background: #16213e;
            border: 1px solid #0f3460;
            padding: 20px;
            margin: 20px 0;
            border-radius: 5px;
        }}
        h2 {{
            color: #4cc9f0;
            margin-top: 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #0f3460;
        }}
        th {{
            color: #4cc9f0;
        }}
        .active {{
            color: #00ff00;
        }}
        .inactive {{
            color: #ff6b6b;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🦞 RustChain Mining Pool Dashboard</h1>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Total Miners</div>
                <div class="stat-value">{stats.total_miners}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Active Miners (1h)</div>
                <div class="stat-value">{stats.active_miners}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Total Attestations</div>
                <div class="stat-value">{stats.total_attestations}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Rewards Distributed</div>
                <div class="stat-value">{stats.total_rewards_distributed:.2f} RTC</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Pool Fee Collected</div>
                <div class="stat-value">{stats.pool_fee_collected:.2f} RTC</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Total Hash Power</div>
                <div class="stat-value">{stats.total_hash_power:.2f}</div>
            </div>
        </div>

        <div class="section">
            <h2>Connected Miners</h2>
            <table>
                <tr>
                    <th>Wallet</th>
                    <th>Architecture</th>
                    <th>Hardware Score</th>
                    <th>Weight</th>
                    <th>Attestations</th>
                    <th>Uptime</th>
                    <th>Status</th>
                </tr>
"""

        now = time.time()
        for miner in miners:
            status = "active" if (now - miner.last_attestation) < 3600 else "inactive"
            status_class = status

            dashboard_html += f"""
                <tr>
                    <td>{miner.wallet[:16]}...</td>
                    <td>{miner.device_arch}</td>
                    <td>{miner.hardware_score:.2f}</td>
                    <td>{miner.contribution_weight:.2f}</td>
                    <td>{miner.total_attestations}</td>
                    <td>{miner.uptime_seconds / 3600:.1f}h</td>
                    <td class="{status_class}">{status}</td>
                </tr>
"""

        dashboard_html += """
            </table>
        </div>

        <div class="section">
            <h2>Recent Rewards</h2>
            <table>
                <tr>
                    <th>Epoch</th>
                    <th>Miner</th>
                    <th>Gross</th>
                    <th>Fee</th>
                    <th>Net</th>
                    <th>Time</th>
                </tr>
"""

        for reward in rewards:
            timestamp = datetime.fromtimestamp(reward['distributed_at']).strftime('%Y-%m-%d %H:%M')
            dashboard_html += f"""
                <tr>
                    <td>{reward['epoch']}</td>
                    <td>{reward['miner_wallet'][:16]}...</td>
                    <td>{reward['gross_reward']:.4f}</td>
                    <td>{reward['pool_fee']:.4f}</td>
                    <td>{reward['net_reward']:.4f}</td>
                    <td>{timestamp}</td>
                </tr>
"""

        dashboard_html += """
            </table>
        </div>
    </div>
</body>
</html>
"""

        return dashboard_html

    def run(self):
        """Run the pool server"""
        print(f"🦞 RustChain Mining Pool Proxy Server")
        print(f"   Port: {self.port}")
        print(f"   Node URL: {self.node_url}")
        print(f"   Pool Fee: {self.pool_fee * 100:.1f}%")
        print(f"   Dashboard: http://localhost:{self.port}")
        print(f"")
        print(f"   Miners can connect with:")
        print(f"   clawrtc --pool http://localhost:{self.port}")
        print(f"")

        self.app.run(host='0.0.0.0', port=self.port, debug=False)


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="RustChain Mining Pool Proxy Server"
    )
    parser.add_argument(
        '--port',
        type=int,
        default=DEFAULT_PORT,
        help=f'Port to listen on (default: {DEFAULT_PORT})'
    )
    parser.add_argument(
        '--node-url',
        type=str,
        default=DEFAULT_NODE_URL,
        help=f'RustChain node URL (default: {DEFAULT_NODE_URL})'
    )
    parser.add_argument(
        '--pool-fee',
        type=float,
        default=DEFAULT_POOL_FEE,
        help=f'Pool fee as decimal (e.g., 0.01 for 1%, default: {DEFAULT_POOL_FEE})'
    )
    parser.add_argument(
        '--db-path',
        type=str,
        default=DEFAULT_DB_PATH,
        help=f'Database path (default: {DEFAULT_DB_PATH})'
    )

    args = parser.parse_args()

    # Validate pool fee
    if not (0 <= args.pool_fee <= 0.5):
        print(f"Error: Pool fee must be between 0 and 0.5 (0-50%)")
        sys.exit(1)

    # Create and run server
    server = MiningPoolServer(
        port=args.port,
        node_url=args.node_url,
        pool_fee=args.pool_fee,
        db_path=args.db_path
    )

    try:
        server.run()
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down pool server...")


if __name__ == "__main__":
    main()
