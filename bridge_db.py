// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import json
import time
from typing import Dict, List, Optional, Tuple, Any
from contextlib import contextmanager

DB_PATH = "bridge.db"

@contextmanager
def get_db_connection():
    """Database connection context manager"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

class BridgeDB:
    
    def __init__(self):
        self.init_database()
    
    def init_database(self):
        """Initialize bridge database schema"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Cross-chain locks table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cross_chain_locks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lock_id TEXT UNIQUE NOT NULL,
                    from_chain TEXT NOT NULL,
                    to_chain TEXT NOT NULL,
                    from_address TEXT NOT NULL,
                    to_address TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    token_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    lock_tx_hash TEXT,
                    release_tx_hash TEXT,
                    created_at INTEGER NOT NULL,
                    locked_at INTEGER,
                    released_at INTEGER,
                    metadata TEXT
                )
            ''')
            
            # Token mappings table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS token_mappings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_chain TEXT NOT NULL,
                    target_chain TEXT NOT NULL,
                    source_token TEXT NOT NULL,
                    target_token TEXT NOT NULL,
                    conversion_rate REAL DEFAULT 1.0,
                    active INTEGER DEFAULT 1,
                    created_at INTEGER NOT NULL,
                    UNIQUE(source_chain, target_chain, source_token)
                )
            ''')
            
            # Bridge transactions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bridge_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tx_hash TEXT UNIQUE NOT NULL,
                    chain TEXT NOT NULL,
                    block_number INTEGER,
                    from_address TEXT NOT NULL,
                    to_address TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    transaction_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    lock_id TEXT,
                    timestamp INTEGER NOT NULL,
                    confirmations INTEGER DEFAULT 0,
                    gas_used INTEGER,
                    gas_price INTEGER,
                    metadata TEXT,
                    FOREIGN KEY(lock_id) REFERENCES cross_chain_locks(lock_id)
                )
            ''')
            
            # Validator signatures table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS validator_signatures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lock_id TEXT NOT NULL,
                    validator_address TEXT NOT NULL,
                    signature TEXT NOT NULL,
                    signed_at INTEGER NOT NULL,
                    is_valid INTEGER DEFAULT 1,
                    FOREIGN KEY(lock_id) REFERENCES cross_chain_locks(lock_id),
                    UNIQUE(lock_id, validator_address)
                )
            ''')
            
            # Chain configurations
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chain_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chain_name TEXT UNIQUE NOT NULL,
                    chain_id TEXT NOT NULL,
                    rpc_endpoint TEXT NOT NULL,
                    bridge_contract TEXT,
                    token_contract TEXT,
                    confirmation_blocks INTEGER DEFAULT 12,
                    active INTEGER DEFAULT 1,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            ''')
            
            conn.commit()
            
            # Insert default chain configs if they don't exist
            self._insert_default_configs(cursor)
            conn.commit()
    
    def _insert_default_configs(self, cursor):
        """Insert default chain configurations"""
        default_configs = [
            ('rustchain', 'rustchain-mainnet', 'http://localhost:8545', None, 'RTC', 6, 1),
            ('solana', 'solana-mainnet', 'https://api.mainnet-beta.solana.com', None, None, 32, 1),
            ('base', 'base-mainnet', 'https://mainnet.base.org', None, None, 12, 1),
            ('ethereum', 'ethereum-mainnet', 'https://mainnet.infura.io/v3/', None, None, 12, 1)
        ]
        
        timestamp = int(time.time())
        for config in default_configs:
            cursor.execute('''
                INSERT OR IGNORE INTO chain_configs 
                (chain_name, chain_id, rpc_endpoint, bridge_contract, token_contract, confirmation_blocks, active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (*config, timestamp, timestamp))
    
    def create_lock(self, from_chain: str, to_chain: str, from_addr: str, 
                   to_addr: str, amount: int, token_type: str, metadata: Dict = None) -> str:
        """Create new cross-chain lock record"""
        import uuid
        
        lock_id = f"lock_{uuid.uuid4().hex[:16]}"
        timestamp = int(time.time())
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO cross_chain_locks 
                (lock_id, from_chain, to_chain, from_address, to_address, amount, token_type, created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (lock_id, from_chain, to_chain, from_addr, to_addr, amount, token_type, 
                  timestamp, json.dumps(metadata) if metadata else None))
            conn.commit()
            
        return lock_id
    
    def update_lock_status(self, lock_id: str, status: str, tx_hash: str = None, 
                          is_release: bool = False) -> bool:
        """Update lock status and transaction hash"""
        timestamp = int(time.time())
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            if is_release:
                cursor.execute('''
                    UPDATE cross_chain_locks 
                    SET status = ?, release_tx_hash = ?, released_at = ?
                    WHERE lock_id = ?
                ''', (status, tx_hash, timestamp, lock_id))
            else:
                cursor.execute('''
                    UPDATE cross_chain_locks 
                    SET status = ?, lock_tx_hash = ?, locked_at = ?
                    WHERE lock_id = ?
                ''', (status, tx_hash, timestamp, lock_id))
                
            conn.commit()
            return cursor.rowcount > 0
    
    def get_lock(self, lock_id: str) -> Optional[Dict]:
        """Get lock record by ID"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM cross_chain_locks WHERE lock_id = ?', (lock_id,))
            row = cursor.fetchone()
            
            if row:
                lock_data = dict(row)
                if lock_data.get('metadata'):
                    lock_data['metadata'] = json.loads(lock_data['metadata'])
                return lock_data
            return None
    
    def get_pending_locks(self, chain: str = None) -> List[Dict]:
        """Get pending lock records"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            if chain:
                cursor.execute('''
                    SELECT * FROM cross_chain_locks 
                    WHERE status = 'pending' AND from_chain = ?
                    ORDER BY created_at ASC
                ''', (chain,))
            else:
                cursor.execute('''
                    SELECT * FROM cross_chain_locks 
                    WHERE status = 'pending'
                    ORDER BY created_at ASC
                ''')
            
            locks = []
            for row in cursor.fetchall():
                lock_data = dict(row)
                if lock_data.get('metadata'):
                    lock_data['metadata'] = json.loads(lock_data['metadata'])
                locks.append(lock_data)
                
            return locks
    
    def add_token_mapping(self, source_chain: str, target_chain: str, 
                         source_token: str, target_token: str, conversion_rate: float = 1.0) -> bool:
        """Add token mapping between chains"""
        timestamp = int(time.time())
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO token_mappings 
                (source_chain, target_chain, source_token, target_token, conversion_rate, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (source_chain, target_chain, source_token, target_token, conversion_rate, timestamp))
            conn.commit()
            return cursor.rowcount > 0
    
    def get_token_mapping(self, source_chain: str, target_chain: str, source_token: str) -> Optional[Dict]:
        """Get token mapping"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM token_mappings 
                WHERE source_chain = ? AND target_chain = ? AND source_token = ? AND active = 1
            ''', (source_chain, target_chain, source_token))
            
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def record_bridge_transaction(self, tx_hash: str, chain: str, from_addr: str, 
                                 to_addr: str, amount: int, tx_type: str, 
                                 lock_id: str = None, block_number: int = None) -> bool:
        """Record bridge transaction"""
        timestamp = int(time.time())
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO bridge_transactions 
                (tx_hash, chain, from_address, to_address, amount, transaction_type, lock_id, timestamp, block_number)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (tx_hash, chain, from_addr, to_addr, amount, tx_type, lock_id, timestamp, block_number))
            conn.commit()
            return cursor.rowcount > 0
    
    def update_transaction_status(self, tx_hash: str, status: str, confirmations: int = None) -> bool:
        """Update transaction status and confirmations"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            if confirmations is not None:
                cursor.execute('''
                    UPDATE bridge_transactions 
                    SET status = ?, confirmations = ?
                    WHERE tx_hash = ?
                ''', (status, confirmations, tx_hash))
            else:
                cursor.execute('''
                    UPDATE bridge_transactions 
                    SET status = ?
                    WHERE tx_hash = ?
                ''', (status, tx_hash))
                
            conn.commit()
            return cursor.rowcount > 0
    
    def add_validator_signature(self, lock_id: str, validator_addr: str, signature: str) -> bool:
        """Add validator signature for lock"""
        timestamp = int(time.time())
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO validator_signatures 
                (lock_id, validator_address, signature, signed_at)
                VALUES (?, ?, ?, ?)
            ''', (lock_id, validator_addr, signature, timestamp))
            conn.commit()
            return cursor.rowcount > 0
    
    def get_validator_signatures(self, lock_id: str) -> List[Dict]:
        """Get all validator signatures for a lock"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM validator_signatures 
                WHERE lock_id = ? AND is_valid = 1
                ORDER BY signed_at ASC
            ''', (lock_id,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_chain_config(self, chain_name: str) -> Optional[Dict]:
        """Get chain configuration"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM chain_configs 
                WHERE chain_name = ? AND active = 1
            ''', (chain_name,))
            
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_bridge_stats(self) -> Dict:
        """Get bridge statistics"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Total locks by status
            cursor.execute('SELECT status, COUNT(*) as count FROM cross_chain_locks GROUP BY status')
            status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
            
            # Total volume by chain
            cursor.execute('''
                SELECT from_chain, SUM(amount) as total_amount 
                FROM cross_chain_locks 
                WHERE status = 'completed'
                GROUP BY from_chain
            ''')
            volume_by_chain = {row['from_chain']: row['total_amount'] for row in cursor.fetchall()}
            
            # Recent transactions
            cursor.execute('''
                SELECT * FROM bridge_transactions 
                ORDER BY timestamp DESC 
                LIMIT 10
            ''')
            recent_txs = [dict(row) for row in cursor.fetchall()]
            
            return {
                'lock_status_counts': status_counts,
                'volume_by_chain': volume_by_chain,
                'recent_transactions': recent_txs,
                'total_locks': sum(status_counts.values())
            }

bridge_db = BridgeDB()