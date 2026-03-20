// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import argparse
import sys
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

DB_PATH = 'rustchain.db'

class PoolCLI:
    def __init__(self):
        self.ensure_pool_tables()

    def ensure_pool_tables(self):
        """Initialize pool-related database tables if they don't exist"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Pool configuration table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pool_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Pool statistics table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pool_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_miners INTEGER DEFAULT 0,
                    active_miners INTEGER DEFAULT 0,
                    total_hashrate REAL DEFAULT 0.0,
                    blocks_found INTEGER DEFAULT 0,
                    total_shares INTEGER DEFAULT 0,
                    pool_fee REAL DEFAULT 0.0
                )
            ''')

            # Miner shares tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS miner_shares (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    miner_address TEXT NOT NULL,
                    shares INTEGER DEFAULT 0,
                    difficulty REAL DEFAULT 0.0,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    block_height INTEGER DEFAULT 0
                )
            ''')

            # Payout history
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS payout_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    miner_address TEXT NOT NULL,
                    amount REAL NOT NULL,
                    transaction_hash TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP
                )
            ''')

            conn.commit()

    def set_config(self, key: str, value: str):
        """Set pool configuration value"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO pool_config (key, value, updated_at)
                VALUES (?, ?, ?)
            ''', (key, value, datetime.now().isoformat()))
            conn.commit()
        print(f"Set {key} = {value}")

    def get_config(self, key: str) -> Optional[str]:
        """Get pool configuration value"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM pool_config WHERE key = ?', (key,))
            result = cursor.fetchone()
            return result[0] if result else None

    def show_config(self):
        """Display all pool configuration"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT key, value, updated_at FROM pool_config ORDER BY key')
            configs = cursor.fetchall()

            if not configs:
                print("No configuration found")
                return

            print("Pool Configuration:")
            print("-" * 50)
            for key, value, updated in configs:
                print(f"{key:<20}: {value} (updated: {updated})")

    def show_stats(self, hours: int = 24):
        """Show pool statistics for the last N hours"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Get latest stats
            cursor.execute('''
                SELECT * FROM pool_stats
                ORDER BY timestamp DESC LIMIT 1
            ''')
            latest = cursor.fetchone()

            if not latest:
                print("No pool statistics available")
                return

            # Get stats from N hours ago
            cutoff = datetime.now() - timedelta(hours=hours)
            cursor.execute('''
                SELECT AVG(total_hashrate), SUM(blocks_found), COUNT(*) as entries
                FROM pool_stats
                WHERE timestamp >= ?
            ''', (cutoff.isoformat(),))
            period_stats = cursor.fetchone()

            print(f"Pool Statistics (last {hours} hours):")
            print("-" * 40)
            print(f"Active Miners     : {latest[3]}")
            print(f"Total Miners      : {latest[2]}")
            print(f"Current Hashrate  : {latest[4]:.2f} H/s")
            print(f"Average Hashrate  : {period_stats[0]:.2f} H/s" if period_stats[0] else "0.00 H/s")
            print(f"Blocks Found      : {period_stats[1] or 0}")
            print(f"Pool Fee          : {latest[6]:.2f}%")
            print(f"Total Shares      : {latest[5]}")

    def show_miners(self, limit: int = 20):
        """Show top miners by shares"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT miner_address, SUM(shares) as total_shares,
                       COUNT(*) as submissions, MAX(timestamp) as last_seen
                FROM miner_shares
                GROUP BY miner_address
                ORDER BY total_shares DESC
                LIMIT ?
            ''', (limit,))

            miners = cursor.fetchall()

            if not miners:
                print("No miners found")
                return

            print(f"Top {limit} Miners:")
            print("-" * 80)
            print(f"{'Address':<42} {'Shares':<10} {'Submissions':<12} {'Last Seen':<15}")
            print("-" * 80)

            for address, shares, subs, last_seen in miners:
                short_addr = f"{address[:8]}...{address[-8:]}" if len(address) > 20 else address
                print(f"{short_addr:<42} {shares:<10} {subs:<12} {last_seen[:10]:<15}")

    def process_payouts(self, min_amount: float = 1.0, dry_run: bool = False):
        """Process pending payouts for miners"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Calculate earnings per miner based on shares
            cursor.execute('''
                SELECT miner_address, SUM(shares) as total_shares
                FROM miner_shares
                WHERE timestamp >= datetime('now', '-24 hours')
                GROUP BY miner_address
                HAVING total_shares > 0
            ''')

            miner_shares = cursor.fetchall()

            if not miner_shares:
                print("No shares found for payout calculation")
                return

            # Get pool fee
            pool_fee = float(self.get_config('pool_fee') or '2.5')

            # Mock reward calculation (in a real pool, this would come from found blocks)
            total_reward = 10.0  # Example: 10 RTC found in last 24h
            total_shares = sum(shares for _, shares in miner_shares)

            payouts_processed = 0
            total_paid = 0.0

            print("Processing Payouts:")
            print("-" * 60)

            for miner_addr, shares in miner_shares:
                share_percent = shares / total_shares
                gross_amount = total_reward * share_percent
                net_amount = gross_amount * (1 - pool_fee / 100)

                if net_amount >= min_amount:
                    if not dry_run:
                        # Record payout in database
                        cursor.execute('''
                            INSERT INTO payout_history
                            (miner_address, amount, status, created_at)
                            VALUES (?, ?, 'pending', ?)
                        ''', (miner_addr, net_amount, datetime.now().isoformat()))

                    short_addr = f"{miner_addr[:8]}...{miner_addr[-8:]}"
                    print(f"{short_addr} - {net_amount:.6f} RTC ({'DRY RUN' if dry_run else 'QUEUED'})")
                    payouts_processed += 1
                    total_paid += net_amount

            if not dry_run:
                conn.commit()

            print("-" * 60)
            print(f"Payouts processed: {payouts_processed}")
            print(f"Total amount: {total_paid:.6f} RTC")
            print(f"Pool fee collected: {total_reward * (pool_fee / 100):.6f} RTC")

    def show_payouts(self, limit: int = 20):
        """Show recent payout history"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT miner_address, amount, status, created_at, processed_at
                FROM payout_history
                ORDER BY created_at DESC
                LIMIT ?
            ''', (limit,))

            payouts = cursor.fetchall()

            if not payouts:
                print("No payout history found")
                return

            print(f"Recent Payouts (last {limit}):")
            print("-" * 80)
            print(f"{'Address':<42} {'Amount':<12} {'Status':<10} {'Created':<15}")
            print("-" * 80)

            for addr, amount, status, created, processed in payouts:
                short_addr = f"{addr[:8]}...{addr[-8:]}" if len(addr) > 20 else addr
                print(f"{short_addr:<42} {amount:<12.6f} {status:<10} {created[:10]:<15}")

def main():
    parser = argparse.ArgumentParser(description='RustChain Mining Pool CLI')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Config commands
    config_parser = subparsers.add_parser('config', help='Manage pool configuration')
    config_subparsers = config_parser.add_subparsers(dest='config_action')

    set_parser = config_subparsers.add_parser('set', help='Set configuration value')
    set_parser.add_argument('key', help='Configuration key')
    set_parser.add_argument('value', help='Configuration value')

    config_subparsers.add_parser('show', help='Show all configuration')

    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show pool statistics')
    stats_parser.add_argument('--hours', type=int, default=24, help='Hours to look back (default: 24)')

    # Miners command
    miners_parser = subparsers.add_parser('miners', help='Show miner information')
    miners_parser.add_argument('--limit', type=int, default=20, help='Number of miners to show (default: 20)')

    # Payout commands
    payout_parser = subparsers.add_parser('payout', help='Manage payouts')
    payout_subparsers = payout_parser.add_subparsers(dest='payout_action')

    process_parser = payout_subparsers.add_parser('process', help='Process pending payouts')
    process_parser.add_argument('--min-amount', type=float, default=1.0, help='Minimum payout amount (default: 1.0)')
    process_parser.add_argument('--dry-run', action='store_true', help='Show what would be paid without processing')

    history_parser = payout_subparsers.add_parser('history', help='Show payout history')
    history_parser.add_argument('--limit', type=int, default=20, help='Number of payouts to show (default: 20)')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    cli = PoolCLI()

    try:
        if args.command == 'config':
            if args.config_action == 'set':
                cli.set_config(args.key, args.value)
            elif args.config_action == 'show':
                cli.show_config()
            else:
                config_parser.print_help()

        elif args.command == 'stats':
            cli.show_stats(args.hours)

        elif args.command == 'miners':
            cli.show_miners(args.limit)

        elif args.command == 'payout':
            if args.payout_action == 'process':
                cli.process_payouts(args.min_amount, args.dry_run)
            elif args.payout_action == 'history':
                cli.show_payouts(args.limit)
            else:
                payout_parser.print_help()

        else:
            parser.print_help()

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
