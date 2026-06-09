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
            'error': str(e)
        }), 503

# Register Hall of Rust and Agent Economy routes
try:
    sys.path.insert(0, os.path.dirname(__file__))
    from explorer.hall_of_rust import register_hall_endpoints
    db_path = os.environ.get('RUSTCHAIN_DB', '/root/rustchain/rustchain_v2.db')
    register_hall_endpoints(app, db_path)
    print("[HALL] Hall of Rust endpoints registered")
except Exception as e:
    print(f"[HALL] Failed to register Hall of Rust endpoints: {e}")

try:
    from rip302_agent_economy import register_agent_economy
    register_agent_economy(app, db_path)
    print("[AGENT] Agent Economy endpoints registered")
except Exception as e:
    print(f"[AGENT] Failed to register Agent Economy endpoints: {e}")

# Add /anchors route
@app.route('/anchors')
def anchors():
    from flask import jsonify
    import sqlite3
    try:
        db = os.environ.get('RUSTCHAIN_DB', '/root/rustchain/rustchain_v2.db')
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT height, anchor_tx_id, ergo_block_height, timestamp, status
            FROM ergo_anchors ORDER BY height DESC LIMIT 50
        """)
        rows = c.fetchall()
        conn.close()
        anchors_list = [dict(r) for r in rows]
        return jsonify({"ok": True, "anchors": anchors_list, "total": len(anchors_list)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "anchors": []}), 200

if __name__ == '__main__':
    # Run the app
    port = int(os.environ.get('PORT', 8099))
    app.run(host='0.0.0.0', port=port, debug=False)
