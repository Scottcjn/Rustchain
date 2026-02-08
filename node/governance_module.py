"""
RustChain On-Chain Governance Module
Implements hardware-weighted voting and proposal lifecycle.
"""

import sqlite3
import time
import logging
from typing import Dict, List, Optional, Tuple

class GovernanceManager:
    def __init__(self, db_path: str = "node/rustchain.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Proposals Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS governance_proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proposer TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'ACTIVE', -- ACTIVE, PASSED, FAILED
                start_time REAL NOT NULL,
                end_time REAL NOT NULL,
                required_stake REAL DEFAULT 10.0,
                snapshot_block INTEGER
            )
        ''')
        # Votes Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS governance_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proposal_id INTEGER NOT NULL,
                voter TEXT NOT NULL,
                weight REAL NOT NULL,
                vote_type TEXT NOT NULL, -- YES, NO, ABSTAIN
                signature TEXT NOT NULL,
                timestamp REAL NOT NULL,
                FOREIGN KEY (proposal_id) REFERENCES governance_proposals (id),
                UNIQUE(proposal_id, voter)
            )
        ''')
        conn.commit()
        conn.close()

    def create_proposal(self, proposer: str, title: str, description: str, stake: float) -> Optional[int]:
        """Creates a new governance proposal."""
        if stake < 10.0:
            logging.warning(f"Insufficient stake: {stake} < 10.0")
            return None
        
        now = time.time()
        expiry = now + (7 * 24 * 3600) # 7 days
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO governance_proposals (proposer, title, description, start_time, end_time)
            VALUES (?, ?, ?, ?, ?)
        ''', (proposer, title, description, now, expiry))
        prop_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return prop_id

    def cast_vote(self, proposal_id: int, voter: str, weight: float, vote_type: str, signature: str) -> bool:
        """Records a hardware-weighted vote."""
        # TODO: Implement Ed25519 signature verification using rustchain_crypto
        now = time.time()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO governance_votes (proposal_id, voter, weight, vote_type, signature, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (proposal_id, voter, weight, vote_type, signature, now))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            logging.warning(f"Voter {voter} already voted on proposal {proposal_id}")
            return False
        finally:
            conn.close()

    def get_tally(self, proposal_id: int) -> Dict:
        """Calculates current results based on weights."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT vote_type, SUM(weight) FROM governance_votes
            WHERE proposal_id = ?
            GROUP BY vote_type
        ''', (proposal_id,))
        results = dict(cursor.fetchall())
        conn.close()
        return results
