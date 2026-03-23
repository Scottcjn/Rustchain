"""
RustChain Multi-Node Health Dashboard
Polls 4 attestation nodes every 60 seconds.
"""

from flask import Flask, jsonify, render_template
import sqlite3
import time
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from datetime import datetime, timezone
import threading

db_lock = threading.Lock()

app = Flask(__name__)

NODES = [
    {"id": "node1", "name": "Node 1", "endpoint": "https://50.28.86.131/health", "location": "LiquidWeb US"},
    {"id": "node2", "name": "Node 2", "endpoint": "https://50.28.86.153/health", "location": "LiquidWeb US"},
    {"id": "node3", "name": "Node 3", "endpoint": "http://76.8.228.245:8099/health", "location": "Ryan's Proxmox"},
    {"id": "node4", "name": "Node 4", "endpoint": "http://38.76.217.189:8099/health", "location": "Hong Kong"},
]

DB_PATH = "/Users/achieve/.openclaw/workspace/rustchain-status-dashboard/status.db"

def get_db():
    return sqlite3.connect(DB_PATH, timeout=10)

def init_db():
    with db_lock:
        conn = get_db()
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS health_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id TEXT,
            timestamp TEXT,
            ok INTEGER,
            response_ms INTEGER,
            version TEXT,
            uptime_s INTEGER,
            db_rw INTEGER,
            backup_age_hours REAL,
            tip_age_slots INTEGER,
            error TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id TEXT,
            timestamp TEXT,
            event_type TEXT,
            description TEXT
        )""")
        conn.commit()
        conn.close()

def log_incident(node_id, event_type, description):
    with db_lock:
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO incidents (node_id, timestamp, event_type, description) VALUES (?, ?, ?, ?)",
                  (node_id, datetime.now(timezone.utc).isoformat(), event_type, description))
        conn.commit()
        conn.close()

def poll_node(node):
    start = time.time()
    try:
        r = requests.get(node["endpoint"], timeout=10, verify=False)
        elapsed_ms = int((time.time() - start) * 1000)
        data = r.json()
        return {
            "node_id": node["id"],
            "name": node["name"],
            "endpoint": node["endpoint"],
            "location": node["location"],
            "ok": data.get("ok", False),
            "response_ms": elapsed_ms,
            "version": data.get("version", "unknown"),
            "uptime_s": data.get("uptime_s", 0),
            "db_rw": data.get("db_rw", None),
            "backup_age_hours": data.get("backup_age_hours"),
            "tip_age_slots": data.get("tip_age_slots"),
            "error": None
        }
    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        return {
            "node_id": node["id"],
            "name": node["name"],
            "endpoint": node["endpoint"],
            "location": node["location"],
            "ok": False,
            "response_ms": elapsed_ms,
            "version": None,
            "uptime_s": 0,
            "db_rw": None,
            "backup_age_hours": None,
            "tip_age_slots": None,
            "error": str(e)
        }

def poll_all_nodes():
    with db_lock:
        conn = get_db()
        c = conn.cursor()
        ts = datetime.now(timezone.utc).isoformat()
        
        # Get previous state for incident detection
        c.execute("SELECT node_id, ok FROM health_log ORDER BY id DESC LIMIT 4")
        prev_states = {row[0]: row[1] for row in c.fetchall()}
        
        for node in NODES:
            result = poll_node(node)
            
            # Log to DB
            c.execute("""INSERT INTO health_log 
                (node_id, timestamp, ok, response_ms, version, uptime_s, db_rw, backup_age_hours, tip_age_slots, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (result["node_id"], ts, int(result["ok"]), result["response_ms"],
                 result["version"], result["uptime_s"], 
                 int(result["db_rw"]) if result["db_rw"] is not None else None,
                 result["backup_age_hours"], result["tip_age_slots"], result["error"]))
            
            # Detect incidents
            prev = prev_states.get(result["node_id"])
            if prev is not None:
                if prev == 1 and result["ok"] == 0:
                    conn.commit()  # commit before nested call
                    log_incident(result["node_id"], "DOWN", f"Node went down at {ts}")
                elif prev == 0 and result["ok"] == 1:
                    conn.commit()
                    log_incident(result["node_id"], "UP", f"Node came back up at {ts}")
        
        conn.commit()
        conn.close()

def background_poller():
    init_db()
    while True:
        poll_all_nodes()
        time.sleep(60)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status")
def api_status():
    with db_lock:
        conn = get_db()
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        statuses = []
        for node in NODES:
            c.execute("""SELECT * FROM health_log WHERE node_id=? ORDER BY id DESC LIMIT 1""", (node["id"],))
            row = c.fetchone()
            if row:
                statuses.append(dict(row))
            else:
                statuses.append({"node_id": node["id"], "ok": 0, "error": "No data"})
        conn.close()
    return jsonify(statuses)

@app.route("/api/history/<node_id>")
def api_history(node_id):
    with db_lock:
        conn = get_db()
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""SELECT * FROM health_log 
                      WHERE node_id=? AND timestamp > datetime('now', '-24 hours')
                      ORDER BY id ASC""", (node_id,))
        rows = [dict(row) for row in c.fetchall()]
        conn.close()
    return jsonify(rows)

@app.route("/api/incidents")
def api_incidents():
    with db_lock:
        conn = get_db()
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""SELECT * FROM incidents ORDER BY id DESC LIMIT 50""")
        rows = [dict(row) for row in c.fetchall()]
        conn.close()
    return jsonify(rows)

if __name__ == "__main__":
    init_db()
    t = threading.Thread(target=background_poller, daemon=True)
    t.start()
    poll_all_nodes()
    app.run(host="0.0.0.0", port=8090, debug=False)
