#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Author: @createkr (RayBot AI)
# BCOS-Tier: L1
import hashlib
import hmac
import os
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
    REQUIRE_HTTPS = os.getenv("RC_SYNC_REQUIRE_HTTPS", "1").lower() not in ("0", "false", "no")

    SYNC_SIGNATURE_SECRET = os.getenv("RC_SYNC_SHARED_SECRET", admin_key)
    SIGNATURE_MAX_SKEW_SEC = 300
    NONCE_TTL_SEC = 600
    MAX_NONCES_TRACKED = 10000
    seen_nonces = {}  # nonce -> first_seen_ts

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

    def _cleanup_nonces(now: float):
        stale = [n for n, ts in seen_nonces.items() if (now - ts) > NONCE_TTL_SEC]
        for n in stale:
            seen_nonces.pop(n, None)

        if len(seen_nonces) > MAX_NONCES_TRACKED:
            oldest = sorted(seen_nonces.items(), key=lambda kv: kv[1])
            drop_n = len(seen_nonces) - MAX_NONCES_TRACKED
            for n, _ in oldest[:drop_n]:
                seen_nonces.pop(n, None)

    def _verify_sync_signature(peer_id: str, now: float):
        if not SYNC_SIGNATURE_SECRET:
            return False, "Signature secret not configured"

        ts_raw = request.headers.get("X-Sync-Timestamp")
        nonce = request.headers.get("X-Sync-Nonce")
        signature = request.headers.get("X-Sync-Signature")

        if not ts_raw or not nonce or not signature:
            return False, "Missing sync signature headers"

        try:
            ts_int = int(ts_raw)
        except (TypeError, ValueError):
            return False, "Invalid timestamp"

        if abs(now - ts_int) > SIGNATURE_MAX_SKEW_SEC:
            return False, "Timestamp skew too large"

        if nonce in seen_nonces:
            return False, "Replay detected"

        body = request.get_data(cache=True) or b""
        body_hash = hashlib.sha256(body).hexdigest()
        signing_payload = f"{peer_id}\n{ts_int}\n{nonce}\n{body_hash}".encode("utf-8")
        expected = hmac.new(
            SYNC_SIGNATURE_SECRET.encode("utf-8"),
            signing_payload,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(signature, expected):
            return False, "Invalid signature"

        seen_nonces[nonce] = now
        return True, None


    def _is_https_request() -> bool:
        if request.is_secure:
            return True
        proto = (request.headers.get("X-Forwarded-Proto") or "").lower().strip()
        if proto == "https":
            return True
        host = (request.host or "").split(":")[0]
        if host in ("127.0.0.1", "localhost"):
            return True
        return False

    def require_https(f):
        from functools import wraps

        @wraps(f)
        def decorated(*args, **kwargs):
            if REQUIRE_HTTPS and not _is_https_request():
                return jsonify({"error": "HTTPS required"}), 403
            return f(*args, **kwargs)

        return decorated

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
    @app.route("/sync/status", methods=["GET"])
    @require_https
    @require_admin
    def sync_status():
        """Returns the current Merkle root and table hashes."""
        now = time.time()
        _cleanup_peer_history(now)
        _cleanup_nonces(now)
        status = sync_manager.get_sync_status()
        status["peer_sync_history"] = last_sync_times
        return jsonify(status)

    @app.route("/api/sync/pull", methods=["GET"])
    @app.route("/sync/pull", methods=["GET"])
    @require_https
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
    @app.route("/sync/push", methods=["POST"])
    @require_https
    @require_admin
    def sync_push():
        """Receives data from a peer and applies it locally."""
        peer_id = request.headers.get("X-Peer-ID", "unknown")

        now = time.time()
        _cleanup_peer_history(now)
        _cleanup_nonces(now)

        ok, err = _verify_sync_signature(peer_id, now)
        if not ok:
            return jsonify({"error": err}), 401

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
            if not sync_manager.apply_sync_payload(table, rows, peer_id=peer_id):
                success = False

        if success:
            last_sync_times[peer_id] = now
            return jsonify({"ok": True, "merkle_root": sync_manager.get_merkle_root()})

        return jsonify({"error": "Partial or total sync failure"}), 500

    print("[Sync] Endpoints registered successfully")
