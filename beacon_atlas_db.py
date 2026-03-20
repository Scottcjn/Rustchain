# SPDX-License-Identifier: MIT

import sqlite3
import os
from contextlib import contextmanager

DB_PATH = "/root/beacon/beacon_atlas.db"

@contextmanager
def get_db_connection():
    """Get database connection with automatic cleanup."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_beacon_db():
    """Initialize the Beacon Atlas database with relay_agents table."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS relay_agents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT UNIQUE NOT NULL,
                pubkey_hex TEXT NOT NULL,
                metadata TEXT,
                registered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                active INTEGER DEFAULT 1
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_relay_agents_agent_id
            ON relay_agents(agent_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_relay_agents_pubkey
            ON relay_agents(pubkey_hex)
        """)

        conn.commit()

def register_agent(agent_id, pubkey_hex, metadata=None):
    """Register a new agent or update existing one."""
    with get_db_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO relay_agents
            (agent_id, pubkey_hex, metadata, last_seen)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, (agent_id, pubkey_hex, metadata))
        conn.commit()

def get_all_agents():
    """Get all active agents from the database."""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT agent_id, pubkey_hex, metadata, registered_at, last_seen
            FROM relay_agents
            WHERE active = 1
            ORDER BY registered_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]

def update_agent_activity(agent_id):
    """Update last_seen timestamp for an agent."""
    with get_db_connection() as conn:
        conn.execute("""
            UPDATE relay_agents
            SET last_seen = CURRENT_TIMESTAMP
            WHERE agent_id = ?
        """, (agent_id,))
        conn.commit()

def remove_agent(agent_id):
    """Mark agent as inactive."""
    with get_db_connection() as conn:
        conn.execute("""
            UPDATE relay_agents
            SET active = 0
            WHERE agent_id = ?
        """, (agent_id,))
        conn.commit()

if __name__ == "__main__":
    init_beacon_db()
    print(f"Beacon Atlas database initialized at {DB_PATH}")
