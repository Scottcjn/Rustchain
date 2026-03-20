// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import json
import os
import sys
import argparse
import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

DB_PATH = "rustchain.db"
FIXTURES_DIR = "epoch_fixtures"
RESULTS_DIR = "replay_results"

class EpochDeterminismSimulator:
    def __init__(self):
        self.fixture_data = {}
        self.node_results = {}
        self.comparison_report = {}

    def initialize_db(self, node_id: str):
        """Initialize database for a specific node simulation"""
        node_db = f"node_{node_id}_replay.db"
        with sqlite3.connect(node_db) as conn:
            cursor = conn.cursor()

            # Create tables for epoch simulation
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS epoch_state (
                    epoch_id INTEGER PRIMARY KEY,
                    start_time INTEGER,
                    end_time INTEGER,
                    config_hash TEXT,
                    status TEXT DEFAULT 'pending'
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS attestations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    epoch_id INTEGER,
                    node_address TEXT,
                    signature TEXT,
                    stake_amount INTEGER,
                    timestamp INTEGER,
                    FOREIGN KEY (epoch_id) REFERENCES epoch_state(epoch_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS enrollments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    epoch_id INTEGER,
                    validator_address TEXT,
                    public_key TEXT,
                    stake_proof TEXT,
                    enrollment_fee INTEGER,
                    FOREIGN KEY (epoch_id) REFERENCES epoch_state(epoch_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reward_calculations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    epoch_id INTEGER,
                    validator_address TEXT,
                    base_reward INTEGER,
                    multiplier_bonus INTEGER,
                    final_payout INTEGER,
                    calculation_hash TEXT,
                    FOREIGN KEY (epoch_id) REFERENCES epoch_state(epoch_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settlement_outputs (
                    epoch_id INTEGER PRIMARY KEY,
                    total_rewards INTEGER,
                    validator_count INTEGER,
                    settlement_hash TEXT,
                    merkle_root TEXT,
                    finalized_at INTEGER,
                    FOREIGN KEY (epoch_id) REFERENCES epoch_state(epoch_id)
                )
            """)

            conn.commit()

    def load_epoch_fixture(self, fixture_path: str) -> Dict:
        """Load epoch fixture data from JSON file"""
        try:
            with open(fixture_path, 'r') as f:
                fixture = json.load(f)

            required_fields = ['epoch_id', 'attestations', 'enrollments', 'config']
            for field in required_fields:
                if field not in fixture:
                    raise ValueError(f"Missing required field: {field}")

            self.fixture_data = fixture
            return fixture

        except FileNotFoundError:
            raise FileNotFoundError(f"Fixture file not found: {fixture_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in fixture: {e}")

    def create_sample_fixture(self, epoch_id: int, output_path: str):
        """Create a sample epoch fixture for testing"""
        fixture = {
            "epoch_id": epoch_id,
            "start_time": int(time.time()) - 3600,
            "end_time": int(time.time()),
            "config": {
                "base_reward": 1000,
                "stake_multiplier": 1.5,
                "min_stake": 100,
                "validator_limit": 50
            },
            "attestations": [
                {
                    "node_address": f"addr_{i}",
                    "signature": f"sig_{i}_{epoch_id}",
                    "stake_amount": 500 + (i * 50),
                    "timestamp": int(time.time()) - (i * 60)
                }
                for i in range(10)
            ],
            "enrollments": [
                {
                    "validator_address": f"validator_{i}",
                    "public_key": f"pubkey_{i}_{epoch_id}",
                    "stake_proof": f"proof_{i}",
                    "enrollment_fee": 50
                }
                for i in range(5)
            ]
        }

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(fixture, f, indent=2)

        print(f"Sample fixture created: {output_path}")

    def replay_epoch_on_node(self, node_id: str, fixture_data: Dict) -> Dict:
        """Replay epoch processing on a specific node"""
        node_db = f"node_{node_id}_replay.db"
        epoch_id = fixture_data['epoch_id']

        with sqlite3.connect(node_db) as conn:
            cursor = conn.cursor()

            # Insert epoch state
            config_hash = hashlib.sha256(
                json.dumps(fixture_data['config'], sort_keys=True).encode()
            ).hexdigest()

            cursor.execute("""
                INSERT OR REPLACE INTO epoch_state
                (epoch_id, start_time, end_time, config_hash, status)
                VALUES (?, ?, ?, ?, 'processing')
            """, (
                epoch_id,
                fixture_data.get('start_time', int(time.time()) - 3600),
                fixture_data.get('end_time', int(time.time())),
                config_hash
            ))

            # Clear existing data for this epoch
            cursor.execute("DELETE FROM attestations WHERE epoch_id = ?", (epoch_id,))
            cursor.execute("DELETE FROM enrollments WHERE epoch_id = ?", (epoch_id,))
            cursor.execute("DELETE FROM reward_calculations WHERE epoch_id = ?", (epoch_id,))

            # Insert attestations
            for att in fixture_data['attestations']:
                cursor.execute("""
                    INSERT INTO attestations
                    (epoch_id, node_address, signature, stake_amount, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    epoch_id,
                    att['node_address'],
                    att['signature'],
                    att['stake_amount'],
                    att['timestamp']
                ))

            # Insert enrollments
            for enr in fixture_data['enrollments']:
                cursor.execute("""
                    INSERT INTO enrollments
                    (epoch_id, validator_address, public_key, stake_proof, enrollment_fee)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    epoch_id,
                    enr['validator_address'],
                    enr['public_key'],
                    enr['stake_proof'],
                    enr['enrollment_fee']
                ))

            # Calculate rewards (simplified algorithm)
            config = fixture_data['config']
            base_reward = config['base_reward']
            multiplier = config.get('stake_multiplier', 1.0)

            total_rewards = 0
            validator_count = 0

            for att in fixture_data['attestations']:
                # Simple reward calculation
                stake_bonus = int(att['stake_amount'] * (multiplier - 1.0))
                final_payout = base_reward + stake_bonus
                total_rewards += final_payout
                validator_count += 1

                calc_data = f"{att['node_address']}:{base_reward}:{stake_bonus}:{final_payout}"
                calc_hash = hashlib.sha256(calc_data.encode()).hexdigest()

                cursor.execute("""
                    INSERT INTO reward_calculations
                    (epoch_id, validator_address, base_reward, multiplier_bonus, final_payout, calculation_hash)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    epoch_id,
                    att['node_address'],
                    base_reward,
                    stake_bonus,
                    final_payout,
                    calc_hash
                ))

            # Create settlement hash
            settlement_data = f"{epoch_id}:{total_rewards}:{validator_count}:{config_hash}"
            settlement_hash = hashlib.sha256(settlement_data.encode()).hexdigest()

            # Generate merkle root (simplified)
            reward_hashes = []
            cursor.execute("SELECT calculation_hash FROM reward_calculations WHERE epoch_id = ?", (epoch_id,))
            for row in cursor.fetchall():
                reward_hashes.append(row[0])

            merkle_root = hashlib.sha256(''.join(sorted(reward_hashes)).encode()).hexdigest()

            # Insert settlement output
            cursor.execute("""
                INSERT OR REPLACE INTO settlement_outputs
                (epoch_id, total_rewards, validator_count, settlement_hash, merkle_root, finalized_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                epoch_id,
                total_rewards,
                validator_count,
                settlement_hash,
                merkle_root,
                int(time.time())
            ))

            # Update epoch status
            cursor.execute("""
                UPDATE epoch_state SET status = 'finalized' WHERE epoch_id = ?
            """, (epoch_id,))

            conn.commit()

        # Return results summary
        return {
            'node_id': node_id,
            'epoch_id': epoch_id,
            'total_rewards': total_rewards,
            'validator_count': validator_count,
            'settlement_hash': settlement_hash,
            'merkle_root': merkle_root,
            'config_hash': config_hash
        }

    def compare_node_results(self, results: List[Dict]) -> Dict:
        """Compare results from multiple nodes"""
        if len(results) < 2:
            return {'error': 'Need at least 2 node results for comparison'}

        comparison = {
            'deterministic': True,
            'epoch_id': results[0]['epoch_id'],
            'nodes_compared': len(results),
            'differences': [],
            'consensus_fields': {},
            'timestamp': datetime.now().isoformat()
        }

        # Compare each field across all nodes
        fields_to_compare = ['total_rewards', 'validator_count', 'settlement_hash', 'merkle_root', 'config_hash']
        base_result = results[0]

        for field in fields_to_compare:
            values = [r[field] for r in results]
            unique_values = set(values)

            if len(unique_values) == 1:
                comparison['consensus_fields'][field] = {
                    'status': 'consensus',
                    'value': list(unique_values)[0]
                }
            else:
                comparison['deterministic'] = False
                comparison['consensus_fields'][field] = {
                    'status': 'divergent',
                    'values': {r['node_id']: r[field] for r in results}
                }
                comparison['differences'].append({
                    'field': field,
                    'node_values': {r['node_id']: r[field] for r in results}
                })

        return comparison

    def generate_report(self, comparison: Dict, output_format: str = 'human') -> str:
        """Generate comparison report in specified format"""
        if output_format == 'json':
            return json.dumps(comparison, indent=2)

        # Human readable format
        report = []
        report.append("=== EPOCH DETERMINISM REPORT ===")
        report.append(f"Epoch ID: {comparison['epoch_id']}")
        report.append(f"Nodes Compared: {comparison['nodes_compared']}")
        report.append(f"Deterministic: {'YES' if comparison['deterministic'] else 'NO'}")
        report.append(f"Generated: {comparison['timestamp']}")
        report.append("")

        if comparison['deterministic']:
            report.append("✅ All nodes produced identical results!")
            report.append("\nConsensus Values:")
            for field, data in comparison['consensus_fields'].items():
                report.append(f"  {field}: {data['value']}")
        else:
            report.append("❌ Nodes produced different results!")
            report.append(f"\nFound {len(comparison['differences'])} differences:")

            for diff in comparison['differences']:
                report.append(f"\n• {diff['field']}:")
                for node_id, value in diff['node_values'].items():
                    report.append(f"    {node_id}: {value}")

        return "\n".join(report)

    def run_simulation(self, fixture_path: str, node_ids: List[str], output_dir: str = RESULTS_DIR):
        """Run complete simulation across multiple nodes"""
        # Load fixture
        fixture_data = self.load_epoch_fixture(fixture_path)
        epoch_id = fixture_data['epoch_id']

        print(f"Loading fixture for epoch {epoch_id}...")

        # Initialize databases for each node
        results = []
        for node_id in node_ids:
            print(f"Initializing node {node_id}...")
            self.initialize_db(node_id)

            print(f"Replaying epoch on node {node_id}...")
            node_result = self.replay_epoch_on_node(node_id, fixture_data)
            results.append(node_result)

        # Compare results
        print("Comparing node results...")
        comparison = self.compare_node_results(results)

        # Generate reports
        os.makedirs(output_dir, exist_ok=True)

        # Human readable report
        human_report = self.generate_report(comparison, 'human')
        human_path = os.path.join(output_dir, f"epoch_{epoch_id}_comparison.txt")
        with open(human_path, 'w') as f:
            f.write(human_report)

        # Machine readable report
        json_report = self.generate_report(comparison, 'json')
        json_path = os.path.join(output_dir, f"epoch_{epoch_id}_comparison.json")
        with open(json_path, 'w') as f:
            f.write(json_report)

        print(f"\nReports generated:")
        print(f"  Human readable: {human_path}")
        print(f"  Machine readable: {json_path}")
        print(f"\nDeterministic: {'YES' if comparison['deterministic'] else 'NO'}")

        return comparison

def main():
    parser = argparse.ArgumentParser(description="Epoch Determinism Simulator")
    parser.add_argument('command', choices=['create-fixture', 'simulate', 'compare'],
                       help='Command to execute')
    parser.add_argument('--fixture', '-f', help='Path to epoch fixture file')
    parser.add_argument('--epoch-id', '-e', type=int, help='Epoch ID for fixture creation')
    parser.add_argument('--nodes', '-n', nargs='+', default=['node1', 'node2'],
                       help='Node IDs to simulate')
    parser.add_argument('--output-dir', '-o', default=RESULTS_DIR,
                       help='Output directory for results')
    parser.add_argument('--ci-mode', action='store_true',
                       help='Exit with error code if not deterministic')

    args = parser.parse_args()

    simulator = EpochDeterminismSimulator()

    try:
        if args.command == 'create-fixture':
            if not args.epoch_id:
                print("Error: --epoch-id required for create-fixture")
                sys.exit(1)

            os.makedirs(FIXTURES_DIR, exist_ok=True)
            fixture_path = os.path.join(FIXTURES_DIR, f"epoch_{args.epoch_id}.json")
            simulator.create_sample_fixture(args.epoch_id, fixture_path)

        elif args.command == 'simulate':
            if not args.fixture:
                print("Error: --fixture required for simulate")
                sys.exit(1)

            comparison = simulator.run_simulation(args.fixture, args.nodes, args.output_dir)

            if args.ci_mode and not comparison['deterministic']:
                print("CI MODE: Determinism check FAILED")
                sys.exit(1)

        elif args.command == 'compare':
            # For comparing existing results
            print("Direct comparison mode not yet implemented")
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
