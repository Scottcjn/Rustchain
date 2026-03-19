// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import json
import re
import time
import hashlib
import requests
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

DB_PATH = "bounty_bot_pro.db"
RUSTCHAIN_NODE_URL = "http://localhost:3000"
GEMINI_API_KEY = "your_gemini_api_key_here"

@dataclass
class QualityScore:
    technical_depth: float
    clarity: float
    originality: float
    total: float
    feedback: str

@dataclass
class BountySubmission:
    id: str
    wallet_address: str
    content_url: str
    submission_type: str
    timestamp: int
    quality_score: Optional[QualityScore] = None
    wallet_verified: bool = False
    star_king_bonus: bool = False
    status: str = "pending"

class RustChainNodeClient:
    def __init__(self, node_url: str):
        self.node_url = node_url.rstrip('/')
    
    def verify_wallet(self, wallet_address: str) -> Tuple[bool, float]:
        try:
            response = requests.get(f"{self.node_url}/wallet/balance/{wallet_address}")
            if response.status_code == 200:
                data = response.json()
                balance = float(data.get('balance', 0))
                return True, balance
            return False, 0.0
        except Exception as e:
            print(f"Wallet verification failed: {e}")
            return False, 0.0
    
    def check_star_king_status(self, wallet_address: str) -> bool:
        try:
            response = requests.get(f"{self.node_url}/wallet/metadata/{wallet_address}")
            if response.status_code == 200:
                data = response.json()
                return data.get('star_king', False) or data.get('balance', 0) >= 1000000
            return False
        except:
            return False

class GeminiContentAnalyzer:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent"
    
    def extract_content(self, url: str) -> str:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                text = re.sub(r'<[^>]+>', ' ', response.text)
                text = re.sub(r'\s+', ' ', text).strip()
                return text[:5000]
            return ""
        except:
            return ""
    
    def score_content(self, content: str, submission_type: str) -> QualityScore:
        prompt = f"""
        Evaluate this {submission_type} content for a blockchain bounty program:

        Content: {content[:2000]}

        Score on a scale of 0-10:
        1. Technical Depth - How technically accurate and detailed is the content?
        2. Clarity - How well is the information presented and structured?
        3. Originality - How unique and innovative is the content?

        Respond with JSON format:
        {{"technical_depth": X, "clarity": X, "originality": X, "feedback": "brief explanation"}}
        """
        
        try:
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.3}
            }
            
            response = requests.post(
                f"{self.api_url}?key={self.api_key}",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                text_response = result["candidates"][0]["content"]["parts"][0]["text"]
                
                json_match = re.search(r'\{.*\}', text_response, re.DOTALL)
                if json_match:
                    scores = json.loads(json_match.group())
                    technical = min(10, max(0, float(scores.get("technical_depth", 5))))
                    clarity = min(10, max(0, float(scores.get("clarity", 5))))
                    originality = min(10, max(0, float(scores.get("originality", 5))))
                    total = (technical + clarity + originality) / 3
                    
                    return QualityScore(
                        technical_depth=technical,
                        clarity=clarity,
                        originality=originality,
                        total=total,
                        feedback=scores.get("feedback", "No feedback provided")
                    )
        except Exception as e:
            print(f"AI scoring failed: {e}")
        
        return QualityScore(5.0, 5.0, 5.0, 5.0, "Default scoring due to analysis failure")

class BountyBotPro:
    def __init__(self):
        self.node_client = RustChainNodeClient(RUSTCHAIN_NODE_URL)
        self.ai_analyzer = GeminiContentAnalyzer(GEMINI_API_KEY)
        self.init_database()
    
    def init_database(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS bounty_submissions (
                    id TEXT PRIMARY KEY,
                    wallet_address TEXT NOT NULL,
                    content_url TEXT NOT NULL,
                    submission_type TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    technical_depth REAL,
                    clarity REAL,
                    originality REAL,
                    total_score REAL,
                    feedback TEXT,
                    wallet_verified INTEGER,
                    wallet_balance REAL,
                    star_king_bonus INTEGER,
                    status TEXT DEFAULT 'pending',
                    processed_at INTEGER
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS quality_metrics (
                    date TEXT PRIMARY KEY,
                    submissions_count INTEGER,
                    avg_technical_depth REAL,
                    avg_clarity REAL,
                    avg_originality REAL,
                    avg_total_score REAL,
                    high_quality_count INTEGER,
                    star_king_submissions INTEGER
                )
            ''')
    
    def generate_submission_id(self, wallet_address: str, content_url: str) -> str:
        data = f"{wallet_address}:{content_url}:{int(time.time())}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def submit_bounty(self, wallet_address: str, content_url: str, submission_type: str) -> Dict:
        submission_id = self.generate_submission_id(wallet_address, content_url)
        
        with sqlite3.connect(DB_PATH) as conn:
            existing = conn.execute(
                "SELECT id FROM bounty_submissions WHERE wallet_address = ? AND content_url = ?",
                (wallet_address, content_url)
            ).fetchone()
            
            if existing:
                return {"success": False, "error": "Duplicate submission"}
        
        submission = BountySubmission(
            id=submission_id,
            wallet_address=wallet_address,
            content_url=content_url,
            submission_type=submission_type,
            timestamp=int(time.time())
        )
        
        self.process_submission(submission)
        
        return {
            "success": True,
            "submission_id": submission_id,
            "status": submission.status,
            "quality_score": submission.quality_score.total if submission.quality_score else 0
        }
    
    def process_submission(self, submission: BountySubmission):
        wallet_verified, balance = self.node_client.verify_wallet(submission.wallet_address)
        submission.wallet_verified = wallet_verified
        
        if wallet_verified:
            submission.star_king_bonus = self.node_client.check_star_king_status(submission.wallet_address)
        
        content = self.ai_analyzer.extract_content(submission.content_url)
        if content:
            submission.quality_score = self.ai_analyzer.score_content(content, submission.submission_type)
        
        if submission.quality_score and submission.quality_score.total >= 6.0 and wallet_verified:
            submission.status = "approved"
        elif not wallet_verified:
            submission.status = "rejected_wallet"
        elif submission.quality_score and submission.quality_score.total < 4.0:
            submission.status = "rejected_quality"
        else:
            submission.status = "review_needed"
        
        self.save_submission(submission, balance)
    
    def save_submission(self, submission: BountySubmission, balance: float):
        with sqlite3.connect(DB_PATH) as conn:
            qs = submission.quality_score
            conn.execute('''
                INSERT INTO bounty_submissions (
                    id, wallet_address, content_url, submission_type, timestamp,
                    technical_depth, clarity, originality, total_score, feedback,
                    wallet_verified, wallet_balance, star_king_bonus, status, processed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                submission.id, submission.wallet_address, submission.content_url,
                submission.submission_type, submission.timestamp,
                qs.technical_depth if qs else None,
                qs.clarity if qs else None,
                qs.originality if qs else None,
                qs.total if qs else None,
                qs.feedback if qs else None,
                1 if submission.wallet_verified else 0,
                balance,
                1 if submission.star_king_bonus else 0,
                submission.status,
                int(time.time())
            ))
    
    def get_submission_status(self, submission_id: str) -> Dict:
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute('''
                SELECT id, wallet_address, content_url, submission_type, status,
                       technical_depth, clarity, originality, total_score, feedback,
                       wallet_verified, star_king_bonus
                FROM bounty_submissions WHERE id = ?
            ''', (submission_id,)).fetchone()
            
            if not row:
                return {"error": "Submission not found"}
            
            return {
                "submission_id": row[0],
                "wallet_address": row[1],
                "content_url": row[2],
                "submission_type": row[3],
                "status": row[4],
                "quality_scores": {
                    "technical_depth": row[5],
                    "clarity": row[6],
                    "originality": row[7],
                    "total": row[8]
                },
                "feedback": row[9],
                "wallet_verified": bool(row[10]),
                "star_king_bonus": bool(row[11])
            }
    
    def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute('''
                SELECT wallet_address, AVG(total_score) as avg_score,
                       COUNT(*) as submission_count,
                       SUM(CASE WHEN star_king_bonus = 1 THEN 1 ELSE 0 END) as star_king_submissions
                FROM bounty_submissions
                WHERE status = 'approved' AND total_score IS NOT NULL
                GROUP BY wallet_address
                ORDER BY avg_score DESC, submission_count DESC
                LIMIT ?
            ''', (limit,)).fetchall()
            
            return [{
                "wallet_address": row[0],
                "average_quality_score": round(row[1], 2),
                "approved_submissions": row[2],
                "star_king_submissions": row[3]
            } for row in rows]
    
    def get_analytics(self) -> Dict:
        with sqlite3.connect(DB_PATH) as conn:
            stats = conn.execute('''
                SELECT 
                    COUNT(*) as total_submissions,
                    AVG(total_score) as avg_quality,
                    COUNT(CASE WHEN status = 'approved' THEN 1 END) as approved_count,
                    COUNT(CASE WHEN star_king_bonus = 1 THEN 1 END) as star_king_count,
                    COUNT(CASE WHEN wallet_verified = 1 THEN 1 END) as verified_wallets
                FROM bounty_submissions
                WHERE total_score IS NOT NULL
            ''').fetchone()
            
            return {
                "total_submissions": stats[0],
                "average_quality_score": round(stats[1] or 0, 2),
                "approval_rate": round((stats[2] / max(stats[0], 1)) * 100, 2),
                "star_king_submissions": stats[3],
                "wallet_verification_rate": round((stats[4] / max(stats[0], 1)) * 100, 2)
            }

def main():
    bot = BountyBotPro()
    
    test_submission = bot.submit_bounty(
        wallet_address="rust1test2024wallet",
        content_url="https://example.com/blockchain-tutorial",
        submission_type="tutorial"
    )
    
    print("Test submission result:", test_submission)
    print("Analytics:", bot.get_analytics())
    print("Leaderboard:", bot.get_leaderboard(5))

if __name__ == "__main__":
    main()