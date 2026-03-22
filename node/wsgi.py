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

# RIP-306: SophiaCore Attestation Inspector
try:
    from sophia_attestation_inspector import register_sophia_endpoints, ensure_schema as sophia_schema
    sophia_schema(DB_PATH)
    register_sophia_endpoints(app, DB_PATH)
    print("[RIP-306] SophiaCore Attestation Inspector registered")
    print("[RIP-306]   Endpoints: /sophia/status, /sophia/inspect, /sophia/batch")
except ImportError as e:
    print(f"[RIP-306] SophiaCore not available: {e}")
except Exception as e:
    print(f"[RIP-306] SophiaCore init failed: {e}")

# RustChain Block Explorer Routes
try:
    from explorer_routes import register_explorer_routes
    register_explorer_routes(app)
    print("[EXPLORER] Block explorer available at /explorer")
except ImportError as e:
    print(f"[EXPLORER] explorer_routes not available: {e}")
except Exception as e:
    print(f"[EXPLORER] Explorer routes failed: {e}")

# WebSocket Feed (Socket.IO real-time events)
# Can run standalone or integrated. If running standalone on port 5001,
# the explorer connects directly. If integrated, we try to init here.
_websocket_integrated = False
try:
    # Try to import websocket_feed and integrate it
    sys.path.insert(0, os.path.join(base_dir, '..'))
    from websocket_feed import ws_bp, socketio, start_event_poller, HAVE_SOCKETIO
    if HAVE_SOCKETIO:
        socketio.init_app(app, cors_allowed_origins="*", async_mode="threading")
        app.register_blueprint(ws_bp)
        start_event_poller()
        _websocket_integrated = True
        print("[WS-FEED] Socket.IO WebSocket feed integrated at /ws/feed")
except ImportError as e:
    print(f"[WS-FEED] websocket_feed not available: {e}")
except Exception as e:
    print(f"[WS-FEED] WebSocket feed integration failed: {e}")

# Expose the app for gunicorn
application = app

if __name__ == "__main__":
    # For direct execution (development)
    app.run(host='0.0.0.0', port=8099, debug=False)
