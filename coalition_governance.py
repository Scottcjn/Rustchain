# SPDX-License-Identifier: MIT

import sqlite3
import json
import time
import hashlib
import os
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from enum import Enum

DB_PATH = "rustchain.db"

class ProposalStatus(Enum):
    ACTIVE = "active"
    PASSED = "passed"
    REJECTED = "rejected"
    EXPIRED = "expired"
    SOPHIA_REVIEW = "sophia_review"
    IMPLEMENTED = "implemented"

class Coalition:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS coalitions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    leader_wallet TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    active INTEGER DEFAULT 1,
                    member_count INTEGER DEFAULT 0,
                    total_voting_power REAL DEFAULT 0.0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS coalition_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    coalition_id INTEGER NOT NULL,
                    wallet_address TEXT NOT NULL,
                    joined_at INTEGER NOT NULL,
                    voting_weight REAL DEFAULT 1.0,
                    active INTEGER DEFAULT 1,
                    FOREIGN KEY (coalition_id) REFERENCES coalitions (id),
                    UNIQUE (coalition_id, wallet_address)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS proposals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    coalition_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    proposer_wallet TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    voting_ends_at INTEGER NOT NULL,
                    status TEXT DEFAULT 'active',
                    proposal_type TEXT DEFAULT 'governance',
                    sophia_approved INTEGER DEFAULT 0,
                    total_votes INTEGER DEFAULT 0,
                    total_voting_power REAL DEFAULT 0.0,
                    FOREIGN KEY (coalition_id) REFERENCES coalitions (id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS votes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    proposal_id INTEGER NOT NULL,
                    voter_wallet TEXT NOT NULL,
                    vote_choice TEXT NOT NULL,
                    voting_power REAL NOT NULL,
                    cast_at INTEGER NOT NULL,
                    FOREIGN KEY (proposal_id) REFERENCES proposals (id),
                    UNIQUE (proposal_id, voter_wallet)
                )
            """)
            conn.commit()

    def create_coalition(self, name: str, description: str, founder: str) -> int:
        """Create a new coalition with founder as leader"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO coalitions (name, description, leader_wallet, created_at) VALUES (?, ?, ?, ?)",
                (name, description, founder, int(time.time()))
            )
            coalition_id = cursor.lastrowid

            # Add founder as first member
            conn.execute(
                "INSERT INTO coalition_members (coalition_id, wallet_address, joined_at, voting_weight) VALUES (?, ?, ?, ?)",
                (coalition_id, founder, int(time.time()), 1.0)
            )

            # Update member count
            conn.execute(
                "UPDATE coalitions SET member_count = 1 WHERE id = ?",
                (coalition_id,)
            )

            conn.commit()
            return coalition_id

    def join_coalition(self, coalition_id: int, wallet_address: str, voting_weight: float = 1.0) -> bool:
        """Join an existing coalition"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Check if coalition exists and is active
                cursor = conn.execute(
                    "SELECT id FROM coalitions WHERE id = ? AND active = 1",
                    (coalition_id,)
                )
                if not cursor.fetchone():
                    return False

                # Add member
                conn.execute(
                    "INSERT OR REPLACE INTO coalition_members (coalition_id, wallet_address, joined_at, voting_weight) VALUES (?, ?, ?, ?)",
                    (coalition_id, wallet_address, int(time.time()), voting_weight)
                )

                # Update member count
                conn.execute(
                    "UPDATE coalitions SET member_count = (SELECT COUNT(*) FROM coalition_members WHERE coalition_id = ? AND active = 1) WHERE id = ?",
                    (coalition_id, coalition_id)
                )

                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

    def calculate_voting_weight(self, wallet_address: str, coalition_id: int = None) -> float:
        """Calculate voting weight for a wallet address"""
        with sqlite3.connect(self.db_path) as conn:
            if coalition_id:
                cursor = conn.execute(
                    "SELECT voting_weight FROM coalition_members WHERE wallet_address = ? AND coalition_id = ? AND active = 1",
                    (wallet_address, coalition_id)
                )
            else:
                cursor = conn.execute(
                    "SELECT SUM(voting_weight) FROM coalition_members WHERE wallet_address = ? AND active = 1",
                    (wallet_address,)
                )

            result = cursor.fetchone()
            return result[0] if result and result[0] else 0.0

    def get_coalition(self, coalition_id: int) -> Optional[Dict]:
        """Get coalition information"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM coalitions WHERE id = ?",
                (coalition_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_coalition_members(self, coalition_id: int) -> List[Dict]:
        """Get all members of a coalition"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM coalition_members WHERE coalition_id = ? AND active = 1",
                (coalition_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def create_proposal(self, coalition_id: int, title: str, description: str, proposer_wallet: str, voting_duration: int = 604800) -> int:
        """Create a new proposal"""
        with sqlite3.connect(self.db_path) as conn:
            voting_ends_at = int(time.time()) + voting_duration
            cursor = conn.execute(
                "INSERT INTO proposals (coalition_id, title, description, proposer_wallet, created_at, voting_ends_at) VALUES (?, ?, ?, ?, ?, ?)",
                (coalition_id, title, description, proposer_wallet, int(time.time()), voting_ends_at)
            )
            proposal_id = cursor.lastrowid
            conn.commit()
            return proposal_id

    def cast_vote(self, proposal_id: int, voter_wallet: str, vote_choice: str, voting_power: float) -> bool:
        """Cast a vote on a proposal"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Check if proposal exists and is active
                cursor = conn.execute(
                    "SELECT id, voting_ends_at FROM proposals WHERE id = ? AND status = 'active'",
                    (proposal_id,)
                )
                proposal = cursor.fetchone()
                if not proposal or proposal[1] < int(time.time()):
                    return False

                # Cast vote
                conn.execute(
                    "INSERT OR REPLACE INTO votes (proposal_id, voter_wallet, vote_choice, voting_power, cast_at) VALUES (?, ?, ?, ?, ?)",
                    (proposal_id, voter_wallet, vote_choice, voting_power, int(time.time()))
                )

                # Update proposal vote counts
                conn.execute(
                    "UPDATE proposals SET total_votes = (SELECT COUNT(*) FROM votes WHERE proposal_id = ?), total_voting_power = (SELECT SUM(voting_power) FROM votes WHERE proposal_id = ?) WHERE id = ?",
                    (proposal_id, proposal_id, proposal_id)
                )

                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

class CoalitionMember:
    def __init__(self, coalition_id: int, wallet_address: str, voting_weight: float = 1.0):
        self.coalition_id = coalition_id
        self.wallet_address = wallet_address
        self.voting_weight = voting_weight
        self.joined_at = int(time.time())
        self.active = True

class Proposal:
    def __init__(self, coalition_id: int, title: str, description: str, proposer_wallet: str):
        self.coalition_id = coalition_id
        self.title = title
        self.description = description
        self.proposer_wallet = proposer_wallet
        self.created_at = int(time.time())
        self.status = ProposalStatus.ACTIVE
        self.votes_for = 0.0
        self.votes_against = 0.0
