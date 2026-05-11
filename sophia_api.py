"""
sophia_api.py -- Flask API for SophiaCore Attestation Inspector.
RIP-306 implementation for Rustchain bounty #2261.

Endpoints:
  POST /sophia/inspect          -- submit fingerprint for inspection
  GET  /sophia/status/<miner_id> -- latest verdict + history
  GET  /sophia/history          -- paginated inspection history
  GET  /sophia/dashboard        -- admin spot-check queue
  GET  /sophia/explorer/<miner_id> -- explorer-friendly verdict with emoji
"""

from flask import Flask, request, jsonify

from sophia_core import SophiaCoreInspector, VERDICTS
from sophia_db import (
    get_connection, init_db, get_latest_inspection,
    get_inspection_history, get_dashboard_stats, get_miner_history,
    get_pending_reviews, DB_PATH
)

app = Flask(__name__)
inspector = SophiaCoreInspector()


def positive_int_query_arg(name, default, max_value=None):
    raw_value = request.args.get(name)
    if raw_value is None:
        return default, None

    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return None, f"{name} must be an integer"

    if value < 1:
        return None, f"{name} must be positive"

    if max_value is not None:
        value = min(value, max_value)

    return value, None


@app.before_request
def _ensure_db():
    """Lazily init DB on first request."""
    if not hasattr(app, "_db_initialized"):
        init_db()
        app._db_initialized = True


@app.route("/sophia/inspect", methods=["POST"])
def inspect_fingerprint():
    """Submit a hardware fingerprint for Sophia inspection."""
    data = request.get_json(force=True)

    miner_id = data.get("miner_id")
    fingerprint = data.get("fingerprint")

    if not miner_id:
        return jsonify({"error": "miner_id is required"}), 400
    if not fingerprint or not isinstance(fingerprint, dict):
        return jsonify({"error": "fingerprint bundle (dict) is required"}), 400

    result = inspector.inspect(miner_id, fingerprint)
    return jsonify(result), 200


@app.route("/sophia/status/<miner_id>", methods=["GET"])
def miner_status(miner_id):
    """Get the latest inspection result + history for a miner."""
    conn = get_connection()
    try:
        latest = get_latest_inspection(conn, miner_id)
        history = get_miner_history(conn, miner_id, limit=10)
    finally:
        conn.close()

    if not latest:
        return jsonify({"error": "No inspections found", "miner_id": miner_id}), 404

    latest["emoji"] = VERDICTS.get(latest["verdict"], "?")
    return jsonify({"latest": latest, "history": history}), 200


@app.route("/sophia/history", methods=["GET"])
def inspection_history():
    """Get paginated inspection history."""
    page, error = positive_int_query_arg("page", 1)
    if error:
        return jsonify({"error": error}), 400

    per_page, error = positive_int_query_arg("per_page", 25, max_value=100)
    if error:
        return jsonify({"error": error}), 400

    conn = get_connection()
    try:
        result = get_inspection_history(conn, page=page, per_page=per_page)
    finally:
        conn.close()

    return jsonify(result), 200


@app.route("/sophia/dashboard", methods=["GET"])
def dashboard():
    """Admin dashboard: aggregate stats + spot-check queue (CAUTIOUS/SUSPICIOUS)."""
    conn = get_connection()
    try:
        stats = get_dashboard_stats(conn)
        queue = get_pending_reviews(conn, limit=50)
    finally:
        conn.close()

    stats["spot_check_queue"] = queue
    return jsonify(stats), 200


@app.route("/sophia/explorer/<miner_id>", methods=["GET"])
def explorer_verdict(miner_id):
    """Emoji verdict for block explorer integration."""
    conn = get_connection()
    try:
        row = get_latest_inspection(conn, miner_id)
    finally:
        conn.close()

    if not row:
        return jsonify({
            "miner_id": miner_id,
            "emoji": "\u2753",
            "verdict": "UNKNOWN",
            "message": "No inspection on record",
        }), 200

    emoji = VERDICTS.get(row["verdict"], "\u2753")
    return jsonify({
        "miner_id": miner_id,
        "emoji": emoji,
        "verdict": row["verdict"],
        "confidence": row["confidence"],
        "inspected_at": row["inspected_at"],
    }), 200


def create_app(db_path=None):
    """Factory for testing -- allows custom DB path."""
    if db_path:
        app.config["SOPHIA_DB_PATH"] = db_path
        inspector.db_path = db_path
        init_db(db_path)
    return app


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=7306, debug=False)
