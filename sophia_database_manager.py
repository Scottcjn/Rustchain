// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import json
import time
import hashlib
from typing import Dict, List, Optional, Tuple

DB_PATH = 'rustchain.db'

class SophiaDatabaseManager:
    def __init__(self):
        self.init_sophia_tables()
    
    def init_sophia_tables(self):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Sophia inspection results table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sophia_inspections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    miner_id TEXT NOT NULL,
                    attestation_hash TEXT NOT NULL,
                    fingerprint_data TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    confidence_score REAL NOT NULL,
                    sophia_reasoning TEXT,
                    timestamp REAL NOT NULL,
                    block_height INTEGER,
                    correlation_flags TEXT,
                    UNIQUE(miner_id, attestation_hash)
                )
            ''')
            
            # Verdict history tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sophia_verdict_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    miner_id TEXT NOT NULL,
                    verdict_count_ok INTEGER DEFAULT 0,
                    verdict_count_suspicious INTEGER DEFAULT 0,
                    verdict_count_failed INTEGER DEFAULT 0,
                    avg_confidence REAL DEFAULT 0.0,
                    last_inspection REAL,
                    reputation_score REAL DEFAULT 0.0,
                    correlation_pattern TEXT,
                    updated_at REAL NOT NULL,
                    UNIQUE(miner_id)
                )
            ''')
            
            # Sophia model status
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sophia_model_status (
                    id INTEGER PRIMARY KEY,
                    model_name TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    last_health_check REAL,
                    status TEXT NOT NULL,
                    total_inspections INTEGER DEFAULT 0,
                    avg_response_time REAL DEFAULT 0.0,
                    error_rate REAL DEFAULT 0.0
                )
            ''')
            
            conn.commit()
    
    def store_inspection_result(self, miner_id: str, attestation_hash: str, 
                              fingerprint_data: Dict, verdict: str, 
                              confidence_score: float, reasoning: str = None,
                              block_height: int = None, correlation_flags: List[str] = None) -> bool:
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                
                fingerprint_json = json.dumps(fingerprint_data)
                correlation_json = json.dumps(correlation_flags) if correlation_flags else None
                current_time = time.time()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO sophia_inspections 
                    (miner_id, attestation_hash, fingerprint_data, verdict, confidence_score,
                     sophia_reasoning, timestamp, block_height, correlation_flags)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (miner_id, attestation_hash, fingerprint_json, verdict, confidence_score,
                      reasoning, current_time, block_height, correlation_json))
                
                self._update_verdict_history(cursor, miner_id, verdict, confidence_score, current_time)
                conn.commit()
                return True
                
        except sqlite3.Error:
            return False
    
    def _update_verdict_history(self, cursor, miner_id: str, verdict: str, 
                               confidence: float, timestamp: float):
        cursor.execute('SELECT * FROM sophia_verdict_history WHERE miner_id = ?', (miner_id,))
        existing = cursor.fetchone()
        
        if existing:
            ok_count = existing[2]
            suspicious_count = existing[3]
            failed_count = existing[4]
            avg_conf = existing[5]
            total_verdicts = ok_count + suspicious_count + failed_count
            
            if verdict == 'OK':
                ok_count += 1
            elif verdict == 'SUSPICIOUS':
                suspicious_count += 1
            elif verdict == 'FAILED':
                failed_count += 1
            
            new_total = total_verdicts + 1
            new_avg_conf = ((avg_conf * total_verdicts) + confidence) / new_total
            reputation = self._calculate_reputation(ok_count, suspicious_count, failed_count, new_avg_conf)
            
            cursor.execute('''
                UPDATE sophia_verdict_history 
                SET verdict_count_ok = ?, verdict_count_suspicious = ?, verdict_count_failed = ?,
                    avg_confidence = ?, last_inspection = ?, reputation_score = ?, updated_at = ?
                WHERE miner_id = ?
            ''', (ok_count, suspicious_count, failed_count, new_avg_conf, 
                  timestamp, reputation, timestamp, miner_id))
        else:
            ok_count = 1 if verdict == 'OK' else 0
            suspicious_count = 1 if verdict == 'SUSPICIOUS' else 0 
            failed_count = 1 if verdict == 'FAILED' else 0
            reputation = self._calculate_reputation(ok_count, suspicious_count, failed_count, confidence)
            
            cursor.execute('''
                INSERT INTO sophia_verdict_history
                (miner_id, verdict_count_ok, verdict_count_suspicious, verdict_count_failed,
                 avg_confidence, last_inspection, reputation_score, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (miner_id, ok_count, suspicious_count, failed_count, 
                  confidence, timestamp, reputation, timestamp))
    
    def _calculate_reputation(self, ok: int, suspicious: int, failed: int, avg_conf: float) -> float:
        total = ok + suspicious + failed
        if total == 0:
            return 0.0
        
        ok_ratio = ok / total
        fail_penalty = (suspicious * 0.3 + failed * 0.7) / total
        confidence_factor = avg_conf / 100.0
        
        reputation = (ok_ratio - fail_penalty) * confidence_factor * 100.0
        return max(0.0, min(100.0, reputation))
    
    def get_miner_sophia_status(self, miner_id: str) -> Optional[Dict]:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT verdict_count_ok, verdict_count_suspicious, verdict_count_failed,
                       avg_confidence, last_inspection, reputation_score
                FROM sophia_verdict_history WHERE miner_id = ?
            ''', (miner_id,))
            
            result = cursor.fetchone()
            if not result:
                return None
            
            cursor.execute('''
                SELECT verdict, confidence_score, timestamp 
                FROM sophia_inspections 
                WHERE miner_id = ? 
                ORDER BY timestamp DESC LIMIT 1
            ''', (miner_id,))
            
            latest = cursor.fetchone()
            
            return {
                'miner_id': miner_id,
                'verdict_counts': {
                    'ok': result[0],
                    'suspicious': result[1], 
                    'failed': result[2]
                },
                'avg_confidence': result[3],
                'last_inspection': result[4],
                'reputation_score': result[5],
                'latest_verdict': latest[0] if latest else None,
                'latest_confidence': latest[1] if latest else None,
                'latest_timestamp': latest[2] if latest else None
            }
    
    def get_inspection_history(self, miner_id: str, limit: int = 50) -> List[Dict]:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT attestation_hash, verdict, confidence_score, sophia_reasoning,
                       timestamp, block_height, correlation_flags
                FROM sophia_inspections 
                WHERE miner_id = ?
                ORDER BY timestamp DESC LIMIT ?
            ''', (miner_id, limit))
            
            results = []
            for row in cursor.fetchall():
                correlation_flags = json.loads(row[6]) if row[6] else []
                results.append({
                    'attestation_hash': row[0],
                    'verdict': row[1],
                    'confidence_score': row[2],
                    'reasoning': row[3],
                    'timestamp': row[4],
                    'block_height': row[5],
                    'correlation_flags': correlation_flags
                })
            
            return results
    
    def get_sophia_stats(self) -> Dict:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM sophia_inspections')
            total_inspections = cursor.fetchone()[0]
            
            cursor.execute('''
                SELECT verdict, COUNT(*) FROM sophia_inspections 
                GROUP BY verdict
            ''')
            verdict_counts = dict(cursor.fetchall())
            
            cursor.execute('SELECT AVG(confidence_score) FROM sophia_inspections')
            avg_confidence = cursor.fetchone()[0] or 0.0
            
            cursor.execute('''
                SELECT COUNT(DISTINCT miner_id) FROM sophia_inspections
            ''')
            unique_miners = cursor.fetchone()[0]
            
            return {
                'total_inspections': total_inspections,
                'verdict_distribution': verdict_counts,
                'average_confidence': round(avg_confidence, 2),
                'unique_miners_inspected': unique_miners
            }
    
    def update_model_status(self, model_name: str, model_version: str, 
                           status: str, response_time: float = None):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            current_time = time.time()
            
            cursor.execute('''
                INSERT OR REPLACE INTO sophia_model_status
                (id, model_name, model_version, last_health_check, status, avg_response_time)
                VALUES (1, ?, ?, ?, ?, ?)
            ''', (model_name, model_version, current_time, status, response_time or 0.0))
            
            conn.commit()
    
    def get_model_status(self) -> Optional[Dict]:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM sophia_model_status WHERE id = 1')
            result = cursor.fetchone()
            
            if not result:
                return None
            
            return {
                'model_name': result[1],
                'model_version': result[2],
                'last_health_check': result[3],
                'status': result[4],
                'total_inspections': result[5],
                'avg_response_time': result[6],
                'error_rate': result[7]
            }