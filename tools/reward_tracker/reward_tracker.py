#!/usr/bin/env python3
"""
RustChain Historical Reward Tracker

Store and visualize historical reward data.
"""

import sqlite3
import json
import time
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import argparse


class RewardTracker:
    """Track and analyze historical mining rewards."""
    
    def __init__(self, db_path: str = "rewards.db", node_url: str = "https://50.28.86.131"):
        self.db_path = db_path
        self.node_url = node_url
        self.conn = sqlite3.connect(db_path)
        self._init_table()
    
    def _init_table(self):
        """Create rewards history table."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS reward_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                miner_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                balance REAL NOT NULL,
                attestations INTEGER DEFAULT 0,
                hardware TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_miner_time 
            ON reward_history(miner_id, timestamp)
        """)
        self.conn.commit()
    
    def record_snapshot(self, miner_id: str) -> bool:
        """Record current reward state for a miner."""
        try:
            # Get balance
            resp = requests.get(
                f"{self.node_url}/wallet/balance",
                params={"miner_id": miner_id},
                timeout=10
            )
            
            # Get miners info
            miners_resp = requests.get(
                f"{self.node_url}/api/miners",
                timeout=10
            )
            
            if resp.status_code != 200 or miners_resp.status_code != 200:
                return False
            
            balance_data = resp.json()
            miners_data = miners_resp.json()
            
            # Find miner info
            hardware = "Unknown"
            attestations = 0
            for m in miners_data.get("miners", []):
                if m.get("miner_id") == miner_id:
                    hardware = m.get("hardware", "Unknown")
                    attestations = m.get("attestations", 0)
                    break
            
            balance = balance_data.get("balance", 0)
            
            self.conn.execute("""
                INSERT INTO reward_history (miner_id, timestamp, balance, attestations, hardware)
                VALUES (?, ?, ?, ?, ?)
            """, (miner_id, time.time(), balance, attestations, hardware))
            self.conn.commit()
            
            return True
            
        except Exception as e:
            print(f"Error recording snapshot: {e}")
            return False
    
    def get_history(self, miner_id: str, days: int = 7) -> List[Dict]:
        """Get reward history for a miner."""
        cursor = self.conn.execute("""
            SELECT timestamp, balance, attestations, hardware
            FROM reward_history
            WHERE miner_id = ? AND timestamp > ?
            ORDER BY timestamp ASC
        """, (miner_id, time.time() - days * 86400))
        
        return [
            {
                "timestamp": row[0],
                "balance": row[1],
                "attestations": row[2],
                "hardware": row[3],
                "date": datetime.fromtimestamp(row[0]).strftime("%Y-%m-%d %H:%M")
            }
            for row in cursor.fetchall()
        ]
    
    def get_statistics(self, miner_id: str) -> Dict:
        """Calculate reward statistics."""
        history = self.get_history(miner_id, days=30)
        
        if not history:
            return {}
        
        balances = [h["balance"] for h in history]
        
        # Calculate daily earnings
        daily = {}
        for h in history:
            date = h["date"].split()[0]
            if date not in daily:
                daily[date] = {"balance": h["balance"], "count": 1}
            else:
                daily[date]["balance"] = max(daily[date]["balance"], h["balance"])
        
        # Calculate averages
        earnings = []
        prev_balance = 0
        for h in sorted(history, key=lambda x: x["timestamp"]):
            if prev_balance > 0:
                earnings.append(h["balance"] - prev_balance)
            prev_balance = h["balance"]
        
        return {
            "miner_id": miner_id,
            "current_balance": balances[-1],
            "first_recorded_balance": balances[0],
            "total_earned": balances[-1] - balances[0],
            "avg_daily_earnings": sum(earnings) / len(earnings) if earnings else 0,
            "record_count": len(history),
            "hardware": history[-1]["hardware"]
        }
    
    def export_csv(self, miner_id: str, output_path: str):
        """Export history to CSV."""
        history = self.get_history(miner_id, days=365)
        
        with open(output_path, "w") as f:
            f.write("date,balance,attestations,hardware\n")
            for h in history:
                f.write(f"{h['date']},{h['balance']},{h['attestations']},{h['hardware']}\n")
        
        print(f"Exported {len(history)} records to {output_path}")
    
    def close(self):
        """Close database connection."""
        self.conn.close()


def main():
    parser = argparse.ArgumentParser(description="RustChain Reward Tracker")
    parser.add_argument("--miner", type=str, required=True, help="Miner wallet ID")
    parser.add_argument("--record", action="store_true", help="Record current snapshot")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--export", type=str, help="Export to CSV file")
    parser.add_argument("--db", type=str, default="rewards.db", help="Database path")
    args = parser.parse_args()
    
    tracker = RewardTracker(db_path=args.db)
    
    if args.record:
        success = tracker.record_snapshot(args.miner)
        if success:
            print(f"✓ Recorded snapshot for {args.miner}")
        else:
            print(f"✗ Failed to record snapshot")
    
    if args.stats:
        stats = tracker.get_statistics(args.miner)
        if stats:
            print(f"\n=== {args.miner} Statistics ===")
            print(f"Current Balance: {stats['current_balance']:.4f} RTC")
            print(f"Total Earned: {stats['total_earned']:.4f} RTC")
            print(f"Avg Daily: {stats['avg_daily_earnings']:.4f} RTC")
            print(f"Hardware: {stats['hardware']}")
            print(f"Records: {stats['record_count']}")
        else:
            print("No data found")
    
    if args.export:
        tracker.export_csv(args.miner, args.export)
    
    tracker.close()


if __name__ == "__main__":
    main()
