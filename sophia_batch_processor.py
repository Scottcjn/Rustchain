// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import json
import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import requests
import hashlib

DB_PATH = "rustchain.db"
SOPHIA_MODEL = "elyan-sophia:7b-q4_K_M"
OLLAMA_URL = "http://localhost:11434"

class SophiaBatchProcessor:
    def __init__(self):
        self.running = False
        self.thread = None
        self.last_batch_run = None
        self.setup_logging()
        
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - SophiaCore - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._batch_loop)
            self.thread.daemon = True
            self.thread.start()
            self.logger.info("Sophia batch processor started")
            
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
        self.logger.info("Sophia batch processor stopped")
        
    def _batch_loop(self):
        while self.running:
            try:
                if self._should_run_batch():
                    self._process_batch()
                    self.last_batch_run = datetime.now()
                time.sleep(3600)  # Check hourly
            except Exception as e:
                self.logger.error(f"Batch loop error: {e}")
                time.sleep(300)  # Wait 5 min on error
                
    def _should_run_batch(self):
        if not self.last_batch_run:
            return True
        return datetime.now() - self.last_batch_run > timedelta(hours=24)
        
    def _process_batch(self):
        self.logger.info("Starting Sophia batch attestation analysis")
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Get unprocessed attestations from last 24h
            cursor.execute("""
                SELECT miner_id, attestation_data, timestamp 
                FROM hardware_attestations 
                WHERE sophia_verdict IS NULL 
                AND timestamp > datetime('now', '-24 hours')
                ORDER BY timestamp DESC
            """)
            
            attestations = cursor.fetchall()
            self.logger.info(f"Processing {len(attestations)} attestations")
            
            for miner_id, attestation_data, timestamp in attestations:
                try:
                    verdict = self._analyze_attestation(attestation_data)
                    self._store_verdict(conn, miner_id, verdict, timestamp)
                except Exception as e:
                    self.logger.error(f"Failed to analyze {miner_id}: {e}")
                    
        self.logger.info("Batch processing complete")
        
    def _analyze_attestation(self, attestation_data: str) -> Dict:
        data = json.loads(attestation_data)
        
        prompt = self._build_analysis_prompt(data)
        response = self._query_sophia(prompt)
        verdict = self._parse_verdict(response)
        
        return verdict
        
    def _build_analysis_prompt(self, data: Dict) -> str:
        fingerprint_summary = self._summarize_fingerprint(data)
        
        prompt = f"""Sophia Elya attestation analysis:

Hardware fingerprint data:
{fingerprint_summary}

Analyze this hardware fingerprint bundle for authenticity. Real hardware shows correlated imperfections and natural variance patterns. Spoofed data often has independently tuned values that lack realistic correlations.

Provide verdict as JSON:
{{
  "authentic": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "brief analysis",
  "anomalies": ["list", "of", "concerns"]
}}"""

        return prompt
        
    def _summarize_fingerprint(self, data: Dict) -> str:
        summary_parts = []
        
        if 'cpu_info' in data:
            cpu = data['cpu_info']
            summary_parts.append(f"CPU: {cpu.get('model', 'unknown')} @ {cpu.get('frequency', 'unknown')}MHz")
            
        if 'memory_info' in data:
            mem = data['memory_info']
            summary_parts.append(f"Memory: {mem.get('total_mb', 'unknown')}MB, {mem.get('type', 'unknown')}")
            
        if 'thermal_readings' in data:
            temps = data['thermal_readings']
            avg_temp = sum(temps) / len(temps) if temps else 0
            summary_parts.append(f"Thermal: avg {avg_temp:.1f}°C, range {min(temps):.1f}-{max(temps):.1f}°C")
            
        if 'power_metrics' in data:
            power = data['power_metrics']
            summary_parts.append(f"Power: {power.get('consumption_watts', 'unknown')}W")
            
        if 'performance_counters' in data:
            perf = data['performance_counters']
            summary_parts.append(f"Performance: {perf.get('instructions_per_second', 'unknown')} IPS")
            
        return '\n'.join(summary_parts)
        
    def _query_sophia(self, prompt: str) -> str:
        try:
            payload = {
                "model": SOPHIA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "top_p": 0.9
                }
            }
            
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '')
            else:
                raise Exception(f"Ollama API error: {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"Sophia query failed: {e}")
            return self._fallback_verdict()
            
    def _fallback_verdict(self) -> str:
        return json.dumps({
            "authentic": True,
            "confidence": 0.5,
            "reasoning": "Sophia analysis unavailable, defaulting to accept",
            "anomalies": ["sophia_offline"]
        })
        
    def _parse_verdict(self, response: str) -> Dict:
        try:
            # Extract JSON from response
            start = response.find('{')
            end = response.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
                verdict = json.loads(json_str)
                
                # Validate required fields
                if all(key in verdict for key in ['authentic', 'confidence', 'reasoning']):
                    verdict['timestamp'] = datetime.now().isoformat()
                    verdict['sophia_version'] = SOPHIA_MODEL
                    return verdict
                    
        except Exception as e:
            self.logger.error(f"Failed to parse verdict: {e}")
            
        return json.loads(self._fallback_verdict())
        
    def _store_verdict(self, conn: sqlite3.Connection, miner_id: str, verdict: Dict, attestation_timestamp: str):
        cursor = conn.cursor()
        
        # Update attestation with Sophia verdict
        cursor.execute("""
            UPDATE hardware_attestations 
            SET sophia_verdict = ?, sophia_confidence = ?, sophia_timestamp = ?
            WHERE miner_id = ? AND timestamp = ?
        """, (
            json.dumps(verdict),
            verdict.get('confidence', 0.5),
            datetime.now().isoformat(),
            miner_id,
            attestation_timestamp
        ))
        
        # Store in sophia_verdicts table
        cursor.execute("""
            INSERT OR REPLACE INTO sophia_verdicts
            (miner_id, verdict_data, confidence_score, authentic, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (
            miner_id,
            json.dumps(verdict),
            verdict.get('confidence', 0.5),
            verdict.get('authentic', True),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        
    def process_on_demand(self, miner_id: str) -> Dict:
        """Immediate attestation analysis for specific miner"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT attestation_data, timestamp 
                FROM hardware_attestations 
                WHERE miner_id = ? 
                ORDER BY timestamp DESC 
                LIMIT 1
            """, (miner_id,))
            
            result = cursor.fetchone()
            if not result:
                return {"error": "No attestation data found"}
                
            attestation_data, timestamp = result
            verdict = self._analyze_attestation(attestation_data)
            self._store_verdict(conn, miner_id, verdict, timestamp)
            
            return verdict
            
    def detect_anomalies(self) -> List[Dict]:
        """Detect miners with suspicious patterns"""
        anomalies = []
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Low confidence scores
            cursor.execute("""
                SELECT miner_id, confidence_score, verdict_data
                FROM sophia_verdicts 
                WHERE confidence_score < 0.7
                AND timestamp > datetime('now', '-7 days')
                ORDER BY confidence_score ASC
            """)
            
            low_confidence = cursor.fetchall()
            for miner_id, confidence, verdict_data in low_confidence:
                anomalies.append({
                    "type": "low_confidence",
                    "miner_id": miner_id,
                    "confidence": confidence,
                    "severity": "medium" if confidence < 0.5 else "low"
                })
                
            # Repeated authentication failures
            cursor.execute("""
                SELECT miner_id, COUNT(*) as failure_count
                FROM sophia_verdicts 
                WHERE authentic = 0
                AND timestamp > datetime('now', '-24 hours')
                GROUP BY miner_id
                HAVING failure_count > 3
            """)
            
            repeat_failures = cursor.fetchall()
            for miner_id, failure_count in repeat_failures:
                anomalies.append({
                    "type": "repeat_failures",
                    "miner_id": miner_id,
                    "failure_count": failure_count,
                    "severity": "high"
                })
                
        return anomalies
        
    def get_verdict_stats(self) -> Dict:
        """Get Sophia verdict statistics"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Overall stats
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_verdicts,
                    AVG(confidence_score) as avg_confidence,
                    SUM(CASE WHEN authentic = 1 THEN 1 ELSE 0 END) as authentic_count,
                    SUM(CASE WHEN authentic = 0 THEN 1 ELSE 0 END) as suspicious_count
                FROM sophia_verdicts
                WHERE timestamp > datetime('now', '-30 days')
            """)
            
            stats = cursor.fetchone()
            
            return {
                "total_verdicts": stats[0] or 0,
                "avg_confidence": round(stats[1] or 0.0, 3),
                "authentic_count": stats[2] or 0,
                "suspicious_count": stats[3] or 0,
                "authenticity_rate": round((stats[2] or 0) / max(stats[0] or 1, 1) * 100, 1)
            }

processor = SophiaBatchProcessor()

def init_sophia_tables():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sophia_verdicts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                miner_id TEXT NOT NULL,
                verdict_data TEXT NOT NULL,
                confidence_score REAL NOT NULL,
                authentic BOOLEAN NOT NULL,
                timestamp TEXT NOT NULL,
                UNIQUE(miner_id, timestamp)
            )
        """)
        
        cursor.execute("""
            ALTER TABLE hardware_attestations 
            ADD COLUMN sophia_verdict TEXT
        """)
        
        cursor.execute("""
            ALTER TABLE hardware_attestations 
            ADD COLUMN sophia_confidence REAL
        """)
        
        cursor.execute("""
            ALTER TABLE hardware_attestations 
            ADD COLUMN sophia_timestamp TEXT
        """)
        
        conn.commit()

if __name__ == "__main__":
    init_sophia_tables()
    processor.start()
    
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        processor.stop()