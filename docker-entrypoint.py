#!/usr/bin/env python3
"""
RustChain Node Entrypoint with Health Check
============================================

Docker container entrypoint that adds a /health endpoint to the RustChain dashboard.

Purpose:
    - Provides Docker healthcheck endpoint for container orchestration
    - Monitors database connectivity and service status
    - Returns structured JSON health status

Integration:
    This module imports the Flask app from rustchain_dashboard and adds
    a /health route before starting the server.

Docker Usage:
    docker run -p 8099:8099 \\
        -e RUSTCHAIN_DB=/rustchain/data/rustchain_v2.db \\
        --health-cmd="curl -f http://localhost:8099/health || exit 1" \\
        --health-interval=30s \\
        --health-timeout=10s \\
        --health-retries=3 \\
        rustchain-node

Environment Variables:
    RUSTCHAIN_DB: Path to SQLite database (default: /rustchain/data/rustchain_v2.db)
    PORT: HTTP server port (default: 8099)

Health Response Format:
    {
        "status": "healthy" | "unhealthy",
        "database": "ok" | "initializing" | "error",
        "version": "2.2.1-docker"
    }

Author: Elyan Labs
Date: 2026-03
"""

from __future__ import annotations

import sys
import os
import sqlite3
from typing import Any, Dict, Tuple

from flask import jsonify

# Add node directory to path for imports
sys.path.insert(0, '/app/node')

# Import the Flask app from rustchain_dashboard
from rustchain_dashboard import app


@app.route('/health')
def health_check() -> Tuple[Dict[str, Any], int]:
    """
    Docker healthcheck endpoint for container orchestration.
    
    Purpose:
        - Verify database connectivity
        - Report service health status to Docker
        - Enable automatic container restart on failure
    
    Health Check Logic:
        1. Check if database file exists
        2. Attempt SQLite connection with 5s timeout
        3. Execute simple query (SELECT 1) to verify DB is responsive
        4. Return structured JSON status
    
    Returns:
        Tuple[Dict[str, Any], int]: JSON response and HTTP status code
        - 200: Service healthy, database accessible
        - 503: Service unhealthy, database error
    
    Response Fields:
        status: "healthy" or "unhealthy"
        database: "ok", "initializing", or error message
        version: Service version string
    
    Docker Integration:
        Used by Docker HEALTHCHECK instruction:
        HEALTHCHECK --interval=30s --timeout=10s --retries=3 \\
            CMD curl -f http://localhost:8099/health || exit 1
    
    Example Response (200 OK):
        {
            "status": "healthy",
            "database": "ok",
            "version": "2.2.1-docker"
        }
    
    Example Response (503 Service Unavailable):
        {
            "status": "unhealthy",
            "error": "database is locked"
        }
    
    Note:
        - Database path from RUSTCHAIN_DB env var
        - Defaults to /rustchain/data/rustchain_v2.db
        - "initializing" status means DB file doesn't exist yet (first run)
    """
    try:
        # Get database path from environment
        db_path: str = os.environ.get('RUSTCHAIN_DB', '/rustchain/data/rustchain_v2.db')
        
        # Check database connectivity
        if os.path.exists(db_path):
            # DB exists, test connection
            conn = sqlite3.connect(db_path, timeout=5)
            conn.execute('SELECT 1')  # Simple query to verify DB is responsive
            conn.close()
            db_status: str = 'ok'
        else:
            # DB file doesn't exist yet (first run, will be created)
            db_status = 'initializing'
        
        return jsonify({
            'status': 'healthy',
            'database': db_status,
            'version': '2.2.1-docker'
        }), 200
        
    except sqlite3.Error as e:
        # Database-specific errors (locked, corrupted, etc.)
        return jsonify({
            'status': 'unhealthy',
            'error': f'Database error: {str(e)}',
            'database': 'error'
        }), 503
        
    except Exception as e:
        # Generic errors
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 503


if __name__ == '__main__':
    """
    Main entrypoint for running the Flask server.
    
    Configuration:
        - Host: 0.0.0.0 (all interfaces, required for Docker)
        - Port: From PORT env var or default 8099
        - Debug: Disabled (production mode)
    
    Usage:
        python3 docker-entrypoint.py
    
    Or with custom port:
        PORT=9000 python3 docker-entrypoint.py
    """
    # Get port from environment or use default
    port: int = int(os.environ.get('PORT', 8099))
    
    print(f"🐳 RustChain Node starting on port {port}")
    print(f"   Health check: http://0.0.0.0:{port}/health")
    print(f"   Database: {os.environ.get('RUSTCHAIN_DB', '/rustchain/data/rustchain_v2.db')}")
    
    # Run Flask app (production mode, debug=False)
    app.run(host='0.0.0.0', port=port, debug=False)
