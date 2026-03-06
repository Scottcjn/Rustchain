#!/usr/bin/env python3
"""
RustChain Node Health Monitor + Discord Alerts

Stdlib-only monitor script that:
- polls node /health endpoints
- polls /api/miners to track miner count and attestation freshness (best-effort)
- debounces alerts so it doesn't spam every interval while a node is down
- can write a status JSON snapshot to disk
- can optionally serve a local HTTP status endpoint

Intended for cron or systemd.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import ssl
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_NODES = [
    "https://rustchain.org",
    "https://50.28.86.153",
    "http://76.8.228.245:8099",
]


def utc_iso(ts: Optional[float] = None) -> str:
    ts = time.time() if ts is None else ts
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def _ssl_context(insecure: bool) -> Optional[ssl.SSLContext]:
    if not insecure:
        return None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def http_json_get(url: str, timeout_s: int, insecure: bool) -> Tuple[bool, Any, str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "rustchain-node-monitor/1.0"})
        with urllib.request.urlopen(req, timeout=timeout_s, context=_ssl_context(insecure)) as resp:
            body = resp.read(1024 * 1024).decode("utf-8", errors="replace")
            try:
                return True, json.loads(body), ""
            except Exception:
                return False, None, "invalid_json"
    except urllib.error.HTTPError as e:
        return False, None, f"http_{e.code}"
    except Exception as e:
        return False, None, "unreachable"


def http_post_json(url: str, payload: Dict[str, Any], timeout_s: int) -> Tuple[bool, str]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "rustchain-node-monitor/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            _ = resp.read(1024 * 1024)
            return 200 <= int(resp.status) < 300, ""
    except Exception:
        return False, "post_failed"


def ensure_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(path)) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts(
              k TEXT PRIMARY KEY,
              last_sent_ts REAL NOT NULL,
              last_state TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS samples(
              ts REAL NOT NULL,
              node TEXT NOT NULL,
              health_ok INTEGER,
              miner_count INTEGER,
              PRIMARY KEY (ts, node)
            )
            """
        )
        db.commit()


def prune_samples(db_path: Path, retention_days: int) -> None:
    if retention_days <= 0:
        return
    cutoff = time.time() - (retention_days * 86400)
    try:
        with sqlite3.connect(str(db_path)) as db:
            db.execute("DELETE FROM samples WHERE ts < ?", (cutoff,))
            db.commit()
    except Exception:
        return


def should_alert(db_path: Path, key: str, state: str, cooldown_s: int) -> bool:
    now = time.time()
    with sqlite3.connect(str(db_path)) as db:
        row = db.execute("SELECT last_sent_ts, last_state FROM alerts WHERE k=?", (key,)).fetchone()
        if row is None:
            db.execute(
                "INSERT OR REPLACE INTO alerts(k,last_sent_ts,last_state) VALUES(?,?,?)",
                (key, now, state),
            )
            db.commit()
            return True

        last_ts, last_state = float(row[0]), str(row[1])
        # Always alert on state change (up->down, down->up).
        if last_state != state:
            db.execute(
                "INSERT OR REPLACE INTO alerts(k,last_sent_ts,last_state) VALUES(?,?,?)",
                (key, now, state),
            )
            db.commit()
            return True

        # Same state: cooldown-based debounce.
        if now - last_ts >= cooldown_s:
            db.execute(
                "INSERT OR REPLACE INTO alerts(k,last_sent_ts,last_state) VALUES(?,?,?)",
                (key, now, state),
            )
            db.commit()
            return True

        return False


def parse_miner_freshness(miners_payload: Any) -> Dict[str, Any]:
    """
    Best-effort parsing of /api/miners response.
    Returns:
      {
        "miner_count": int,
        "stale_miners": [{"miner_id":..., "age_s":...}, ...] (optional)
      }
    """
    out: Dict[str, Any] = {"miner_count": 0, "stale_miners": []}

    # common formats:
    # - {"miners": [...]}  or {"miners": {"a": {...}}}
    # - [{"miner_id":..., "ts_ok":...}, ...]
    miners_obj = miners_payload
    if isinstance(miners_payload, dict) and "miners" in miners_payload:
        miners_obj = miners_payload["miners"]

    miners_list: List[Dict[str, Any]] = []
    if isinstance(miners_obj, list):
        miners_list = [m for m in miners_obj if isinstance(m, dict)]
    elif isinstance(miners_obj, dict):
        for _, v in miners_obj.items():
            if isinstance(v, dict):
                miners_list.append(v)

    out["miner_count"] = len(miners_list)

    now = time.time()
    stale: List[Dict[str, Any]] = []
    for m in miners_list:
        miner_id = m.get("miner_id") or m.get("miner") or m.get("id") or ""
        ts = m.get("ts_ok") or m.get("last_attest_ts") or m.get("last_attestation") or m.get("last_seen") or None
        try:
            if ts is None:
                continue
            ts_f = float(ts)
            age_s = now - ts_f
            stale.append({"miner_id": str(miner_id), "age_s": int(age_s)})
        except Exception:
            continue

    # keep most stale first
    stale.sort(key=lambda x: x.get("age_s", 0), reverse=True)
    out["stale_miners"] = stale
    return out


def discord_send(webhook_url: str, content: str, timeout_s: int = 10) -> Tuple[bool, str]:
    # Discord webhook expects {"content": "..."}.
    payload = {"content": content[:1900]}
    ok, err = http_post_json(webhook_url, payload, timeout_s=timeout_s)
    return ok, err


class StatusState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.snapshot: Dict[str, Any] = {"meta": {"updated_utc": utc_iso()}, "nodes": []}

    def update(self, snap: Dict[str, Any]) -> None:
        with self.lock:
            self.snapshot = snap

    def get(self) -> Dict[str, Any]:
        with self.lock:
            return dict(self.snapshot)


class StatusHandler(BaseHTTPRequestHandler):
    STATE: Optional[StatusState] = None

    def do_GET(self) -> None:  # noqa: N802
        if self.path not in ("/", "/status", "/status.json"):
            self.send_response(404)
            self.end_headers()
            return

        body = json.dumps(self.STATE.get() if self.STATE else {}, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:
        # Quiet by default (systemd/cron friendly)
        return


def run_http_server(bind: str, port: int, state: StatusState) -> ThreadingHTTPServer:
    StatusHandler.STATE = state
    srv = ThreadingHTTPServer((bind, port), StatusHandler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    return srv


def monitor_once(
    nodes: List[str],
    timeout_s: int,
    insecure_ssl: bool,
    miner_stale_s: int,
    miner_drop_threshold: int,
    state_db: Path,
    discord_webhook: Optional[str],
    alert_cooldown_s: int,
    sample_retention_days: int,
    prev_miner_counts: Dict[str, int],
) -> Dict[str, Any]:
    ensure_db(state_db)
    prune_samples(state_db, sample_retention_days)

    snap: Dict[str, Any] = {"meta": {"updated_utc": utc_iso(), "insecure_ssl": insecure_ssl}, "nodes": []}

    for base in nodes:
        base = base.rstrip("/")
        health_url = f"{base}/health"
        miners_url = f"{base}/api/miners"

        node_row: Dict[str, Any] = {"base": base, "health": {}, "miners": {}}

        ok_h, hdata, herr = http_json_get(health_url, timeout_s=timeout_s, insecure=insecure_ssl)
        node_row["health"] = {"ok": bool(ok_h), "err": herr, "data": hdata if ok_h else None}

        ok_m, mdata, merr = http_json_get(miners_url, timeout_s=timeout_s, insecure=insecure_ssl)
        miners_info = parse_miner_freshness(mdata) if ok_m else {"miner_count": 0, "stale_miners": []}
        node_row["miners"] = {
            "ok": bool(ok_m),
            "err": merr,
            "miner_count": int(miners_info.get("miner_count", 0)),
            "stale_miners": miners_info.get("stale_miners", [])[:20],
        }

        # Record sample for history (nice-to-have).
        with sqlite3.connect(str(state_db)) as db:
            db.execute(
                "INSERT OR REPLACE INTO samples(ts,node,health_ok,miner_count) VALUES(?,?,?,?)",
                (time.time(), base, 1 if ok_h else 0, int(node_row["miners"]["miner_count"])),
            )
            db.commit()

        # Alerting (debounced)
        if discord_webhook:
            # Node reachability / ok:false
            health_ok = bool(ok_h) and bool((hdata or {}).get("ok", True))
            health_state = "up" if health_ok else "down"
            if should_alert(state_db, f"health:{base}", health_state, cooldown_s=alert_cooldown_s):
                if health_state == "down":
                    msg = f"[RustChain] Node DOWN: {base} ({herr or 'ok:false'}) at {utc_iso()}"
                    discord_send(discord_webhook, msg)
                else:
                    msg = f"[RustChain] Node RECOVERED: {base} at {utc_iso()}"
                    discord_send(discord_webhook, msg)

            # Miner count drop
            cur_cnt = int(node_row["miners"]["miner_count"])
            prev_cnt = int(prev_miner_counts.get(base, cur_cnt))
            prev_miner_counts[base] = cur_cnt
            if prev_cnt - cur_cnt >= miner_drop_threshold:
                if should_alert(state_db, f"miners_drop:{base}", "drop", cooldown_s=alert_cooldown_s):
                    msg = f"[RustChain] Miner count drop on {base}: {prev_cnt} -> {cur_cnt} at {utc_iso()}"
                    discord_send(discord_webhook, msg)

            # Stale miners
            stale = [m for m in node_row["miners"]["stale_miners"] if int(m.get("age_s", 0)) >= miner_stale_s]
            if stale:
                if should_alert(state_db, f"stale_miners:{base}", "stale", cooldown_s=alert_cooldown_s):
                    top = stale[:5]
                    brief = ", ".join([f"{x.get('miner_id','?')}({int(x.get('age_s',0))//60}m)" for x in top])
                    msg = f"[RustChain] Stale miners on {base} (>{miner_stale_s//60}m): {brief} at {utc_iso()}"
                    discord_send(discord_webhook, msg)

        snap["nodes"].append(node_row)

    return snap


def load_config(path: Optional[str]) -> Dict[str, Any]:
    if not path:
        return {}
    p = Path(path).expanduser().resolve()
    return json.loads(p.read_text(encoding="utf-8"))


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="RustChain node/miner monitor + Discord alerts (stdlib-only).")
    ap.add_argument("--config", help="Path to JSON config file.")
    ap.add_argument("--once", action="store_true", help="Run one poll iteration then exit.")
    ap.add_argument("--interval-s", type=int, default=300, help="Polling interval in seconds (default: 300).")
    ap.add_argument("--timeout-s", type=int, default=10, help="HTTP timeout in seconds (default: 10).")
    ap.add_argument("--insecure-ssl", action="store_true", help="Disable TLS verification (self-signed nodes).")
    ap.add_argument("--discord-webhook", help="Discord webhook URL for alerts.")
    ap.add_argument("--state-db", default=str(Path("~/.rustchain/node_monitor.db").expanduser()), help="SQLite state DB path.")
    ap.add_argument("--status-json", help="Write last snapshot JSON to this path each interval.")
    ap.add_argument("--serve", type=int, default=0, help="Serve local status JSON on this port (0=off).")
    ap.add_argument("--bind", default="127.0.0.1", help="Bind address for --serve (default 127.0.0.1).")

    ap.add_argument("--miner-stale-s", type=int, default=2 * 3600, help="Alert if miner age exceeds this (default 2h).")
    ap.add_argument("--miner-drop", type=int, default=2, help="Alert if miner count drops by >= this (default 2).")
    ap.add_argument("--alert-cooldown-s", type=int, default=600, help="Debounce repeated alerts (default 10m).")
    ap.add_argument("--sample-retention-days", type=int, default=7, help="Keep samples for N days (default 7, 0=keep forever).")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)

    nodes = cfg.get("nodes") or DEFAULT_NODES
    nodes = [str(n) for n in nodes]

    webhook = args.discord_webhook or cfg.get("discord_webhook")
    state_db = Path(args.state_db)

    miner_stale_s = int(cfg.get("miner_stale_s", args.miner_stale_s))
    miner_drop = int(cfg.get("miner_drop_threshold", args.miner_drop))
    alert_cooldown_s = int(cfg.get("alert_cooldown_s", args.alert_cooldown_s))
    sample_retention_days = int(cfg.get("sample_retention_days", args.sample_retention_days))

    insecure_ssl = bool(cfg.get("insecure_ssl", args.insecure_ssl))
    timeout_s = int(cfg.get("timeout_s", args.timeout_s))
    interval_s = int(cfg.get("interval_s", args.interval_s))

    status_json = args.status_json or cfg.get("status_json_path")
    serve_port = int(cfg.get("serve_port", args.serve))
    bind = str(cfg.get("bind", args.bind))

    state = StatusState()
    srv = None
    if serve_port:
        srv = run_http_server(bind, serve_port, state)

    prev_miner_counts: Dict[str, int] = {}
    try:
        while True:
            snap = monitor_once(
                nodes=nodes,
                timeout_s=timeout_s,
                insecure_ssl=insecure_ssl,
                miner_stale_s=miner_stale_s,
                miner_drop_threshold=miner_drop,
                state_db=state_db,
                discord_webhook=webhook,
                alert_cooldown_s=alert_cooldown_s,
                sample_retention_days=sample_retention_days,
                prev_miner_counts=prev_miner_counts,
            )
            state.update(snap)

            if status_json:
                outp = Path(status_json).expanduser().resolve()
                outp.parent.mkdir(parents=True, exist_ok=True)
                outp.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            if args.once:
                return 0

            time.sleep(interval_s)
    finally:
        if srv:
            srv.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())

