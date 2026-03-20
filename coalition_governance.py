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

    def create_coalition(self, name: str, description: str, leader_wallet: str) -> Optional[int]:
        with sqlite3.connect(self.db_path) as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO coalitions (name, description, leader_wallet, created_at) VALUES (?, ?, ?, ?)",
                    (name, description, leader_wallet, int(time.time()))
                )
                coalition_id = cursor.lastrowid
                # Add leader as first member
                conn.execute(
                    "INSERT INTO coalition_members (coalition_id, wallet_address, joined_at) VALUES (?, ?, ?)",
                    (coalition_id, leader_wallet, int(time.time()))
                )
                conn.commit()
                return coalition_id
            except sqlite3.IntegrityError:
                return None

    def get_coalition(self, coalition_id: int) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM coalitions WHERE id = ?",
                (coalition_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

class CoalitionMember:
    def __init__(self, coalition_id: int, wallet_address: str, voting_weight: float = 1.0):
        self.coalition_id = coalition_id
        self.wallet_address = wallet_address
        self.voting_weight = voting_weight
        self.joined_at = int(time.time())
        self.active = True

    def get_voting_power(self) -> float:
        return self.voting_weight

class Proposal:
    def __init__(self, coalition_id: int, title: str, description: str, proposer_wallet: str, voting_duration: int = 86400):
        self.coalition_id = coalition_id
        self.title = title
        self.description = description
        self.proposer_wallet = proposer_wallet
        self.created_at = int(time.time())
        self.voting_ends_at = self.created_at + voting_duration
        self.status = ProposalStatus.ACTIVE
        self.sophia_approved = False
        self.total_votes = 0
        self.total_voting_power = 0.0

    def get_status(self) -> ProposalStatus:
        if int(time.time()) > self.voting_ends_at and self.status == ProposalStatus.ACTIVE:
            return ProposalStatus.EXPIRED
        return self.status
