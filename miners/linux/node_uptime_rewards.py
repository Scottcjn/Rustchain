#!/usr/bin/env python3
"""
RustChain Node Uptime Tracking & Rewards System
================================================
- Monitors node health via /health and /p2p/health endpoints
- Tracks uptime percentage and response latency
- Distributes weekly rewards based on performance
- Run as cron job: every hour for tracking, weekly for rewards

Usage:
  python3 node_uptime_rewards.py check     # Record uptime check
  python3 node_uptime_rewards.py rewards   # Calculate and distribute weekly rewards
  python3 node_uptime_rewards.py status    # Show current node status
"""

import sqlite3
import requests
import time
import sys
import json
from datetime import datetime, timedelta

# Configuration
DB_PATH = "/root/rustchain/rustchain_v2.db"
ADMIN_KEY = "rustchain_admin_key_2025_secure64"

# Known nodes (will auto-discover from P2P)
KNOWN_NODES = [
    {"node_id": "node-primary-131", "url": "http://50.28.86.131:8099", "name": "Primary Node"},
    {"node_id": "node-secondary-153", "url": "http://50.28.86.153:8099", "name": "Secondary/Ergo Node"},
    {"node_id": "node-ryan-245", "url": "http://76.8.228.245:8099", "name": "Ryan's Factorio Node"},
]

# Reward configuration
WEEKLY_BASE_REWARD = 10.0      # RTC per week for 95%+ uptime
LATENCY_BONUS = 2.0           # RTC bonus for <100ms average latency
P2P_SYNC_BONUS = 3.0          # RTC bonus for running P2P gossip sync
EARLY_ADOPTER_MULTIPLIER = 2  # 2x for first 10 nodes
MIN_UPTIME_FOR_REWARD = 0.80  # Minimum 80% uptime to get any reward
REWARD_SOURCE = "founder_community"  # Fund that pays node rewards

def init_uptime_tables():
    """Create uptime tracking tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Node registration table
    c.execute("""
        CREATE TABLE IF NOT EXISTS node_registry (
            node_id TEXT PRIMARY KEY,
            wallet_address TEXT NOT NULL,
            url TEXT NOT NULL,
            name TEXT,
            registered_at INTEGER NOT NULL,
            is_active INTEGER DEFAULT 1
        )
    """)

    # Uptime check records
    c.execute("""
        CREATE TABLE IF NOT EXISTS node_uptime_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id TEXT NOT NULL,
            check_time INTEGER NOT NULL,
            is_up INTEGER NOT NULL,
            latency_ms INTEGER,
            health_response TEXT,
            p2p_active INTEGER DEFAULT 0
        )
    """)

    # Weekly reward history
    c.execute("""
        CREATE TABLE IF NOT EXISTS node_rewards_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id TEXT NOT NULL,
            wallet_address TEXT NOT NULL,
            week_start INTEGER NOT NULL,
            week_end INTEGER NOT NULL,
            uptime_percent REAL NOT NULL,
            avg_latency_ms REAL,
            checks_total INTEGER,
            checks_passed INTEGER,
            p2p_bonus INTEGER DEFAULT 0,
            reward_rtc REAL NOT NULL,
            paid_at INTEGER
        )
    """)

    conn.commit()
    conn.close()
    print("[NodeUptime] Tables initialized")

def register_node(node_id: str, wallet_address: str, url: str, name: str = None):
    """Register a new node for uptime tracking."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        INSERT OR REPLACE INTO node_registry (node_id, wallet_address, url, name, registered_at, is_active)
        VALUES (?, ?, ?, ?, ?, 1)
    """, (node_id, wallet_address, url, name or node_id, int(time.time())))

    conn.commit()
    conn.close()
    print(f"[NodeUptime] Registered node: {node_id} -> {wallet_address}")

def check_node_health(url: str, timeout: int = 10) -> tuple:
    """
    Check node health and measure latency.
    Returns (is_up, latency_ms, health_data, p2p_active)
    """
    is_up = False
    latency_ms = None
    health_data = None
    p2p_active = False

    try:
        # Check /health endpoint
        start = time.time()
        resp = requests.get(f"{url}/health", timeout=timeout)
        latency_ms = int((time.time() - start) * 1000)

        if resp.status_code == 200:
            is_up = True
            health_data = resp.json()

            # Check /p2p/health for P2P sync bonus
            try:
                p2p_resp = requests.get(f"{url}/p2p/health", timeout=5)
                if p2p_resp.status_code == 200:
                    p2p_data = p2p_resp.json()
                    if p2p_data.get("gossip_enabled") or p2p_data.get("peers_connected", 0) > 0:
                        p2p_active = True
            except:
                pass

    except requests.exceptions.Timeout:
        pass
    except requests.exceptions.ConnectionError:
        pass
    except Exception as e:
        print(f"[NodeUptime] Error checking {url}: {e}")

    return is_up, latency_ms, health_data, p2p_active

def record_uptime_check(node_id: str, url: str):
    """Record a single uptime check for a node."""
    is_up, latency_ms, health_data, p2p_active = check_node_health(url)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        INSERT INTO node_uptime_checks (node_id, check_time, is_up, latency_ms, health_response, p2p_active)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        node_id,
        int(time.time()),
        1 if is_up else 0,
        latency_ms,
        json.dumps(health_data) if health_data else None,
        1 if p2p_active else 0
    ))

    conn.commit()
    conn.close()

    status = "UP" if is_up else "DOWN"
    latency_str = f"{latency_ms}ms" if latency_ms else "N/A"
    p2p_str = "+P2P" if p2p_active else ""
    print(f"[NodeUptime] {node_id}: {status} {latency_str} {p2p_str}")

    return is_up

def check_all_nodes():
    """Run uptime check on all registered nodes."""
    init_uptime_tables()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Get all active nodes
    c.execute("SELECT node_id, url FROM node_registry WHERE is_active = 1")
    nodes = c.fetchall()
    conn.close()

    if not nodes:
        # Register known nodes if none exist
        print("[NodeUptime] No nodes registered, adding known nodes...")
        for node in KNOWN_NODES:
            # Generate wallet from node_id
            import hashlib
            wallet_hash = hashlib.sha256(f"node-wallet-{node['node_id']}".encode()).hexdigest()[:40]
            wallet = f"{wallet_hash}RTC"
            register_node(node["node_id"], wallet, node["url"], node["name"])

        # Reload
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT node_id, url FROM node_registry WHERE is_active = 1")
        nodes = c.fetchall()
        conn.close()

    print(f"\n[NodeUptime] Checking {len(nodes)} nodes...")
    results = []
    for node_id, url in nodes:
        is_up = record_uptime_check(node_id, url)
        results.append((node_id, is_up))

    up_count = sum(1 for _, up in results if up)
    print(f"\n[NodeUptime] Results: {up_count}/{len(results)} nodes UP")

def calculate_weekly_rewards():
    """Calculate and distribute weekly rewards based on uptime."""
    init_uptime_tables()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Time range: last 7 days
    now = int(time.time())
    week_ago = now - (7 * 24 * 60 * 60)

    # Get all active nodes
    c.execute("SELECT node_id, wallet_address, name FROM node_registry WHERE is_active = 1")
    nodes = c.fetchall()

    print(f"\n{'='*60}")
    print(f"RustChain Node Rewards - Week ending {datetime.now().strftime('%Y-%m-%d')}")
    print(f"{'='*60}\n")

    total_rewards = 0.0
    reward_entries = []

    for node_id, wallet_address, name in nodes:
        # Get uptime stats for this node
        c.execute("""
            SELECT
                COUNT(*) as total_checks,
                SUM(is_up) as up_checks,
                AVG(CASE WHEN is_up = 1 THEN latency_ms END) as avg_latency,
                SUM(p2p_active) as p2p_checks
            FROM node_uptime_checks
            WHERE node_id = ? AND check_time >= ?
        """, (node_id, week_ago))

        row = c.fetchone()
        total_checks, up_checks, avg_latency, p2p_checks = row

        if not total_checks or total_checks == 0:
            print(f"  {name}: No checks recorded this week")
            continue

        uptime_percent = (up_checks or 0) / total_checks
        avg_latency = avg_latency or 999
        p2p_active = (p2p_checks or 0) > (total_checks * 0.5)  # P2P in >50% of checks

        # Calculate reward
        reward = 0.0
        breakdown = []

        if uptime_percent >= MIN_UPTIME_FOR_REWARD:
            # Base reward scaled by uptime
            if uptime_percent >= 0.95:
                reward = WEEKLY_BASE_REWARD
                breakdown.append(f"Base: {WEEKLY_BASE_REWARD} RTC (95%+ uptime)")
            else:
                # Partial reward
                scaled = WEEKLY_BASE_REWARD * (uptime_percent / 0.95)
                reward = round(scaled, 2)
                breakdown.append(f"Base: {reward} RTC ({uptime_percent*100:.1f}% uptime)")

            # Latency bonus
            if avg_latency < 100:
                reward += LATENCY_BONUS
                breakdown.append(f"Latency: +{LATENCY_BONUS} RTC (<100ms)")

            # P2P sync bonus
            if p2p_active:
                reward += P2P_SYNC_BONUS
                breakdown.append(f"P2P Sync: +{P2P_SYNC_BONUS} RTC")

            # Early adopter bonus (first 10 nodes)
            c.execute("SELECT COUNT(*) FROM node_registry")
            node_count = c.fetchone()[0]
            if node_count <= 10:
                reward *= EARLY_ADOPTER_MULTIPLIER
                breakdown.append(f"Early Adopter: x{EARLY_ADOPTER_MULTIPLIER}")

        # Print node summary
        print(f"  {name} ({node_id})")
        print(f"    Wallet: {wallet_address}")
        print(f"    Uptime: {uptime_percent*100:.1f}% ({up_checks}/{total_checks} checks)")
        print(f"    Avg Latency: {avg_latency:.0f}ms")
        print(f"    P2P Active: {'Yes' if p2p_active else 'No'}")
        print(f"    Reward: {reward:.2f} RTC")
        if breakdown:
            for b in breakdown:
                print(f"      - {b}")
        print()

        if reward > 0:
            total_rewards += reward
            reward_entries.append({
                "node_id": node_id,
                "wallet_address": wallet_address,
                "uptime_percent": uptime_percent,
                "avg_latency": avg_latency,
                "total_checks": total_checks,
                "up_checks": up_checks,
                "p2p_active": p2p_active,
                "reward": reward
            })

    print(f"{'='*60}")
    print(f"Total Rewards: {total_rewards:.2f} RTC to {len(reward_entries)} nodes")
    print(f"{'='*60}\n")

    # Distribute rewards
    if reward_entries:
        print("Distributing rewards...")
        for entry in reward_entries:
            success = distribute_reward(
                entry["wallet_address"],
                entry["reward"],
                f"Node operator reward - {entry['node_id']}"
            )
            if success:
                # Record in history
                c.execute("""
                    INSERT INTO node_rewards_history
                    (node_id, wallet_address, week_start, week_end, uptime_percent,
                     avg_latency_ms, checks_total, checks_passed, p2p_bonus, reward_rtc, paid_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry["node_id"],
                    entry["wallet_address"],
                    week_ago,
                    now,
                    entry["uptime_percent"],
                    entry["avg_latency"],
                    entry["total_checks"],
                    entry["up_checks"],
                    1 if entry["p2p_active"] else 0,
                    entry["reward"],
                    int(time.time())
                ))
                print(f"  {entry['node_id']}: {entry['reward']:.2f} RTC -> {entry['wallet_address'][:20]}...")

        conn.commit()

    conn.close()
    return total_rewards

def distribute_reward(wallet_address: str, amount_rtc: float, memo: str) -> bool:
    """Distribute RTC reward to a wallet."""
    try:
        # Use internal transfer from founder fund
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        amount_micro = int(amount_rtc * 1_000_000)

        # Check founder balance
        c.execute("SELECT amount_i64 FROM balances WHERE miner_id = ?", (REWARD_SOURCE,))
        row = c.fetchone()
        if not row or row[0] < amount_micro:
            print(f"[NodeUptime] Insufficient funds in {REWARD_SOURCE}")
            conn.close()
            return False

        # Deduct from source
        c.execute("UPDATE balances SET amount_i64 = amount_i64 - ? WHERE miner_id = ?",
                  (amount_micro, REWARD_SOURCE))

        # Add to destination (create if needed)
        c.execute("""
            INSERT INTO balances (miner_id, amount_i64)
            VALUES (?, ?)
            ON CONFLICT(miner_id) DO UPDATE SET amount_i64 = amount_i64 + ?
        """, (wallet_address, amount_micro, amount_micro))

        # Record in ledger
        c.execute("""
            INSERT INTO ledger (ts, from_pk, to_pk, amount_i64, memo, tx_type)
            VALUES (?, ?, ?, ?, ?, 'node_reward')
        """, (int(time.time()), REWARD_SOURCE, wallet_address, amount_micro, memo))

        conn.commit()
        conn.close()
        return True

    except Exception as e:
        print(f"[NodeUptime] Error distributing reward: {e}")
        return False

def show_status():
    """Show current node status and uptime stats."""
    init_uptime_tables()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    print(f"\n{'='*70}")
    print("RustChain Node Status")
    print(f"{'='*70}\n")

    c.execute("""
        SELECT nr.node_id, nr.wallet_address, nr.name, nr.url,
               (SELECT COUNT(*) FROM node_uptime_checks WHERE node_id = nr.node_id AND check_time > ?) as recent_checks,
               (SELECT SUM(is_up) FROM node_uptime_checks WHERE node_id = nr.node_id AND check_time > ?) as recent_up,
               (SELECT AVG(latency_ms) FROM node_uptime_checks WHERE node_id = nr.node_id AND is_up = 1 AND check_time > ?) as avg_latency
        FROM node_registry nr
        WHERE nr.is_active = 1
    """, (int(time.time()) - 86400,) * 3)

    nodes = c.fetchall()

    for node_id, wallet, name, url, checks, up, latency in nodes:
        uptime = (up / checks * 100) if checks and up else 0
        latency_str = f"{latency:.0f}ms" if latency else "N/A"

        # Check current status
        is_up, curr_latency, _, p2p = check_node_health(url, timeout=5)
        status = "ONLINE" if is_up else "OFFLINE"

        print(f"  {name}")
        print(f"    Node ID: {node_id}")
        print(f"    Wallet:  {wallet}")
        print(f"    URL:     {url}")
        print(f"    Status:  {status}")
        print(f"    24h Uptime: {uptime:.1f}% ({up or 0}/{checks or 0} checks)")
        print(f"    Avg Latency: {latency_str}")
        print(f"    P2P Sync: {'Active' if p2p else 'Inactive'}")
        print()

    # Show recent rewards
    c.execute("""
        SELECT node_id, reward_rtc, datetime(paid_at, 'unixepoch') as paid
        FROM node_rewards_history
        ORDER BY paid_at DESC LIMIT 10
    """)
    rewards = c.fetchall()

    if rewards:
        print(f"\nRecent Rewards:")
        print(f"  {'Node':<25} {'Amount':>10} {'Paid At':<20}")
        print(f"  {'-'*55}")
        for node_id, amount, paid in rewards:
            print(f"  {node_id:<25} {amount:>10.2f} {paid:<20}")

    conn.close()

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 node_uptime_rewards.py [check|rewards|status]")
        print("  check   - Record uptime check for all nodes")
        print("  rewards - Calculate and distribute weekly rewards")
        print("  status  - Show current node status")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "check":
        check_all_nodes()
    elif command == "rewards":
        calculate_weekly_rewards()
    elif command == "status":
        show_status()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()
