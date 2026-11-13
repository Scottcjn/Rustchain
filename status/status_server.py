# SPDX-License-Identifier: MIT
"""
RustChain Multi-Node Health Dashboard — Live Status Page
Bounty #2300: 50 RTC

Monitors all 4 RustChain attestation nodes in real-time.
Polls every 60 seconds, tracks 24h uptime history, logs incidents.
"""

import json
import ssl
import sys
import time
import threading
import os
from datetime import datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from flask import Flask, render_template, jsonify, Response

# Shared body-validating node probe (issue #17180): liveness is never decided
# from the HTTP status code alone — a 200 with an HTML/non-node body is an
# "impostor", not "up".
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
from monitoring.node_probe import probe_health, UP, UNREACHABLE  # noqa: E402

app = Flask(__name__, template_folder="templates", static_folder="static")

# ── Node Configuration ────────────────────────────────────────────
NODES = [
    {"id": "node-1", "name": "Node 1", "endpoint": "https://50.28.86.131/health",
     "location": "LiquidWeb US", "lat": 42.96, "lon": -85.67},
    {"id": "node-2", "name": "Node 2", "endpoint": "https://50.28.86.153/health",
     "location": "LiquidWeb US", "lat": 42.96, "lon": -85.67},
    {"id": "node-3", "name": "Node 3", "endpoint": "http://76.8.228.245:8099/health",
     "location": "Ryan's Proxmox", "lat": 37.77, "lon": -122.42},
    {"id": "node-4", "name": "Node 4", "endpoint": "http://38.76.217.189:8099/health",
     "location": "Hong Kong", "lat": 22.32, "lon": 114.17},
]

POLL_INTERVAL = 60  # seconds
DATA_DIR = Path(os.environ.get("STATUS_DATA_DIR", "/tmp/rustchain-status"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── In-memory state ───────────────────────────────────────────────
node_status = {}       # current status per node
history = {}           # 24h history per node (list of checks)
incidents = []         # incident log


def load_state():
    """Load persisted state from disk."""
    global node_status, history, incidents
    state_file = DATA_DIR / "state.json"
    if state_file.exists():
        try:
            data = json.loads(state_file.read_text())
            node_status = data.get("node_status", {})
            history = data.get("history", {})
            incidents = data.get("incidents", [])
        except (json.JSONDecodeError, KeyError):
            pass


def save_state():
    """Persist state to disk."""
    state_file = DATA_DIR / "state.json"
    state_file.write_text(json.dumps({
        "node_status": node_status,
        "history": history,
        "incidents": incidents,
    }, default=str, indent=2))


def _node_ssl_context():
    """Pinned node cert if present, otherwise default verification."""
    cert = os.path.expanduser("~/.rustchain/node_cert.pem")
    if os.path.exists(cert):
        return ssl.create_default_context(cafile=cert)
    return None  # probe_health then uses the default verifying context


def check_node(node):
    """Poll a single node and return status dict.

    "up" comes from the shared probe's validated state, never from the HTTP
    status code alone: a 200 answered by an HTML page (SPA, parking page,
    captive portal) comes back as state="impostor" with up=False.
    """
    start = time.time()
    endpoint = node["endpoint"]
    try:
        result = probe_health(endpoint, timeout=10, ssl_context=_node_ssl_context())
    except Exception as e:
        elapsed_ms = round((time.time() - start) * 1000)
        return {
            "up": False,
            "state": UNREACHABLE,
            "error": str(e)[:200],
            "response_ms": elapsed_ms,
            "checked_at": datetime.utcnow().isoformat() + "Z",
        }
    data = result.data or {}
    elapsed_ms = (result.response_ms if result.response_ms is not None
                  else (time.time() - start) * 1000)
    out = {
        "up": result.state == UP,
        "state": result.state,  # up | down | impostor | degraded | unreachable
        "status_code": result.status_code,
        "response_ms": round(elapsed_ms),
        "version": result.version or data.get("version", "unknown"),
        "uptime": data.get("uptime_s", data.get("uptime", data.get("uptime_seconds", 0))),
        "active_miners": data.get("active_miners", data.get("miners", 0)),
        "current_epoch": data.get("epoch", data.get("current_epoch", 0)),
        "checked_at": datetime.utcnow().isoformat() + "Z",
    }
    if result.state != UP:
        out["error"] = result.detail or result.state
    return out


def poll_all():
    """Poll all nodes, update state, log incidents."""
    for node in NODES:
        nid = node["id"]
        result = check_node(node)
        prev = node_status.get(nid, {})
        was_up = prev.get("up", True)
        now_up = result["up"]

        # Incident detection
        state = result.get("state", "up" if now_up else "down")
        if was_up and not now_up:
            incidents.insert(0, {
                "node": node["name"],
                "event": "impostor" if state == "impostor" else "down",
                "time": result["checked_at"],
                "detail": result.get("error", f"state={state} HTTP {result.get('status_code', '?')}"),
            })
        elif not was_up and now_up:
            incidents.insert(0, {
                "node": node["name"],
                "event": "recovered",
                "time": result["checked_at"],
            })

        # Update current status
        node_status[nid] = {**result, **{k: node[k] for k in ("name", "location", "lat", "lon")}}

        # Append to history (keep 24h = 1440 entries at 60s interval)
        if nid not in history:
            history[nid] = []
        history[nid].append({
            "t": result["checked_at"],
            "up": result["up"],
            "state": state,
            "ms": result.get("response_ms", 0),
        })
        # Trim to 24h
        cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat() + "Z"
        history[nid] = [h for h in history[nid] if h["t"] >= cutoff]

    # Trim incidents to last 100
    if len(incidents) > 100:
        incidents[:] = incidents[:100]

    save_state()


def poller_loop():
    """Background thread that polls nodes every POLL_INTERVAL seconds."""
    while True:
        try:
            poll_all()
        except Exception as e:
            print(f"Poller error: {e}")
        time.sleep(POLL_INTERVAL)


def xml_text(value):
    """Escape dynamic text before embedding it in RSS XML text nodes."""
    return xml_escape(str(value), {'"': "&quot;", "'": "&apos;"})


# ── Routes ────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("status.html")


@app.route("/api/status")
def api_status():
    """Current status of all nodes."""
    nodes = list(node_status.values())
    if all(n.get("up") for n in nodes):
        overall = "operational"
    elif any(n.get("state") == "impostor" for n in nodes):
        overall = "impostor"
    else:
        overall = "degraded"
    return jsonify({
        "nodes": nodes,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "overall": overall,
        "nodes_up": sum(1 for n in nodes if n.get("up")),
        "nodes_impostor": sum(1 for n in nodes if n.get("state") == "impostor"),
    })


@app.route("/api/history/<node_id>")
def api_history(node_id):
    """24h history for a specific node."""
    return jsonify(history.get(node_id, []))


@app.route("/api/incidents")
def api_incidents():
    """Recent incidents."""
    return jsonify(incidents[:50])


@app.route("/api/uptime")
def api_uptime():
    """24h uptime percentage per node."""
    result = {}
    for node in NODES:
        nid = node["id"]
        checks = history.get(nid, [])
        if not checks:
            result[nid] = {"name": node["name"], "uptime_pct": 0, "total_checks": 0}
            continue
        up_count = sum(1 for c in checks if c["up"])
        result[nid] = {
            "name": node["name"],
            "uptime_pct": round(up_count / len(checks) * 100, 2),
            "total_checks": len(checks),
            "avg_response_ms": round(
                sum(c["ms"] for c in checks if c["up"]) / max(up_count, 1)
            ),
        }
    return jsonify(result)


@app.route("/feed.xml")
def rss_feed():
    """RSS/Atom feed for incidents (Bonus)."""
    items = []
    for inc in incidents[:20]:
        items.append(f"""    <item>
      <title>{xml_text(inc['node'])} — {xml_text(inc['event'])}</title>
      <description>{xml_text(inc.get('detail', inc['event']))}</description>
      <pubDate>{xml_text(inc['time'])}</pubDate>
    </item>""")
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>RustChain Node Status</title>
    <link>https://rustchain.org/status</link>
    <description>RustChain attestation node status feed</description>
{"".join(items)}
  </channel>
</rss>"""
    return Response(xml, mimetype="application/rss+xml")


# ── Main ──────────────────────────────────────────────────────────

load_state()
# Start background poller
poller_thread = threading.Thread(target=poller_loop, daemon=True)
poller_thread.start()
# Do an immediate poll
poll_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)
