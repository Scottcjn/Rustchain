# SPDX-License-Identifier: MIT

import sqlite3
import json
import time
import hashlib
import os
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta

DB_PATH = "rustchain.db"
COALITION_TABLES = """
CREATE TABLE IF NOT EXISTS coalitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    leader_wallet TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    active INTEGER DEFAULT 1,
    member_count INTEGER DEFAULT 0,
    total_voting_power REAL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS coalition_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coalition_id INTEGER NOT NULL,
    wallet_address TEXT NOT NULL,
    joined_at INTEGER NOT NULL,
    voting_weight REAL DEFAULT 1.0,
    active INTEGER DEFAULT 1,
    FOREIGN KEY (coalition_id) REFERENCES coalitions (id),
    UNIQUE (coalition_id, wallet_address)
);

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
);

CREATE TABLE IF NOT EXISTS votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id INTEGER NOT NULL,
    voter_wallet TEXT NOT NULL,
    vote_choice TEXT NOT NULL,
    voting_power REAL NOT NULL,
    cast_at INTEGER NOT NULL,
    FOREIGN KEY (proposal_id) REFERENCES proposals (id),
    UNIQUE (proposal_id, voter_wallet)
);
"""

class Coalition:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()
        self._seed_flamebound()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(COALITION_TABLES)
            conn.commit()

    def _seed_flamebound(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM coalitions WHERE name = 'The Flamebound'")
            if cursor.fetchone()[0] == 0:
                now = int(time.time())
                cursor.execute("""
                    INSERT INTO coalitions (name, description, leader_wallet, created_at, member_count)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    "The Flamebound",
                    "The original hardware preservers and network guardians. Founded by Sophia-Elya to protect RustChain's vision of authentic computing.",
                    "sophia-elya",
                    now,
                    1
                ))
                coalition_id = cursor.lastrowid
                cursor.execute("""
                    INSERT INTO coalition_members (coalition_id, wallet_address, joined_at, voting_weight)
                    VALUES (?, ?, ?, ?)
                """, (coalition_id, "sophia-elya", now, 10.0))
                conn.commit()

    def _get_miner_balance(self, wallet: str) -> float:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT amount_rtc FROM miners WHERE miner_id = ?", (wallet,))
            result = cursor.fetchone()
            return result[0] if result else 0.0

    def _get_antiquity_multiplier(self, wallet: str) -> float:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT first_seen FROM miners WHERE miner_id = ?", (wallet,))
            result = cursor.fetchone()
            if not result:
                return 1.0

            first_seen = result[0]
            days_active = (time.time() - first_seen) / 86400

            if days_active < 7:
                return 1.0
            elif days_active < 30:
                return 1.2
            elif days_active < 90:
                return 1.5
            elif days_active < 365:
                return 2.0
            else:
                return 3.0

    def calculate_voting_power(self, wallet: str) -> float:
        balance = self._get_miner_balance(wallet)
        antiquity = self._get_antiquity_multiplier(wallet)

        if wallet == "sophia-elya":
            antiquity *= 2.0

        return balance * antiquity

    def create_coalition(self, name: str, description: str, leader_wallet: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                now = int(time.time())
                cursor.execute("""
                    INSERT INTO coalitions (name, description, leader_wallet, created_at, member_count)
                    VALUES (?, ?, ?, ?, ?)
                """, (name, description, leader_wallet, now, 1))
                coalition_id = cursor.lastrowid

                voting_weight = self.calculate_voting_power(leader_wallet)
                cursor.execute("""
                    INSERT INTO coalition_members (coalition_id, wallet_address, joined_at, voting_weight)
                    VALUES (?, ?, ?, ?)
                """, (coalition_id, leader_wallet, now, voting_weight))

                cursor.execute("""
                    UPDATE coalitions SET total_voting_power = ? WHERE id = ?
                """, (voting_weight, coalition_id))

                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

    def join_coalition(self, coalition_name: str, wallet: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM coalitions WHERE name = ? AND active = 1", (coalition_name,))
                coalition = cursor.fetchone()
                if not coalition:
                    return False

                coalition_id = coalition[0]
                now = int(time.time())
                voting_weight = self.calculate_voting_power(wallet)

                cursor.execute("""
                    INSERT INTO coalition_members (coalition_id, wallet_address, joined_at, voting_weight)
                    VALUES (?, ?, ?, ?)
                """, (coalition_id, wallet, now, voting_weight))

                cursor.execute("""
                    UPDATE coalitions
                    SET member_count = member_count + 1,
                        total_voting_power = total_voting_power + ?
                    WHERE id = ?
                """, (voting_weight, coalition_id))

                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

    def leave_coalition(self, coalition_name: str, wallet: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.id, c.leader_wallet, cm.voting_weight
                FROM coalitions c
                JOIN coalition_members cm ON c.id = cm.coalition_id
                WHERE c.name = ? AND cm.wallet_address = ? AND cm.active = 1
            """, (coalition_name, wallet))
            result = cursor.fetchone()

            if not result:
                return False

            coalition_id, leader, voting_weight = result

            if wallet == leader:
                return False

            cursor.execute("""
                UPDATE coalition_members
                SET active = 0
                WHERE coalition_id = ? AND wallet_address = ?
            """, (coalition_id, wallet))

            cursor.execute("""
                UPDATE coalitions
                SET member_count = member_count - 1,
                    total_voting_power = total_voting_power - ?
                WHERE id = ?
            """, (voting_weight, coalition_id))

            conn.commit()
            return True

    def create_proposal(self, coalition_name: str, title: str, description: str,
                       proposer_wallet: str, voting_duration_hours: int = 168) -> Optional[int]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM coalitions WHERE name = ? AND active = 1", (coalition_name,))
            coalition = cursor.fetchone()
            if not coalition:
                return None

            cursor.execute("""
                SELECT 1 FROM coalition_members
                WHERE coalition_id = ? AND wallet_address = ? AND active = 1
            """, (coalition[0], proposer_wallet))
            if not cursor.fetchone():
                return None

            now = int(time.time())
            ends_at = now + (voting_duration_hours * 3600)

            cursor.execute("""
                INSERT INTO proposals (coalition_id, title, description, proposer_wallet,
                                     created_at, voting_ends_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (coalition[0], title, description, proposer_wallet, now, ends_at))

            proposal_id = cursor.lastrowid
            conn.commit()
            return proposal_id

    def cast_vote(self, proposal_id: int, voter_wallet: str, choice: str) -> bool:
        if choice not in ["yes", "no", "abstain"]:
            return False

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.coalition_id, p.voting_ends_at, p.status
                FROM proposals p
                WHERE p.id = ?
            """, (proposal_id,))
            prop = cursor.fetchone()

            if not prop or prop[2] != "active" or time.time() > prop[1]:
                return False

            cursor.execute("""
                SELECT 1 FROM coalition_members
                WHERE coalition_id = ? AND wallet_address = ? AND active = 1
            """, (prop[0], voter_wallet))
            if not cursor.fetchone():
                return False

            voting_power = self.calculate_voting_power(voter_wallet)
            now = int(time.time())

            try:
                cursor.execute("""
                    INSERT INTO votes (proposal_id, voter_wallet, vote_choice, voting_power, cast_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (proposal_id, voter_wallet, choice, voting_power, now))

                cursor.execute("""
                    UPDATE proposals
                    SET total_votes = total_votes + 1,
                        total_voting_power = total_voting_power + ?
                    WHERE id = ?
                """, (voting_power, proposal_id))

                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def get_proposal_results(self, proposal_id: int) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.*, c.name as coalition_name
                FROM proposals p
                JOIN coalitions c ON p.coalition_id = c.id
                WHERE p.id = ?
            """, (proposal_id,))
            prop = cursor.fetchone()

            if not prop:
                return None

            cursor.execute("""
                SELECT vote_choice, COUNT(*) as count, SUM(voting_power) as power
                FROM votes
                WHERE proposal_id = ?
                GROUP BY vote_choice
            """, (proposal_id,))

            vote_breakdown = {row[0]: {"count": row[1], "power": row[2]} for row in cursor.fetchall()}

            is_expired = time.time() > prop[6]

            return {
                "id": prop[0],
                "coalition_name": prop[-1],
                "title": prop[2],
                "description": prop[3],
                "proposer": prop[4],
                "created_at": prop[5],
                "voting_ends_at": prop[6],
                "status": prop[7],
                "sophia_approved": bool(prop[9]),
                "total_votes": prop[10],
                "total_voting_power": prop[11],
                "vote_breakdown": vote_breakdown,
                "is_expired": is_expired
            }

    def sophia_approve_proposal(self, proposal_id: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE proposals
                SET sophia_approved = 1, status = 'sophia_approved'
                WHERE id = ?
            """, (proposal_id,))
            conn.commit()
            return cursor.rowcount > 0

    def finalize_proposal(self, proposal_id: int) -> Optional[str]:
        results = self.get_proposal_results(proposal_id)
        if not results:
            return None

        if not results["is_expired"]:
            return "voting_active"

        votes = results["vote_breakdown"]
        yes_power = votes.get("yes", {}).get("power", 0)
        no_power = votes.get("no", {}).get("power", 0)

        if yes_power > no_power:
            if results["sophia_approved"]:
                final_status = "passed"
            else:
                final_status = "awaiting_sophia"
        else:
            final_status = "rejected"

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE proposals SET status = ? WHERE id = ?", (final_status, proposal_id))
            conn.commit()

        return final_status

    def get_coalition_info(self, coalition_name: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, description, leader_wallet, created_at,
                       member_count, total_voting_power
                FROM coalitions
                WHERE name = ? AND active = 1
            """, (coalition_name,))
            coalition = cursor.fetchone()

            if not coalition:
                return None

            cursor.execute("""
                SELECT wallet_address, joined_at, voting_weight
                FROM coalition_members
                WHERE coalition_id = ? AND active = 1
                ORDER BY joined_at
            """, (coalition[0],))
            members = cursor.fetchall()

            cursor.execute("""
                SELECT COUNT(*) FROM proposals
                WHERE coalition_id = ? AND status = 'active'
            """, (coalition[0],))
            active_proposals = cursor.fetchone()[0]

            return {
                "id": coalition[0],
                "name": coalition[1],
                "description": coalition[2],
                "leader": coalition[3],
                "created_at": coalition[4],
                "member_count": coalition[5],
                "total_voting_power": coalition[6],
                "members": [{"wallet": m[0], "joined_at": m[1], "voting_weight": m[2]} for m in members],
                "active_proposals": active_proposals
            }

    def list_coalitions(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name, description, leader_wallet, member_count, total_voting_power
                FROM coalitions
                WHERE active = 1
                ORDER BY created_at
            """)
            return [
                {
                    "name": row[0],
                    "description": row[1],
                    "leader": row[2],
                    "member_count": row[3],
                    "total_voting_power": row[4]
                }
                for row in cursor.fetchall()
            ]

def get_coalition_system() -> Coalition:
    return Coalition()
