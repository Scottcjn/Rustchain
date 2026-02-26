#!/usr/bin/env python3
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List

import requests
from flask import Flask, render_template

BASE_URL = os.getenv("RUSTCHAIN_API_BASE", "https://rustchain.org")
TIMEOUT = float(os.getenv("RUSTCHAIN_API_TIMEOUT", "8"))

app = Flask(__name__, template_folder="templates", static_folder="static")


def _get_json(path: str) -> Any:
    url = f"{BASE_URL}{path}"
    r = requests.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def _safe_get(path: str, fallback: Any) -> Any:
    try:
        return _get_json(path)
    except Exception:
        return fallback


def _normalize_miners(miners: Any) -> List[Dict[str, Any]]:
    if not isinstance(miners, list):
        return []
    out: List[Dict[str, Any]] = []
    for m in miners[:300]:
        if not isinstance(m, dict):
            continue
        out.append({
            "miner_id": m.get("miner_id") or m.get("id") or "-",
            "arch": m.get("arch") or m.get("architecture") or "-",
            "weight": m.get("weight") or m.get("multiplier") or "-",
            "last_seen": m.get("last_seen") or m.get("updated_at") or m.get("timestamp") or "-",
            "balance": m.get("balance") or m.get("amount") or "-",
        })
    return out


def _normalize_txs(epoch_data: Any) -> List[Dict[str, Any]]:
    if not isinstance(epoch_data, dict):
        return []
    candidates = epoch_data.get("transactions") or epoch_data.get("txs") or epoch_data.get("history") or []
    if not isinstance(candidates, list):
        return []
    txs: List[Dict[str, Any]] = []
    for t in candidates[:200]:
        if not isinstance(t, dict):
            continue
        txs.append({
            "tx_hash": t.get("tx_hash") or t.get("hash") or "-",
            "from": t.get("from") or t.get("from_address") or "-",
            "to": t.get("to") or t.get("to_address") or "-",
            "amount": t.get("amount") or t.get("value") or "-",
            "ts": t.get("timestamp") or t.get("created_at") or "-",
        })
    return txs


@app.route("/")
def index():
    health = _safe_get("/health", {})
    miners_raw = _safe_get("/api/miners", [])
    epoch = _safe_get("/epoch", {})

    miners = _normalize_miners(miners_raw)
    txs = _normalize_txs(epoch)

    summary = {
        "active_miners": len(miners),
        "epoch": (epoch.get("epoch") if isinstance(epoch, dict) else "-") or "-",
        "version": (health.get("version") if isinstance(health, dict) else "-") or "-",
        "tip_age_slots": (health.get("tip_age_slots") if isinstance(health, dict) else "-") or "-",
        "uptime_s": (health.get("uptime_s") if isinstance(health, dict) else "-") or "-",
    }

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    return render_template(
        "index.html",
        base_url=BASE_URL,
        summary=summary,
        health=health if isinstance(health, dict) else {},
        epoch=epoch if isinstance(epoch, dict) else {},
        miners=miners,
        txs=txs,
        now_utc=now_utc,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")), debug=False)
