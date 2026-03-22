"""
Subscription management for BoTTube Telegram Bot
Bonus feature: Get notified when your favorite agents upload new videos
"""

import sqlite3
from typing import List, Tuple

class SubscriptionManager:
    def __init__(self, db_path: str = "bottube_subscriptions.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                chat_id INTEGER NOT NULL,
                agent_name TEXT NOT NULL,
                PRIMARY KEY (chat_id, agent_name)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS last_check (
                agent_name TEXT PRIMARY KEY,
                last_video_id TEXT NOT NULL
            )
        """)
        
        conn.commit()
        conn.close()
    
    def subscribe(self, chat_id: int, agent_name: str) -> bool:
        """Subscribe a chat to an agent's uploads."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "INSERT INTO subscriptions (chat_id, agent_name) VALUES (?, ?)",
                (chat_id, agent_name)
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Already subscribed
            return False
        finally:
            conn.close()
    
    def unsubscribe(self, chat_id: int, agent_name: str) -> bool:
        """Unsubscribe a chat from an agent's uploads."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "DELETE FROM subscriptions WHERE chat_id = ? AND agent_name = ?",
            (chat_id, agent_name)
        )
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        return deleted
    
    def get_subscriptions(self, chat_id: int) -> List[str]:
        """Get all subscribed agents for a chat."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT agent_name FROM subscriptions WHERE chat_id = ?",
            (chat_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows]
    
    def get_all_subscriptions(self) -> List[Tuple[int, str]]:
        """Get all subscriptions across all chats."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT chat_id, agent_name FROM subscriptions")
        rows = cursor.fetchall()
        conn.close()
        return rows
    
    def update_last_check(self, agent_name: str, last_video_id: str) -> None:
        """Update the last checked video ID for an agent."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            REPLACE INTO last_check (agent_name, last_video_id)
            VALUES (?, ?)
        """, (agent_name, last_video_id))
        
        conn.commit()
        conn.close()
    
    def get_last_check(self, agent_name: str) -> Optional[str]:
        """Get the last checked video ID for an agent."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT last_video_id FROM last_check WHERE agent_name = ?",
            (agent_name,)
        )
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
