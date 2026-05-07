#!/usr/bin/env python3
"""
RustChain Node Entrypoint with Health Check
Adds a /health endpoint to rustchain_dashboard.py
"""
import sys
import os

# Add node directory to path
sys.path.insert(0, '/app/node')

# Import the Flask app from rustchain_dashboard
from rustchain_dashboard import app

# Add health check endpoint
@app.route('/health')
def health_check():
    """Simple health check endpoint for Docker healthcheck"""
    import sqlite3
    from flask import jsonify
    
    try:
        # Check if database is accessible
        db_path = os.environ.get('RUSTCHAIN_DB', '/rustchain/data/rustchain_v2.db')
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path, timeout=5)
            conn.execute('SELECT 1')
            conn.close()
            db_status = 'ok'
        else:
            db_status = 'initializing'
        
        return jsonify({
            'status': 'healthy',
            'database': db_status,
            'version': '2.2.1-docker'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': 'Internal error'
        }), 503


@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response


if __name__ == '__main__':
    # Run the app
    port = int(os.environ.get('PORT', 8099))
    app.run(host='0.0.0.0', port=port, debug=False)
