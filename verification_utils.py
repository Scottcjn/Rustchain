# SPDX-License-Identifier: MIT

import re
import sqlite3
from urllib.parse import urlparse
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import json
from typing import Dict, List, Tuple, Optional
import html
from html.parser import HTMLParser


DB_PATH = 'rustchain.db'


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_content = []
        self.in_script = False
        self.in_style = False

    def handle_starttag(self, tag, attrs):
        if tag.lower() in ['script', 'style']:
            self.in_script = True
            self.in_style = True

    def handle_endtag(self, tag):
        if tag.lower() in ['script', 'style']:
            self.in_script = False
            self.in_style = False

    def handle_data(self, data):
        if not self.in_script and not self.in_style:
            self.text_content.append(data)

    def get_text(self):
        return ' '.join(self.text_content)


def is_valid_url(url: str) -> bool:
    """Check if URL has valid format"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def check_url_accessible(url: str, timeout: int = 10) -> Tuple[bool, Optional[str]]:
    """Check if URL is accessible and return content if successful"""
    if not is_valid_url(url):
        return False, None

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        req = Request(url, headers=headers)

        with urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                content = response.read().decode('utf-8', errors='ignore')
                return True, content
            return False, None

    except (URLError, HTTPError, Exception):
        return False, None


def extract_text_from_html(html_content: str) -> str:
    """Extract readable text from HTML content"""
    if not html_content:
        return ""

    parser = TextExtractor()
    try:
        parser.feed(html_content)
        text = parser.get_text()
        # Clean up whitespace
        text = ' '.join(text.split())
        return text
    except Exception:
        return ""


def count_words(text: str) -> int:
    """Count words in text, excluding common stop words"""
    if not text:
        return 0

    # Simple word counting - split on whitespace and punctuation
    words = re.findall(r'\b[a-zA-Z]+\b', text.lower())

    # Filter out very common words that don't add much value
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
        'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
        'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we',
        'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his', 'her',
        'its', 'our', 'their'
    }

    meaningful_words = [w for w in words if w not in stop_words and len(w) > 2]
    return len(meaningful_words)


def analyze_article_quality(content: str) -> Dict[str, any]:
    """Analyze article content for quality metrics"""
    text = extract_text_from_html(content) if '<' in content else content
    word_count = count_words(text)

    # Basic quality indicators
    has_code = bool(re.search(r'```|<code>|<pre>', content))
    has_headers = bool(re.search(r'<h[1-6]>|#{1,6}\s', content))
    paragraph_count = len([p for p in text.split('\n\n') if p.strip()])

    # Estimate reading time (assuming 200 words per minute)
    reading_time = max(1, word_count // 200)

    quality_score = 0
    if word_count >= 300:
        quality_score += 2
    if word_count >= 600:
        quality_score += 2
    if has_code:
        quality_score += 2
    if has_headers:
        quality_score += 1
    if paragraph_count >= 3:
        quality_score += 1

    return {
        'word_count': word_count,
        'has_code': has_code,
        'has_headers': has_headers,
        'paragraph_count': paragraph_count,
        'reading_time': reading_time,
        'quality_score': quality_score
    }


def check_duplicate_claim(username: str, bounty_id: str) -> Tuple[bool, Optional[str]]:
    """Check if user has already claimed this bounty"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Check for existing claims
            cursor.execute("""
                SELECT created_at, status FROM bounty_claims
                WHERE username = ? AND bounty_id = ?
                ORDER BY created_at DESC LIMIT 1
            """, (username, bounty_id))

            result = cursor.fetchone()
            if result:
                created_at, status = result
                return True, f"Previous claim on {created_at} (Status: {status})"

            return False, None

    except sqlite3.Error:
        return False, "Database error"


def format_verification_table(results: Dict[str, any]) -> str:
    """Format verification results into markdown table"""
    table_rows = []

    # Header
    table_rows.append("| Check | Status | Details |")
    table_rows.append("|-------|---------|---------|")

    # Add each result
    for check_name, result in results.items():
        if isinstance(result, dict):
            status = "✅ Pass" if result.get('success', False) else "❌ Fail"
            details = result.get('details', 'No details')
        else:
            status = "✅ Pass" if result else "❌ Fail"
            details = "-"

        # Escape pipe characters in details
        details = str(details).replace('|', '\\|')
        table_rows.append(f"| {check_name} | {status} | {details} |")

    return '\n'.join(table_rows)


def validate_dev_to_url(url: str) -> bool:
    """Check if URL is a valid dev.to article"""
    if not url:
        return False

    dev_to_patterns = [
        r'https?://dev\.to/[\w-]+/[\w-]+',
        r'https?://[\w-]+\.dev\.to/[\w-]+'
    ]

    return any(re.match(pattern, url) for pattern in dev_to_patterns)


def validate_medium_url(url: str) -> bool:
    """Check if URL is a valid Medium article"""
    if not url:
        return False

    medium_patterns = [
        r'https?://medium\.com/@?[\w-]+/[\w-]+',
        r'https?://[\w-]+\.medium\.com/[\w-]+',
        r'https?://link\.medium\.com/[\w-]+'
    ]

    return any(re.match(pattern, url) for pattern in medium_patterns)


def create_bounty_claims_table():
    """Initialize the bounty claims table if it doesn't exist"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bounty_claims (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    bounty_id TEXT NOT NULL,
                    claim_type TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    verification_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")


def store_verification_result(username: str, bounty_id: str, claim_type: str,
                            verification_data: Dict, status: str = 'verified'):
    """Store verification results in database"""
    create_bounty_claims_table()

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO bounty_claims
                (username, bounty_id, claim_type, status, verification_data)
                VALUES (?, ?, ?, ?, ?)
            """, (username, bounty_id, claim_type, status, json.dumps(verification_data)))
            conn.commit()
    except sqlite3.Error as e:
        print(f"Failed to store verification: {e}")
