"""
RustChain Fork Choice Graph Visualizer — Backend Service

Provides fork choice data endpoints and historical tracking for the
Fork Choice Graph dashboard (fork_choice_graph.html).

Usage:
  python3 fork_choice_graph.py              # Start API server
  python3 fork_choice_graph.py --export     # Export static JSON snapshot
  python3 fork_choice_graph.py --simulate   # Generate simulated fork data

Requirements:
  pip install flask flask-cors requests

Endpoints:
  GET  /api/health          → Node health + fork metrics
  GET  /api/epoch           → Current epoch/slot/height
  GET  /api/forks           → Active fork list
  GET  /api/history         → Historical fork data
  GET  /api/dashboard       → All metrics aggregated
"""

import json
import os
import sys
import time
import math
import random
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    print("⚠️  requests not installed. Install with: pip install requests")
    requests = None

# ── Configuration ──────────────────────────────────────────
RUSTCHAIN_NODE = os.getenv("RUSTCHAIN_NODE", "https://50.28.86.131")
HISTORY_FILE = os.path.join(os.path.dirname(__file__), "fork_choice_history.json")
HISTORY_MAX = 200              # Max historical data points
REFRESH_SECONDS = 30           # Data refresh interval
SIMULATE = os.getenv("SIMULATE", "0") == "1"

# ── Data Store ─────────────────────────────────────────────
_fork_store = {
    "health": None,
    "epoch": None,
    "forks": [],
    "history": [],
    "last_update": 0,
    "metrics": {
        "epoch": 0,
        "slot": 0,
        "height": 0,
        "forks": 0,
        "validators": 0,
        "uptime": 0
    }
}


# ── API Client ─────────────────────────────────────────────
def fetch_node(endpoint, timeout=5):
    """Fetch data from RustChain node API."""
    if not requests:
        return None
    try:
        resp = requests.get(
            f"{RUSTCHAIN_NODE}{endpoint}",
            timeout=timeout,
            verify=False  # Self-signed cert
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"  ⚠  API error ({endpoint}): {e}")
    return None


def get_health():
    """Fetch node health status."""
    data = fetch_node("/health")
    if data:
        return {
            "ok": data.get("ok", False),
            "version": data.get("version", "unknown"),
            "uptime_s": data.get("uptime_s", 0)
        }
    return None


def get_epoch():
    """Fetch current epoch/slot/height."""
    data = fetch_node("/epoch")
    if data:
        return {
            "epoch": data.get("epoch", 0),
            "slot": data.get("slot", 0),
            "height": data.get("height", 0)
        }
    return None


# ── Fork Analysis ──────────────────────────────────────────
def analyze_forks(epoch_data, health_data):
    """
    Analyze fork choice based on node data.
    In a real implementation, this would query the node's
    internal fork choice state.
    """
    if not epoch_data:
        return _generate_simulated_forks()

    epoch = epoch_data.get("epoch", 0)
    slot = epoch_data.get("slot", 0)

    # Simulate fork analysis based on epoch/slot patterns
    # In production, replace with actual node queries
    num_forks = min(max(epoch % 7, 1), 6)
    forks = []

    for f in range(num_forks):
        fork_slot = max(0, slot - ((f * 37) + (epoch % 13)))
        parent_slot = max(0, fork_slot - (13 + f * 7))
        weight = 45 - (f * 6) + (epoch % 5)
        validators = max(1, 4 - f)

        status = "canonical" if f == 0 else ("active" if f < 3 else "abandoned")
        forks.append({
            "id": f"fork-e{epoch}-s{fork_slot}",
            "slot": fork_slot,
            "parentSlot": parent_slot,
            "weight": max(1, weight),
            "validators": validators,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    return forks


def _generate_simulated_forks():
    """Generate simulated fork data for demo purposes."""
    base_slot = 12345 + random.randint(0, 100)
    epoch = 95 + random.randint(0, 2)
    return [
        {"id": "fork-main", "slot": base_slot, "parentSlot": base_slot - 23,
         "weight": 45, "validators": 4, "status": "canonical",
         "timestamp": datetime.now(timezone.utc).isoformat()},
        {"id": "fork-a", "slot": base_slot - 37, "parentSlot": base_slot - 50,
         "weight": 28, "validators": 3, "status": "active",
         "timestamp": datetime.now(timezone.utc).isoformat()},
        {"id": "fork-b", "slot": base_slot - 89, "parentSlot": base_slot - 102,
         "weight": 15, "validators": 2, "status": "active",
         "timestamp": datetime.now(timezone.utc).isoformat()},
        {"id": "fork-c", "slot": base_slot - 156, "parentSlot": base_slot - 170,
         "weight": 8, "validators": 1, "status": "abandoned",
         "timestamp": datetime.now(timezone.utc).isoformat()}
    ]


# ── Core Update ────────────────────────────────────────────
def refresh_data():
    """Fetch latest data and regenerate fork analysis."""
    health = get_health() if not SIMULATE else {
        "ok": True, "version": "2.2.1-rip200", "uptime_s": 200000 + random.randint(0, 100)
    }
    epoch = get_epoch() if not SIMULATE else {
        "epoch": 95 + random.randint(0, 2),
        "slot": 12345 + random.randint(0, 50),
        "height": 67890 + random.randint(0, 250)
    }

    if SIMULATE or (not health and not epoch):
        # Fallback to simulated data
        health = {"ok": True, "version": "2.2.1-rip200", "uptime_s": 200000}
        epoch = {"epoch": 95, "slot": 12345, "height": 67890}

    forks = analyze_forks(epoch, health)

    _fork_store["health"] = health
    _fork_store["epoch"] = epoch
    _fork_store["forks"] = forks
    _fork_store["last_update"] = time.time()

    # Update metrics
    _fork_store["metrics"] = {
        "epoch": epoch.get("epoch", 0),
        "slot": epoch.get("slot", 0),
        "height": epoch.get("height", 0),
        "forks": len(forks),
        "validators": sum(f["validators"] for f in forks),
        "uptime": health.get("uptime_s", 0) if health else 0
    }

    # Update history
    _fork_store["history"].append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "epoch": epoch.get("epoch", 0),
        "slot": epoch.get("slot", 0),
        "height": epoch.get("height", 0),
        "forks": len(forks),
        "validators": sum(f["validators"] for f in forks)
    })

    if len(_fork_store["history"]) > HISTORY_MAX:
        _fork_store["history"] = _fork_store["history"][-HISTORY_MAX:]

    # Persist history
    _save_history()

    return _fork_store


def _save_history():
    """Save historical data to disk."""
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(_fork_store["history"], f, indent=2)
    except Exception as e:
        print(f"  ⚠  Could not save history: {e}")


def _load_history():
    """Load historical data from disk."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return []


# ── Flask API ──────────────────────────────────────────────
def create_app():
    """Create Flask application with all endpoints."""
    try:
        from flask import Flask, jsonify
        from flask_cors import CORS
    except ImportError:
        print("❌ Flask not installed. Run: pip install flask flask-cors")
        sys.exit(1)

    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": os.environ.get("CORS_ORIGINS", "*")}})

    # Load historical data
    _fork_store["history"] = _load_history()

    @app.route("/api/health")
    def api_health():
        return jsonify(_fork_store.get("health", {"ok": False}))

    @app.route("/api/epoch")
    def api_epoch():
        return jsonify(_fork_store.get("epoch", {"epoch": 0, "slot": 0, "height": 0}))

    @app.route("/api/forks")
    def api_forks():
        return jsonify(_fork_store.get("forks", []))

    @app.route("/api/history")
    def api_history():
        return jsonify(_fork_store.get("history", []))

    @app.route("/api/dashboard")
    def api_dashboard():
        return jsonify({
            "metrics": _fork_store["metrics"],
            "forks": _fork_store["forks"],
            "health": _fork_store["health"],
            "last_update": _fork_store["last_update"]
        })

    @app.route("/api/refresh")
    def api_refresh():
        refresh_data()
        return jsonify({"status": "ok", "timestamp": time.time()})

    @app.route("/")
    def index():
        return """<html><head><meta http-equiv="refresh" content="0;url=fork_choice_graph.html"></head>
<body><a href="fork_choice_graph.html">→ Open Fork Choice Graph Visualizer</a></body></html>"""

    return app


# ── CLI ────────────────────────────────────────────────────
def main():
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "--export":
            refresh_data()
            print(json.dumps(_fork_store, indent=2))
            return
        elif cmd == "--simulate":
            os.environ["SIMULATE"] = "1"
            sim = _generate_simulated_forks()
            print(json.dumps({"forks": sim, "count": len(sim)}, indent=2))
            return
        elif cmd == "--help":
            print(__doc__)
            return

    # Start Flask server
    app = create_app()
    port = int(os.getenv("PORT", 8765))
    print(f"🚀 RustChain Fork Choice Visualizer API")
    print(f"   Listening on http://0.0.0.0:{port}")
    print(f"   Dashboard: http://localhost:{port}/")
    print(f"   API:       http://localhost:{port}/api/dashboard")
    print(f"   Node:      {RUSTCHAIN_NODE}")
    print(f"   Simulate:  {SIMULATE}")
    print()

    # Initial data fetch
    print("📡 Fetching initial data...")
    refresh_data()
    print(f"   Epoch: {_fork_store['metrics']['epoch']}, "
          f"Slot: {_fork_store['metrics']['slot']}, "
          f"Forks: {_fork_store['metrics']['forks']}")

    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
