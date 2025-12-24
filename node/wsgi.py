#!/usr/bin/env python3
"""
RustChain WSGI Entry Point for Gunicorn Production Server
=========================================================

Usage:
    gunicorn -w 4 -b 0.0.0.0:8099 wsgi:app --timeout 120
"""

import os
import sys
import importlib.util

# Ensure the rustchain directory is in path
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_dir)

# Load the main module dynamically (handles dots/dashes in filename)
spec = importlib.util.spec_from_file_location(
    "rustchain_main",
    os.path.join(base_dir, "rustchain_v2_integrated_v2.2.1_rip200.py")
)
rustchain_main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rustchain_main)

# Get the Flask app
app = rustchain_main.app
init_db = rustchain_main.init_db
DB_PATH = rustchain_main.DB_PATH

# Initialize database
init_db()

# Initialize P2P if available
p2p_node = None
try:
    from rustchain_p2p_init import init_p2p
    p2p_node = init_p2p(app, DB_PATH)
    print("[WSGI] P2P initialized successfully")
except ImportError as e:
    print(f"[WSGI] P2P not available: {e}")
except Exception as e:
    print(f"[WSGI] P2P init failed: {e}")

# Expose the app for gunicorn
application = app

if __name__ == "__main__":
    # For direct execution (development)
    app.run(host='0.0.0.0', port=8099, debug=False)
