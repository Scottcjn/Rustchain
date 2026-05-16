# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from flask import Flask, jsonify, render_template_string, request

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS faucet_claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet TEXT NOT NULL,
    github_username TEXT,
    ip TEXT,
    amount REAL NOT NULL,
    created_at TEXT NOT NULL
);
"""

INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_faucet_claims_identity
ON faucet_claims(github_username, ip, created_at);
"""

FAUCET_HTML = """
<!doctype html>
<html>
  <head><title>RustChain Testnet Faucet</title></head>
  <body>
    <h1>RustChain Testnet Faucet</h1>
    <form method=\"post\" action=\"/faucet/drip\">
      <label>Wallet address <input name=\"wallet\" required /></label><br/>
      <label>GitHub username (optional) <input name=\"github_username\" /></label><br/>
      <button type=\"submit\">Request drip</button>
    </form>
  </body>
</html>
"""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def init_db(path: str) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(CREATE_SQL)
        conn.execute(INDEX_SQL)
        conn.commit()
    finally:
        conn.close()


def github_account_age_days(username: str, token: str | None = None) -> int | None:
    if not username:
        return None
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        resp = requests.get(f"https://api.github.com/users/{username}", headers=headers, timeout=10)
        if resp.status_code != 200:
            return None
        created_at = resp.json().get("created_at")
        if not created_at:
            return None
        created = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return (_utcnow() - created).days
    except Exception:
        return None


def _limit_for_identity(github_username: str | None, account_age_days: int | None) -> float:
    if not github_username:
        return 0.5
    if account_age_days is not None and account_age_days >= 365:
        return 2.0
    return 1.0


def _request_data() -> tuple[dict[str, Any] | None, tuple[Any, int] | None]:
    data = request.get_json(silent=True)
    if data is None:
        return request.form.to_dict() or {}, None
    if not isinstance(data, dict):
        return None, (jsonify({"ok": False, "error": "json_object_required"}), 400)
    return data, None


def _sum_last_24h(conn: sqlite3.Connection, github_username: str | None, ip: str) -> float:
    since = (_utcnow() - timedelta(hours=24)).isoformat()
    if github_username:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM faucet_claims WHERE github_username = ? AND created_at >= ?",
            (github_username, since),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM faucet_claims WHERE ip = ? AND created_at >= ?",
            (ip, since),
        ).fetchone()
    return float(row[0] if row else 0.0)


def _next_available(conn: sqlite3.Connection, github_username: str | None, ip: str) -> str:
    if github_username:
        row = conn.execute(
            "SELECT created_at FROM faucet_claims WHERE github_username = ? ORDER BY created_at DESC LIMIT 1",
            (github_username,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT created_at FROM faucet_claims WHERE ip = ? ORDER BY created_at DESC LIMIT 1",
            (ip,),
        ).fetchone()

    if not row:
        return _utcnow().isoformat()

    last = datetime.fromisoformat(row[0])
    return (last + timedelta(hours=24)).isoformat()


def _transfer(wallet: str, amount: float, cfg: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    if cfg.get("DRY_RUN", True):
        return True, {"ok": True, "txid": "dry-run", "amount": amount, "wallet": wallet}

    payload = {
        "to_address": wallet,
        "amount": amount,
        "from_wallet": cfg["FAUCET_POOL_WALLET"],
    }
    headers = {"Content-Type": "application/json"}
    if cfg.get("ADMIN_API_TOKEN"):
        headers["Authorization"] = f"Bearer {cfg['ADMIN_API_TOKEN']}"

    resp = requests.post(cfg["ADMIN_TRANSFER_URL"], json=payload, headers=headers, timeout=15)
    if resp.status_code >= 300:
        return False, {"error": f"transfer_failed_{resp.status_code}", "body": resp.text}
    try:
        return True, resp.json()
    except Exception:
        return True, {"raw": resp.text}


def create_app(config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    cfg = {
        "DB_PATH": os.getenv("FAUCET_DB_PATH", "faucet.db"),
        "ADMIN_TRANSFER_URL": os.getenv("FAUCET_ADMIN_TRANSFER_URL", "http://127.0.0.1:8080/wallet/transfer"),
        "ADMIN_API_TOKEN": os.getenv("FAUCET_ADMIN_API_TOKEN", ""),
        "FAUCET_POOL_WALLET": os.getenv("FAUCET_POOL_WALLET", "faucet_pool"),
        "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN", ""),
        "DRY_RUN": os.getenv("FAUCET_DRY_RUN", "1") == "1",
    }
    if config:
        cfg.update(config)

    init_db(cfg["DB_PATH"])

    @app.get("/faucet")
    def faucet_page():
        return render_template_string(FAUCET_HTML)

    @app.post("/faucet/drip")
    def faucet_drip():
        data, error = _request_data()
        if error:
            return error
        wallet = (data.get("wallet") or "").strip()
        github_username = (data.get("github_username") or "").strip() or None
        ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()

        if not wallet:
            return jsonify({"ok": False, "error": "wallet_required"}), 400

        age_days = github_account_age_days(github_username or "", cfg.get("GITHUB_TOKEN")) if github_username else None
        daily_limit = _limit_for_identity(github_username, age_days)
        drip_amount = 1.0 if github_username else 0.5

        conn = sqlite3.connect(cfg["DB_PATH"])
        try:
            used = _sum_last_24h(conn, github_username, ip)
            if used + drip_amount > daily_limit:
                return jsonify(
                    {
                        "ok": False,
                        "error": "rate_limited",
                        "daily_limit": daily_limit,
                        "used": round(used, 3),
                        "next_available": _next_available(conn, github_username, ip),
                    }
                ), 429

            sent_ok, transfer_meta = _transfer(wallet, drip_amount, cfg)
            if not sent_ok:
                return jsonify({"ok": False, "error": "transfer_failed", "details": transfer_meta}), 502

            now = _utcnow().isoformat()
            cur = conn.execute(
                "INSERT INTO faucet_claims(wallet, github_username, ip, amount, created_at) VALUES(?,?,?,?,?)",
                (wallet, github_username, ip, drip_amount, now),
            )
            conn.commit()

            return jsonify(
                {
                    "ok": True,
                    "amount": drip_amount,
                    "pending_id": int(cur.lastrowid),
                    "next_available": (_utcnow() + timedelta(hours=24)).isoformat(),
                    "transfer": transfer_meta,
                }
            )
        finally:
            conn.close()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8090")))
