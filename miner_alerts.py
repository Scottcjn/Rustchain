#!/usr/bin/env python3
"""RustChain miner alert system (email + optional Twilio SMS)."""

from __future__ import annotations
import argparse
import json
import os
import smtplib
import ssl
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Dict, Any

import requests

try:
    from twilio.rest import Client as TwilioClient
except Exception:  # pragma: no cover
    TwilioClient = None

DEFAULT_API = os.getenv("RUSTCHAIN_API", "https://50.28.86.131")
STATE_FILE = Path(os.getenv("ALERT_STATE_FILE", "miner_alert_state.json"))
WATCHLIST_FILE = Path(os.getenv("WATCHLIST_FILE", "miner_watchlist.json"))


@dataclass
class Cfg:
    api: str
    interval: int
    transfer_threshold: float
    attestation_stale_seconds: int


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def fetch_miners(api: str):
    r = requests.get(f"{api}/api/miners", timeout=20, verify=False)
    r.raise_for_status()
    d = r.json()
    return d.get("miners") or d.get("items") or []


def fetch_balance(api: str, miner_id: str) -> float:
    try:
        r = requests.get(f"{api}/wallet/balance", params={"miner_id": miner_id}, timeout=15, verify=False)
        if r.status_code != 200:
            return 0.0
        d = r.json()
        return float(d.get("balance", 0) or 0)
    except Exception:
        return 0.0


def send_email(to_addr: str, subject: str, body: str):
    host = os.getenv("SMTP_SERVER", "")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    pw = os.getenv("SMTP_PASSWORD", "")
    sender = os.getenv("SMTP_FROM", user)
    if not (host and user and pw and sender and to_addr):
        return False, "smtp_not_configured"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_addr
    msg.set_content(body)

    ctx = ssl.create_default_context()
    with smtplib.SMTP(host, port, timeout=20) as s:
        s.starttls(context=ctx)
        s.login(user, pw)
        s.send_message(msg)
    return True, "sent"


def send_sms(phone: str, body: str):
    sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    token = os.getenv("TWILIO_AUTH_TOKEN", "")
    sender = os.getenv("TWILIO_PHONE_NUMBER", "")
    if not (sid and token and sender and phone and TwilioClient):
        return False, "twilio_not_configured"
    c = TwilioClient(sid, token)
    c.messages.create(from_=sender, to=phone, body=body[:1500])
    return True, "sent"


def notify(w: Dict[str, Any], title: str, body: str):
    out = []
    if w.get("email"):
        ok, msg = send_email(w["email"], title, body)
        out.append(("email", ok, msg))
    if w.get("phone"):
        ok, msg = send_sms(w["phone"], f"{title}\n{body}")
        out.append(("sms", ok, msg))
    return out


def check_once(cfg: Cfg):
    watch = load_json(WATCHLIST_FILE, {"miners": []})
    state = load_json(STATE_FILE, {"miners": {}})
    state.setdefault("miners", {})

    miners = fetch_miners(cfg.api)
    by_id = {m.get("miner_id") or m.get("id") or m.get("wallet", ""): m for m in miners}

    events = []
    for w in watch.get("miners", []):
        mid = w.get("miner_id", "").strip()
        if not mid:
            continue
        prev = state["miners"].get(mid, {})
        m = by_id.get(mid)
        online = bool(m)
        prev_online = bool(prev.get("online", False))

        # offline/online transition
        if prev and prev_online and not online:
            events.append((w, "Miner offline", f"{mid} went offline at {now_iso()}"))
        if prev and (not prev_online) and online:
            events.append((w, "Miner recovered", f"{mid} is back online at {now_iso()}"))

        bal = fetch_balance(cfg.api, mid)
        prev_bal = float(prev.get("balance", bal))
        delta = bal - prev_bal
        if delta > 0.0001:
            events.append((w, "Rewards received", f"{mid} balance increased by {delta:.4f} RTC (now {bal:.4f})"))
        if abs(delta) >= cfg.transfer_threshold:
            events.append((w, "Large transfer detected", f"{mid} balance delta {delta:.4f} RTC exceeds threshold {cfg.transfer_threshold}"))

        last_att = float((m or {}).get("last_attest") or 0)
        if online and last_att > 0 and (time.time() - last_att) > cfg.attestation_stale_seconds:
            events.append((w, "Attestation stale", f"{mid} last attestation is stale ({int((time.time()-last_att)/60)} min ago)"))

        state["miners"][mid] = {
            "online": online,
            "balance": bal,
            "last_attest": last_att,
            "updated_at": now_iso(),
        }

    for w, title, body in events:
        notify(w, f"[RustChain Alert] {title}", body)

    save_json(STATE_FILE, state)
    return len(events)


def main():
    ap = argparse.ArgumentParser(description="RustChain miner alerts")
    ap.add_argument("--api", default=DEFAULT_API)
    ap.add_argument("--interval", type=int, default=int(os.getenv("ALERT_INTERVAL", "300")))
    ap.add_argument("--transfer-threshold", type=float, default=float(os.getenv("TRANSFER_THRESHOLD", "50")))
    ap.add_argument("--attestation-stale-seconds", type=int, default=int(os.getenv("ATTEST_STALE_SECONDS", "18000")))
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()

    cfg = Cfg(args.api, args.interval, args.transfer_threshold, args.attestation_stale_seconds)

    if args.once:
        n = check_once(cfg)
        print(f"events={n}")
        return

    while True:
        try:
            n = check_once(cfg)
            print(f"[{now_iso()}] events={n}")
        except Exception as e:
            print(f"[{now_iso()}] error={e}")
        time.sleep(max(30, cfg.interval))


if __name__ == "__main__":
    requests.packages.urllib3.disable_warnings()  # self-signed node certs
    main()
