// SPDX-License-Identifier: MIT
#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import sqlite3
import os

DB_PATH = 'music_submissions.db'

def create_music_submissions_table():
    """Initialize the music submissions database"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS music_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submitter_address TEXT NOT NULL,
                title TEXT NOT NULL,
                genre TEXT,
                duration INTEGER NOT NULL,
                audio_file_path TEXT NOT NULL,
                lyrics_file_path TEXT,
                description TEXT,
                references_rustchain INTEGER DEFAULT 0,
                references_rtc INTEGER DEFAULT 0,
                references_poa INTEGER DEFAULT 0,
                references_vintage_hw INTEGER DEFAULT 0,
                references_cpu_vote INTEGER DEFAULT 0,
                references_mining INTEGER DEFAULT 0,
                total_references INTEGER DEFAULT 0,
                reward_amount REAL DEFAULT 0.0,
                paid INTEGER DEFAULT 0,
                submission_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                review_status TEXT DEFAULT 'pending'
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS music_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER NOT NULL,
                reviewer TEXT,
                score INTEGER CHECK(score >= 1 AND score <= 10),
                bonus_points INTEGER DEFAULT 0,
                notes TEXT,
                review_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (submission_id) REFERENCES music_submissions (id)
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_submissions_status 
            ON music_submissions(review_status)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_submissions_paid 
            ON music_submissions(paid)
        ''')
        
        conn.commit()
        print(f"Music submissions database created: {DB_PATH}")

if __name__ == '__main__':
    create_music_submissions_table()