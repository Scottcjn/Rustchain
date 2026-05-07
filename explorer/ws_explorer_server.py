# SPDX-License-Identifier: MIT
"""
RustChain Block Explorer — WebSocket Real-Time Feed
Bounty #2295: 75 RTC

Adds real-time WebSocket updates to the existing block explorer.
New blocks and attestations stream live without page refresh.
"""

import os
import json
import time
import threading
from datetime import datetime

import requests
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit

# ── Configuration ─────────────────────────────────────────────────
API_BASE = os.environ.get("RUSTCHAIN_API_BASE", "https://rustchain.org").rstrip("/")
API_TIMEOUT = float(os.environ.get("API_TIMEOUT", "8"))
POLL_INTERVAL = float(os.environ.get("WS_POLL_INTERVAL", "10"))
PORT = int(os.environ.get("WS_EXPLORER_PORT", "8060"))

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
if not app.config["SECRET_KEY"]:
    import secrets
    app.config["SECRET_KEY"] = secrets.token_hex(32)
    import warnings
    warnings.warn(
        "SECRET_KEY not set. Using random key — sessions will NOT persist across restarts. "
        "Set the SECRET_KEY environment variable before deployment.",
        UserWarning
    )
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ── State ─────────────────────────────────────────────────────────
state = {
    "last_epoch": None,
    "last_miner_count": None,
    "last_block_hash": None,
    "connected_clients": 0,
    "total_updates": 0,
    "started_at": datetime.utcnow().isoformat() + "Z",
}


def fetch_api(path):
    """Fetch data from RustChain API."""
    try:
        _cert = os.path.expanduser("~/.rustchain/node_cert.pem")
        _verify = _cert if os.path.exists(_cert) else True
        resp = requests.get(f"{API_BASE}{path}", timeout=API_TIMEOUT, verify=_verify)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


def poll_and_broadcast():
    """Poll RustChain API and broadcast changes via WebSocket."""
    while True:
        try:
            # Fetch current data
            epoch_data = fetch_api("/epoch")
            miners_data = fetch_api("/api/miners")
            health_data = fetch_api("/health")

            updates = {}

            if epoch_data:
                current_epoch = epoch_data.get("epoch", epoch_data.get("current_epoch"))
                if current_epoch and current_epoch != state["last_epoch"]:
                    state["last_epoch"] = current_epoch
                    updates["epoch"] = epoch_data

                # Check for new block/settlement
                block_hash = epoch_data.get("last_block_hash", epoch_data.get("hash"))
                if block_hash and block_hash != state["last_block_hash"]:
                    state["last_block_hash"] = block_hash
                    updates["new_block"] = {
                        "hash": block_hash,
                        "epoch": current_epoch,
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                    }

            if miners_data:
                miners = miners_data.get("miners", [])
                miner_count = len(miners) if isinstance(miners, list) else miners_data.get("count", 0)
                if miner_count != state["last_miner_count"]:
                    state["last_miner_count"] = miner_count
                    updates["miners"] = {
                        "count": miner_count,
                        "miners": miners[:20] if isinstance(miners, list) else [],
                    }

                # Attestation feed — send latest attestations
                attestations = []
                if isinstance(miners, list):
                    for m in miners:
                        if "last_seen" in m or "last_attestation" in m:
                            attestations.append({
                                "miner_id": m.get("miner_id", m.get("id", "unknown")),
                                "hardware": m.get("hardware", m.get("architecture", "unknown")),
                                "multiplier": m.get("multiplier", 1.0),
                                "last_seen": m.get("last_seen", 0),
                            })
                if attestations:
                    updates["attestations"] = attestations

            if health_data:
                updates["health"] = health_data

            # Broadcast if there are updates
            if updates:
                updates["server_time"] = datetime.utcnow().isoformat() + "Z"
                state["total_updates"] += 1
                socketio.emit("explorer_update", updates, namespace="/")

        except Exception as e:
            socketio.emit("explorer_error", {"error": str(e)[:200]}, namespace="/")

        time.sleep(POLL_INTERVAL)


# ── WebSocket Events ──────────────────────────────────────────────

@socketio.on("connect")
def handle_connect():
    state["connected_clients"] += 1
    # Send current state to newly connected client
    emit("welcome", {
        "message": "Connected to RustChain Explorer WebSocket",
        "connected_clients": state["connected_clients"],
        "server_uptime": state["started_at"],
    })


@socketio.on("disconnect")
def handle_disconnect():
    state["connected_clients"] = max(0, state["connected_clients"] - 1)


@socketio.on("request_snapshot")
def handle_snapshot():
    """Client requests full current state."""
    epoch_data = fetch_api("/epoch")
    miners_data = fetch_api("/api/miners")
    health_data = fetch_api("/health")
    emit("snapshot", {
        "epoch": epoch_data,
        "miners": miners_data,
        "health": health_data,
        "server_time": datetime.utcnow().isoformat() + "Z",
    })


# ── HTTP Routes ───────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("ws_explorer.html")


@app.route("/api/ws-status")
def ws_status():
    return jsonify({
        "connected_clients": state["connected_clients"],
        "total_updates": state["total_updates"],
        "last_epoch": state["last_epoch"],
        "started_at": state["started_at"],
    })


# ── Start ─────────────────────────────────────────────────────────

# Background poller thread
poller = threading.Thread(target=poll_and_broadcast, daemon=True)
poller.start()

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=PORT, debug=False)
