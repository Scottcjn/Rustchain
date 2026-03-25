#!/usr/bin/env python3
"""
RustChain Block Explorer Routes
Serves the real-time WebSocket block explorer at /explorer
"""
import os
from flask import Blueprint, send_from_directory, jsonify, request

explorer_bp = Blueprint('explorer', __name__)

# Path to the site/explorer directory (relative to node/ dir → ../../site/explorer)
NODE_DIR = os.path.dirname(os.path.abspath(__file__))
SITE_EXPLORER_DIR = os.path.normpath(os.path.join(NODE_DIR, '..', 'site', 'explorer'))


@explorer_bp.route('/explorer')
def explorer_index():
    """Serve the main explorer page."""
    return send_from_directory(SITE_EXPLORER_DIR, 'index.html')


@explorer_bp.route('/explorer/<path:filename>')
def explorer_static(filename):
    """Serve static assets for the explorer (JS, CSS, images)."""
    return send_from_directory(SITE_EXPLORER_DIR, filename)


@explorer_bp.route('/api/explorer/status')
def explorer_status():
    """Return the explorer WebSocket endpoint info."""
    # Determine WS URL based on request
    scheme = 'wss' if request.is_secure else 'ws'
    host = request.host.split(':')[0]
    ws_port = os.environ.get('EXPLORER_WS_PORT', '5001')
    ws_url = os.environ.get('EXPLORER_WS_URL', f'{scheme}://{host}:{ws_port}')

    return jsonify({
        'status': 'ok',
        'explorer_version': '1.0.0',
        'ws_endpoint': f'{ws_url}/ws/feed',
        'events': [
            'new_block - emitted when a new slot/block is detected',
            'attestation - emitted when a miner submits an attestation',
            'epoch_settlement - emitted when epoch advances',
        ],
        'site_explorer_dir': SITE_EXPLORER_DIR,
    })


def register_explorer_routes(app):
    """Register the explorer blueprint with the Flask app."""
    app.register_blueprint(explorer_bp)
    print("[EXPLORER] Block explorer routes registered at /explorer")
    print(f"[EXPLORER] Serving static files from: {SITE_EXPLORER_DIR}")
