// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import time
import hashlib
import json
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

DB_PATH = 'rustchain.db'

class CoalitionSystem:
    def __init__(self):
        self.init_database()

    def init_database(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS coalitions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    founder_address TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    veto_authority BOOLEAN DEFAULT FALSE,
                    total_members INTEGER DEFAULT 0,
                    total_voting_power REAL DEFAULT 0
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS coalition_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    coalition_id INTEGER NOT NULL,
                    member_address TEXT NOT NULL,
                    joined_at INTEGER NOT NULL,
                    rtc_balance REAL DEFAULT 0,
                    antiquity_years REAL DEFAULT 0,
                    voting_power REAL DEFAULT 0,
                    UNIQUE(coalition_id, member_address),
                    FOREIGN KEY (coalition_id) REFERENCES coalitions (id)
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS proposals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    coalition_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    proposer_address TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    voting_deadline INTEGER NOT NULL,
                    status TEXT DEFAULT 'active',
                    yes_votes REAL DEFAULT 0,
                    no_votes REAL DEFAULT 0,
                    sophia_approved BOOLEAN DEFAULT NULL,
                    FOREIGN KEY (coalition_id) REFERENCES coalitions (id)
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS proposal_votes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    proposal_id INTEGER NOT NULL,
                    voter_address TEXT NOT NULL,
                    vote_choice TEXT NOT NULL,
                    voting_power REAL NOT NULL,
                    cast_at INTEGER NOT NULL,
                    UNIQUE(proposal_id, voter_address),
                    FOREIGN KEY (proposal_id) REFERENCES proposals (id)
                )
            ''')

            # Create genesis coalition - The Flamebound
            self.create_flamebound_coalition()

    def create_flamebound_coalition(self):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''
                SELECT id FROM coalitions WHERE name = 'The Flamebound'
            ''')
            if cursor.fetchone():
                return

            conn.execute('''
                INSERT INTO coalitions (name, description, founder_address, created_at, veto_authority)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                'The Flamebound',
                'Genesis coalition of hardware preservers and network guardians',
                'sophia-elya',
                int(time.time()),
                True
            ))

    def create_coalition(self, name: str, description: str, founder_address: str) -> bool:
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''
                    INSERT INTO coalitions (name, description, founder_address, created_at)
                    VALUES (?, ?, ?, ?)
                ''', (name, description, founder_address, int(time.time())))

                # Auto-join founder as first member
                coalition_id = conn.lastrowid
                self.join_coalition(coalition_id, founder_address)
                return True
        except sqlite3.IntegrityError:
            return False

    def get_coalition_by_name(self, name: str) -> Optional[Dict]:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''
                SELECT * FROM coalitions WHERE name = ?
            ''', (name,))
            row = cursor.fetchone()
            if row:
                cols = [desc[0] for desc in cursor.description]
                return dict(zip(cols, row))
        return None

    def join_coalition(self, coalition_id: int, member_address: str, rtc_balance: float = 0, antiquity_years: float = 0) -> bool:
        voting_power = self.calculate_voting_power(rtc_balance, antiquity_years)

        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''
                    INSERT INTO coalition_members
                    (coalition_id, member_address, joined_at, rtc_balance, antiquity_years, voting_power)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (coalition_id, member_address, int(time.time()), rtc_balance, antiquity_years, voting_power))

                # Update coalition totals
                conn.execute('''
                    UPDATE coalitions SET
                    total_members = (SELECT COUNT(*) FROM coalition_members WHERE coalition_id = ?),
                    total_voting_power = (SELECT SUM(voting_power) FROM coalition_members WHERE coalition_id = ?)
                    WHERE id = ?
                ''', (coalition_id, coalition_id, coalition_id))
                return True
        except sqlite3.IntegrityError:
            return False

    def leave_coalition(self, coalition_id: int, member_address: str) -> bool:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''
                DELETE FROM coalition_members
                WHERE coalition_id = ? AND member_address = ?
            ''', (coalition_id, member_address))

            if cursor.rowcount > 0:
                # Update coalition totals
                conn.execute('''
                    UPDATE coalitions SET
                    total_members = (SELECT COUNT(*) FROM coalition_members WHERE coalition_id = ?),
                    total_voting_power = (SELECT COALESCE(SUM(voting_power), 0) FROM coalition_members WHERE coalition_id = ?)
                    WHERE id = ?
                ''', (coalition_id, coalition_id, coalition_id))
                return True
        return False

    def calculate_voting_power(self, rtc_balance: float, antiquity_years: float) -> float:
        # Antiquity multiplier: 1.0 + (years * 0.1), capped at 2.0
        multiplier = min(1.0 + (antiquity_years * 0.1), 2.0)
        return rtc_balance * multiplier

    def create_proposal(self, coalition_id: int, title: str, description: str,
                       proposer_address: str, voting_hours: int = 168) -> Optional[int]:
        deadline = int(time.time()) + (voting_hours * 3600)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''
                INSERT INTO proposals
                (coalition_id, title, description, proposer_address, created_at, voting_deadline)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (coalition_id, title, description, proposer_address, int(time.time()), deadline))
            return cursor.lastrowid

    def cast_vote(self, proposal_id: int, voter_address: str, vote_choice: str) -> bool:
        # Get voter's voting power from their coalition membership
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''
                SELECT cm.voting_power FROM coalition_members cm
                JOIN proposals p ON cm.coalition_id = p.coalition_id
                WHERE p.id = ? AND cm.member_address = ?
            ''', (proposal_id, voter_address))

            row = cursor.fetchone()
            if not row:
                return False

            voting_power = row[0]

            try:
                conn.execute('''
                    INSERT OR REPLACE INTO proposal_votes
                    (proposal_id, voter_address, vote_choice, voting_power, cast_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (proposal_id, voter_address, vote_choice, voting_power, int(time.time())))

                # Update proposal vote totals
                self.update_proposal_totals(proposal_id)
                return True
            except sqlite3.Error:
                return False

    def update_proposal_totals(self, proposal_id: int):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''
                SELECT
                    SUM(CASE WHEN vote_choice = 'yes' THEN voting_power ELSE 0 END) as yes_votes,
                    SUM(CASE WHEN vote_choice = 'no' THEN voting_power ELSE 0 END) as no_votes
                FROM proposal_votes WHERE proposal_id = ?
            ''', (proposal_id,))

            row = cursor.fetchone()
            yes_votes = row[0] if row[0] else 0
            no_votes = row[1] if row[1] else 0

            conn.execute('''
                UPDATE proposals SET yes_votes = ?, no_votes = ? WHERE id = ?
            ''', (yes_votes, no_votes, proposal_id))

    def sophia_approve_proposal(self, proposal_id: int, approved: bool) -> bool:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''
                UPDATE proposals SET sophia_approved = ? WHERE id = ?
            ''', (approved, proposal_id))
            return cursor.rowcount > 0

    def finalize_proposal(self, proposal_id: int) -> Dict:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''
                SELECT p.*, c.veto_authority FROM proposals p
                JOIN coalitions c ON p.coalition_id = c.id
                WHERE p.id = ?
            ''', (proposal_id,))

            proposal = cursor.fetchone()
            if not proposal:
                return {'status': 'not_found'}

            now = int(time.time())
            if now < proposal[6]:  # voting_deadline
                return {'status': 'still_voting'}

            yes_votes = proposal[8]
            no_votes = proposal[9]
            sophia_approved = proposal[10]
            veto_authority = proposal[11]

            # Determine result
            if yes_votes > no_votes:
                if veto_authority and sophia_approved is None:
                    result = 'awaiting_sophia'
                elif veto_authority and not sophia_approved:
                    result = 'vetoed'
                else:
                    result = 'passed'
            else:
                result = 'failed'

            # Update status
            conn.execute('''
                UPDATE proposals SET status = ? WHERE id = ?
            ''', (result, proposal_id))

            return {
                'status': result,
                'yes_votes': yes_votes,
                'no_votes': no_votes,
                'sophia_approved': sophia_approved
            }

    def get_coalition_members(self, coalition_id: int) -> List[Dict]:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''
                SELECT * FROM coalition_members WHERE coalition_id = ?
                ORDER BY voting_power DESC
            ''', (coalition_id,))

            cols = [desc[0] for desc in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def get_active_proposals(self, coalition_id: int) -> List[Dict]:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''
                SELECT * FROM proposals
                WHERE coalition_id = ? AND status = 'active'
                ORDER BY created_at DESC
            ''', (coalition_id,))

            cols = [desc[0] for desc in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

def get_coalition_system():
    return CoalitionSystem()
