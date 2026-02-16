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
    last_sync_times = {}  # peer_id -> timestamp

    RATE_LIMIT_WINDOW_SEC = 60
    PEER_TTL_SEC = 3600
    MAX_PEERS_TRACKED = 2000

    def _cleanup_peer_history(now: float):
        stale = [k for k, ts in last_sync_times.items() if (now - ts) > PEER_TTL_SEC]
        for k in stale:
            last_sync_times.pop(k, None)

        if len(last_sync_times) > MAX_PEERS_TRACKED:
            # Trim oldest entries to keep bounded memory usage.
            oldest = sorted(last_sync_times.items(), key=lambda kv: kv[1])
            drop_n = len(last_sync_times) - MAX_PEERS_TRACKED
            for k, _ in oldest[:drop_n]:
                last_sync_times.pop(k, None)

    def require_admin(f):
        from functools import wraps

        @wraps(f)
        def decorated(*args, **kwargs):
            key = request.headers.get("X-Admin-Key") or request.headers.get("X-API-Key")
            if not key or key != admin_key:
                return jsonify({"error": "Unauthorized"}), 401
            return f(*args, **kwargs)

        return decorated

    @app.route("/api/sync/status", methods=["GET"])
    @require_admin
    def sync_status():
        """Returns the current Merkle root and table hashes."""
        now = time.time()
        _cleanup_peer_history(now)
        status = sync_manager.get_sync_status()
        status["peer_sync_history"] = last_sync_times
        return jsonify(status)

    @app.route("/api/sync/pull", methods=["GET"])
    @require_admin
    def sync_pull():
        """
        Returns bounded data for synced tables.

        Query params:
        - table: optional single table name; if omitted returns all synced tables
        - limit: max rows per table (default 200, max 1000)
        - offset: row offset (default 0)
        """
        table = request.args.get("table", "").strip()
        try:
            limit = int(request.args.get("limit", 200))
            offset = int(request.args.get("offset", 0))
        except ValueError:
            return jsonify({"error": "limit/offset must be integers"}), 400

        limit = max(1, min(limit, 1000))
        offset = max(0, offset)

        tables = sync_manager.SYNC_TABLES
        if table:
            if table not in tables:
                return jsonify({"error": f"invalid table: {table}"}), 400
            tables = [table]

        payload = {
            "meta": {
                "limit": limit,
                "offset": offset,
                "tables": tables,
            },
            "data": {},
        }
        for t in tables:
            payload["data"][t] = sync_manager.get_table_data(t, limit=limit, offset=offset)

        return jsonify(payload)

    @app.route("/api/sync/push", methods=["POST"])
    @require_admin
    def sync_push():
        """Receives data from a peer and applies it locally."""
        peer_id = request.headers.get("X-Peer-ID", "unknown")

        now = time.time()
        _cleanup_peer_history(now)

        # Rate limiting: Max 1 sync per minute per peer
        if peer_id in last_sync_times and (now - last_sync_times[peer_id] < RATE_LIMIT_WINDOW_SEC):
            return jsonify({"error": "Rate limit exceeded"}), 429

        data = request.get_json(silent=True)
        if not data or not isinstance(data, dict):
            return jsonify({"error": "Invalid payload"}), 400

        success = True
        for table, rows in data.items():
            if not isinstance(rows, list):
                success = False
                continue
            if not sync_manager.apply_sync_payload(table, rows):
                success = False

        if success:
            last_sync_times[peer_id] = now
            return jsonify({"ok": True, "merkle_root": sync_manager.get_merkle_root()})

        return jsonify({"error": "Partial or total sync failure"}), 500

    print("[Sync] Endpoints registered successfully")
