#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Author: @createkr (RayBot AI)
# BCOS-Tier: L1
import time
from flask import request, jsonify
from node.rustchain_sync import RustChainSyncManager

def register_sync_endpoints(app, db_path, admin_key):
    """Registers sync-related endpoints to the Flask app."""
    
    sync_manager = RustChainSyncManager(db_path, admin_key)
    last_sync_times = {} # peer_id -> timestamp

    def require_admin(f):
        from functools import wraps
        @wraps(f)
        def decorated(*args, **kwargs):
            key = request.headers.get("X-Admin-Key")
            if not key or key != admin_key:
                return jsonify({"error": "Unauthorized"}), 401
            return f(*args, **kwargs)
        return decorated

    @app.route("/api/sync/status", methods=["GET"])
    @require_admin
    def sync_status():
        """Returns the current Merkle root and table hashes."""
        status = sync_manager.get_sync_status()
        status["peer_sync_history"] = last_sync_times
        return jsonify(status)

    @app.route("/api/sync/pull", methods=["GET"])
    @require_admin
    def sync_pull():
        """Returns data for all synced tables."""
        payload = {}
        for table in sync_manager.SYNC_TABLES:
            payload[table] = sync_manager.get_table_data(table)
        return jsonify(payload)

    @app.route("/api/sync/push", methods=["POST"])
    @require_admin
    def sync_push():
        """Receives data from a peer and applies it locally."""
        peer_id = request.headers.get("X-Peer-ID", "unknown")
        
        # Rate limiting: Max 1 sync per minute per peer
        now = time.time()
        if peer_id in last_sync_times:
            if now - last_sync_times[peer_id] < 60:
                return jsonify({"error": "Rate limit exceeded"}), 429
        
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Invalid payload"}), 400
            
        success = True
        for table, rows in data.items():
            if not sync_manager.apply_sync_payload(table, rows):
                success = False
                
        if success:
            last_sync_times[peer_id] = now
            return jsonify({"ok": True, "merkle_root": sync_manager.get_merkle_root()})
        else:
            return jsonify({"error": "Partial or total sync failure"}), 500

    print("[Sync] Endpoints registered successfully")
