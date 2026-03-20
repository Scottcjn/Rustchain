"""
Flask Blueprint: BoTTube RTC Bridge API
======================================
Integrates the bridge's tip handling into a Flask app.

Usage in app.py:
    from bottube_rtc_bridge import bridge_bp
    app.register_blueprint(bridge_bp, url_prefix='/api/bridge')

Endpoints:
  POST /api/bridge/tip          — Tip another user
  GET  /api/bridge/balance       — Bridge wallet balance
  GET  /api/bridge/rewards      — Reward history
  GET  /api/bridge/stats         — Bridge statistics
"""

import os
from flask import Blueprint, g, jsonify, request

try:
    from bottube_rtc_bridge import BoTTubeRTCBridge, handle_tip
    BRIDGE_AVAILABLE = True
except ImportError:
    BRIDGE_AVAILABLE = False

bridge_bp = Blueprint("bottube_rtc_bridge", __name__)

BOTTUBE_ADMIN_KEY = os.environ.get("BOTTUBE_ADMIN_KEY", "bottube_admin_key_2026")


def require_admin(f):
    """Decorator: require admin key header."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get("X-Admin-Key", "")
        if key != BOTTUBE_ADMIN_KEY:
            return jsonify({"error": "Unauthorized"}), 403
        return f(*args, **kwargs)
    return decorated


@bridge_bp.route("/tip", methods=["POST"])
def tip_user():
    """
    Tip another BoTTube user in RTC.

    Body: { "to_agent": "...", "amount": 1.0 }
    Requires: X-API-Key header (standard BoTTube auth)
    """
    if not BRIDGE_AVAILABLE:
        return jsonify({"error": "Bridge not available"}), 503

    if not hasattr(g, "agent") or not g.agent:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json(silent=True) or {}
    to_agent = str(data.get("to_agent", "")).strip()
    try:
        amount = float(data.get("amount", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid amount"}), 400

    if not to_agent:
        return jsonify({"error": "to_agent required"}), 400
    if to_agent == g.agent["agent_name"]:
        return jsonify({"error": "Cannot tip yourself"}), 400

    ok, msg = handle_tip(g.agent["agent_name"], to_agent, amount)
    if ok:
        return jsonify({"ok": True, "message": msg})
    else:
        return jsonify({"ok": False, "error": msg}), 400


@bridge_bp.route("/balance", methods=["GET"])
@require_admin
def bridge_balance():
    """Get bridge wallet balance. Admin only."""
    if not BRIDGE_AVAILABLE:
        return jsonify({"error": "Bridge not available"}), 503

    from bottube_rtc_bridge import RustChainTransfer
    wallet = os.environ.get("BRIDGE_WALLET", "")
    if not wallet:
        return jsonify({"error": "BRIDGE_WALLET not configured"}), 500

    rc = RustChainTransfer()
    balance = rc.get_balance(wallet)
    return jsonify({"ok": True, "wallet": wallet, "balance": balance})


@bridge_bp.route("/rewards", methods=["GET"])
@require_admin
def reward_history():
    """Get recent reward history. Admin only."""
    if not BRIDGE_AVAILABLE:
        return jsonify({"error": "Bridge not available"}), 503

    from bottube_rtc_bridge import get_db
    limit = min(int(request.args.get("limit", 50)), 200)

    db = get_db()
    rows = db.execute("""
        SELECT agent_id, video_id, event_type, amount_rtc, tx_hash,
               status, created_at, paid_at
        FROM video_rewards
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    db.close()

    return jsonify({
        "ok": True,
        "rewards": [dict(r) for r in rows]
    })


@bridge_bp.route("/stats", methods=["GET"])
def bridge_stats():
    """
    Public bridge statistics (no auth required).
    Returns total rewards paid, total RTC, blocked count.
    """
    if not BRIDGE_AVAILABLE:
        return jsonify({"error": "Bridge not available"}), 503

    from bottube_rtc_bridge import get_db
    db = get_db()

    total = db.execute(
        "SELECT COUNT(*), COALESCE(SUM(amount_rtc),0) FROM video_rewards WHERE status='paid'"
    ).fetchone()
    blocked = db.execute(
        "SELECT COUNT(*) FROM video_rewards WHERE status='hold'"
    ).fetchone()
    pending = db.execute(
        "SELECT COUNT(*) FROM video_rewards WHERE status='pending'"
    ).fetchone()
    db.close()

    return jsonify({
        "ok": True,
        "stats": {
            "total_rewards_paid": total[0],
            "total_rtc_paid": round(total[1], 4),
            "rewards_pending": pending[0],
            "rewards_blocked": blocked[0],
        }
    })
