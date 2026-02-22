"""
Generic Rate Limiting Module for RustChain Beacon Atlas API

Implements sliding window rate limiting with SQLite backend for persistence
across gunicorn workers. Supports different limits for read/write operations.

Usage:
    from rate_limiting import rate_limit
    
    @app.route('/api/endpoint', methods=['POST'])
    @rate_limit(calls_per_minute=10, key_prefix="write")
    def my_endpoint():
        return jsonify({"status": "ok"})
"""

import sqlite3
import time
from functools import wraps
from flask import request, jsonify


# Database path (should match existing DB_PATH in main app)
DB_PATH = "beacon_atlas.db"

# Rate limit configuration
WRITE_LIMIT = 10    # requests per minute for write operations
READ_LIMIT = 60     # requests per minute for read operations


def init_rate_limit_tables():
    """Initialize rate limiting tables in the database"""
    with sqlite3.connect(DB_PATH) as conn:
        # Table for write operations (POST, PUT, DELETE)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rate_limit_write (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_ip TEXT,
                ts INTEGER
            )
        """)
        
        # Table for read operations (GET)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rate_limit_read (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_ip TEXT,
                ts INTEGER
            )
        """)
        
        # Create indexes for better performance
        conn.execute("CREATE INDEX IF NOT EXISTS idx_write_ts ON rate_limit_write(ts)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_read_ts ON rate_limit_read(ts)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_write_ip ON rate_limit_write(client_ip)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_read_ip ON rate_limit_read(client_ip)")


def check_rate_limit(client_ip, max_calls, period_seconds, table_name):
    """
    Check if a client IP is within rate limits.
    
    Args:
        client_ip (str): Client IP address
        max_calls (int): Maximum number of calls allowed
        period_seconds (int): Time window in seconds
        table_name (str): Database table name to use
        
    Returns:
        bool: True if within limits, False if rate limited
    """
    now = int(time.time())
    cutoff = now - period_seconds
    
    with sqlite3.connect(DB_PATH) as conn:
        # Clean up old entries outside the time window
        conn.execute(f"DELETE FROM {table_name} WHERE ts < ?", (cutoff,))
        
        # Count current requests within the time window
        row = conn.execute(
            f"SELECT COUNT(*) FROM {table_name} WHERE client_ip = ? AND ts >= ?",
            (client_ip, cutoff)
        ).fetchone()
        current_count = row[0] if row else 0
        
        if current_count >= max_calls:
            return False
        
        # Add the current request
        conn.execute(
            f"INSERT INTO {table_name} (client_ip, ts) VALUES (?, ?)",
            (client_ip, now)
        )
        return True


def get_client_ip():
    """Extract client IP from Flask request (handle proxies)"""
    # Handle nginx proxy headers
    if request.headers.get('X-Forwarded-For'):
        ip = request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        ip = request.headers.get('X-Real-IP')
    else:
        ip = request.remote_addr or '127.0.0.1'
    return ip


def rate_limit(calls_per_minute=10, key_prefix="write"):
    """
    Flask decorator for rate limiting endpoints.
    
    Args:
        calls_per_minute (int): Maximum calls per minute
        key_prefix (str): Table prefix ('write' or 'read')
        
    Returns:
        decorator function
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = get_client_ip()
            period = 60  # 1 minute window
            
            # Determine which table to use based on key_prefix
            if key_prefix == "write":
                table_name = "rate_limit_write"
                max_calls = WRITE_LIMIT
            elif key_prefix == "read":
                table_name = "rate_limit_read"
                max_calls = READ_LIMIT
            else:
                table_name = f"rate_limit_{key_prefix}"
                max_calls = calls_per_minute
            
            # Check rate limit
            if not check_rate_limit(client_ip, max_calls, period, table_name):
                retry_after = 60  # 1 minute
                return jsonify({
                    "error": "rate_limited",
                    "message": f"Rate limit exceeded. Please try again in {retry_after} seconds."
                }), 429, {"Retry-After": str(retry_after)}
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# Initialize tables when module is imported
try:
    init_rate_limit_tables()
except Exception as e:
    print(f"[RATE_LIMIT] Warning: Failed to initialize rate limit tables: {e}")