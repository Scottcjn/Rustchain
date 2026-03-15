#!/usr/bin/env python3
"""
RustChain Email Notification Service

Subscribe to blockchain events (new epoch, miner changes, balance changes)
and receive HTML email alerts via SMTP. Supports digest mode (hourly/daily)
and per-subscriber unsubscribe management.
"""

import json
import hashlib
import hmac
import logging
import os
import smtplib
import sqlite3
import threading
import time
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from pathlib import Path
from typing import Optional

log = logging.getLogger("rustchain.email-alerts")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_NODE_URL = "https://50.28.86.131"
DEFAULT_DB_PATH = Path.home() / ".rustchain" / "email_alerts.db"
DEFAULT_POLL_INTERVAL = 30  # seconds
UNSUBSCRIBE_SECRET = os.getenv("RUSTCHAIN_UNSUB_SECRET", "change-me-in-production")


# ---------------------------------------------------------------------------
# Enums & data classes
# ---------------------------------------------------------------------------

class EventType(str, Enum):
    NEW_EPOCH = "new_epoch"
    MINER_CHANGE = "miner_change"
    BALANCE_CHANGE = "balance_change"


class DigestMode(str, Enum):
    INSTANT = "instant"
    HOURLY = "hourly"
    DAILY = "daily"


@dataclass
class Subscriber:
    email: str
    events: list[str]
    digest: str = DigestMode.INSTANT
    wallet: str = ""
    active: bool = True
    created_at: str = ""
    token: str = ""


@dataclass
class Event:
    event_type: str
    payload: dict
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# SMTP presets
# ---------------------------------------------------------------------------

SMTP_PRESETS = {
    "gmail": {"host": "smtp.gmail.com", "port": 587, "tls": True},
    "outlook": {"host": "smtp.office365.com", "port": 587, "tls": True},
    "yahoo": {"host": "smtp.mail.yahoo.com", "port": 587, "tls": True},
}


@dataclass
class SMTPConfig:
    host: str = "smtp.gmail.com"
    port: int = 587
    tls: bool = True
    username: str = ""
    password: str = ""
    from_addr: str = ""

    @classmethod
    def from_env(cls) -> "SMTPConfig":
        preset_name = os.getenv("RUSTCHAIN_SMTP_PRESET", "").lower()
        preset = SMTP_PRESETS.get(preset_name, {})
        return cls(
            host=os.getenv("RUSTCHAIN_SMTP_HOST", preset.get("host", "smtp.gmail.com")),
            port=int(os.getenv("RUSTCHAIN_SMTP_PORT", preset.get("port", 587))),
            tls=os.getenv("RUSTCHAIN_SMTP_TLS", str(preset.get("tls", True))).lower()
            in ("true", "1", "yes"),
            username=os.getenv("RUSTCHAIN_SMTP_USER", ""),
            password=os.getenv("RUSTCHAIN_SMTP_PASS", ""),
            from_addr=os.getenv(
                "RUSTCHAIN_SMTP_FROM",
                os.getenv("RUSTCHAIN_SMTP_USER", "alerts@rustchain.org"),
            ),
        )


# ---------------------------------------------------------------------------
# Template loader
# ---------------------------------------------------------------------------

TEMPLATE_DIR = Path(__file__).parent / "templates"


def _load_template(name: str) -> str:
    path = TEMPLATE_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Template not found: {path}")


def _render(template: str, ctx: dict) -> str:
    """Minimal {{ key }} replacement."""
    out = template
    for key, val in ctx.items():
        out = out.replace("{{" + f" {key} " + "}}", str(val))
        out = out.replace("{{" + key + "}}", str(val))
    return out


# ---------------------------------------------------------------------------
# Database layer
# ---------------------------------------------------------------------------

class SubscriberStore:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._lock = threading.Lock()
        self._init_tables()

    def _init_tables(self):
        with self._lock, self._conn:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS subscribers (
                    email       TEXT PRIMARY KEY,
                    events      TEXT NOT NULL,
                    digest      TEXT NOT NULL DEFAULT 'instant',
                    wallet      TEXT NOT NULL DEFAULT '',
                    active      INTEGER NOT NULL DEFAULT 1,
                    created_at  TEXT NOT NULL,
                    token       TEXT NOT NULL
                )
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS pending_digests (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    email       TEXT NOT NULL,
                    event_type  TEXT NOT NULL,
                    payload     TEXT NOT NULL,
                    created_at  TEXT NOT NULL,
                    FOREIGN KEY (email) REFERENCES subscribers(email)
                )
            """)

    @staticmethod
    def _make_token(email: str) -> str:
        return hmac.new(
            UNSUBSCRIBE_SECRET.encode(), email.encode(), hashlib.sha256
        ).hexdigest()[:16]

    def subscribe(self, sub: Subscriber) -> Subscriber:
        sub.created_at = sub.created_at or datetime.now(timezone.utc).isoformat()
        sub.token = self._make_token(sub.email)
        with self._lock, self._conn:
            self._conn.execute(
                """INSERT OR REPLACE INTO subscribers
                   (email, events, digest, wallet, active, created_at, token)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    sub.email,
                    json.dumps(sub.events),
                    sub.digest,
                    sub.wallet,
                    int(sub.active),
                    sub.created_at,
                    sub.token,
                ),
            )
        log.info("Subscribed %s to %s (digest=%s)", sub.email, sub.events, sub.digest)
        return sub

    def unsubscribe(self, email: str, token: str) -> bool:
        expected = self._make_token(email)
        if not hmac.compare_digest(token, expected):
            log.warning("Invalid unsubscribe token for %s", email)
            return False
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE subscribers SET active = 0 WHERE email = ?", (email,)
            )
        log.info("Unsubscribed %s", email)
        return True

    def resubscribe(self, email: str) -> bool:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "UPDATE subscribers SET active = 1 WHERE email = ?", (email,)
            )
        return cur.rowcount > 0

    def get_subscribers(self, event_type: str) -> list[Subscriber]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT email, events, digest, wallet, active, created_at, token "
                "FROM subscribers WHERE active = 1"
            ).fetchall()
        out = []
        for row in rows:
            events = json.loads(row[1])
            if event_type in events:
                out.append(
                    Subscriber(
                        email=row[0],
                        events=events,
                        digest=row[2],
                        wallet=row[3],
                        active=bool(row[4]),
                        created_at=row[5],
                        token=row[6],
                    )
                )
        return out

    def list_all(self) -> list[Subscriber]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT email, events, digest, wallet, active, created_at, token "
                "FROM subscribers"
            ).fetchall()
        return [
            Subscriber(
                email=r[0],
                events=json.loads(r[1]),
                digest=r[2],
                wallet=r[3],
                active=bool(r[4]),
                created_at=r[5],
                token=r[6],
            )
            for r in rows
        ]

    # -- digest queue -------------------------------------------------------

    def queue_digest(self, email: str, event: Event):
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO pending_digests (email, event_type, payload, created_at) "
                "VALUES (?, ?, ?, ?)",
                (email, event.event_type, json.dumps(event.payload), event.timestamp),
            )

    def flush_digest(self, email: str) -> list[Event]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT event_type, payload, created_at FROM pending_digests "
                "WHERE email = ? ORDER BY created_at",
                (email,),
            ).fetchall()
            self._conn.execute(
                "DELETE FROM pending_digests WHERE email = ?", (email,)
            )
            self._conn.commit()
        return [Event(r[0], json.loads(r[1]), r[2]) for r in rows]

    def close(self):
        self._conn.close()


# ---------------------------------------------------------------------------
# Email sender
# ---------------------------------------------------------------------------

class EmailSender:
    def __init__(self, smtp: SMTPConfig):
        self.smtp = smtp

    def send(self, to: str, subject: str, html_body: str):
        msg = MIMEMultipart("alternative")
        msg["From"] = self.smtp.from_addr
        msg["To"] = to
        msg["Subject"] = subject

        # plain text fallback
        plain = html_body.replace("<br>", "\n").replace("</p>", "\n")
        import re
        plain = re.sub(r"<[^>]+>", "", plain)

        msg.attach(MIMEText(plain, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        try:
            if self.smtp.tls:
                server = smtplib.SMTP(self.smtp.host, self.smtp.port, timeout=15)
                server.ehlo()
                server.starttls()
            else:
                server = smtplib.SMTP(self.smtp.host, self.smtp.port, timeout=15)

            if self.smtp.username:
                server.login(self.smtp.username, self.smtp.password)

            server.sendmail(self.smtp.from_addr, [to], msg.as_string())
            server.quit()
            log.info("Email sent to %s: %s", to, subject)
        except Exception:
            log.exception("Failed to send email to %s", to)
            raise


# ---------------------------------------------------------------------------
# Node poller
# ---------------------------------------------------------------------------

class NodePoller:
    """Polls the RustChain node for state changes."""

    def __init__(self, node_url: str = DEFAULT_NODE_URL):
        self.node_url = node_url.rstrip("/")
        self._last_epoch: Optional[int] = None
        self._last_miners: Optional[set] = None
        self._last_balances: dict[str, float] = {}

    def _get(self, path: str, timeout: int = 10) -> Optional[dict]:
        try:
            req = urllib.request.Request(
                f"{self.node_url}{path}",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except Exception as exc:
            log.debug("Polling %s failed: %s", path, exc)
            return None

    def check_epoch(self) -> Optional[Event]:
        data = self._get("/epoch")
        if data is None:
            return None
        epoch_num = data.get("epoch") or data.get("current_epoch")
        if epoch_num is None:
            return None
        if self._last_epoch is not None and epoch_num != self._last_epoch:
            event = Event(
                EventType.NEW_EPOCH,
                {
                    "previous_epoch": self._last_epoch,
                    "new_epoch": epoch_num,
                    "epoch_data": data,
                },
            )
            self._last_epoch = epoch_num
            return event
        self._last_epoch = epoch_num
        return None

    def check_miners(self) -> Optional[Event]:
        data = self._get("/miners") or self._get("/health")
        if data is None:
            return None
        miners = set()
        if isinstance(data, list):
            miners = {m.get("id", str(m)) for m in data}
        elif isinstance(data, dict) and "miners" in data:
            miners = set(data["miners"]) if isinstance(data["miners"], list) else set()
        elif isinstance(data, dict) and "active_miners" in data:
            miners = set(str(data["active_miners"]))

        if not miners:
            return None

        if self._last_miners is not None and miners != self._last_miners:
            joined = miners - self._last_miners
            left = self._last_miners - miners
            event = Event(
                EventType.MINER_CHANGE,
                {
                    "joined": list(joined),
                    "left": list(left),
                    "total_miners": len(miners),
                },
            )
            self._last_miners = miners
            return event
        self._last_miners = miners
        return None

    def check_balance(self, wallet: str) -> Optional[Event]:
        data = self._get(f"/balance/{wallet}")
        if data is None:
            return None
        balance = data.get("balance") or data.get("amount")
        if balance is None:
            return None
        balance = float(balance)
        old = self._last_balances.get(wallet)
        if old is not None and balance != old:
            event = Event(
                EventType.BALANCE_CHANGE,
                {
                    "wallet": wallet,
                    "old_balance": old,
                    "new_balance": balance,
                    "change": round(balance - old, 8),
                },
            )
            self._last_balances[wallet] = balance
            return event
        self._last_balances[wallet] = balance
        return None


# ---------------------------------------------------------------------------
# Alert service (main orchestrator)
# ---------------------------------------------------------------------------

class RustChainEmailAlerts:
    """
    Main service: polls the node, detects events, sends emails.

    Usage:
        svc = RustChainEmailAlerts()
        svc.subscribe("alice@example.com", ["new_epoch", "balance_change"],
                       digest="daily", wallet="RTC...")
        svc.start()     # starts background polling
        svc.stop()
    """

    def __init__(
        self,
        node_url: str = DEFAULT_NODE_URL,
        smtp: Optional[SMTPConfig] = None,
        db_path: Path = DEFAULT_DB_PATH,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
        base_url: str = "https://alerts.rustchain.org",
    ):
        self.store = SubscriberStore(db_path)
        self.sender = EmailSender(smtp or SMTPConfig.from_env())
        self.poller = NodePoller(node_url)
        self.poll_interval = poll_interval
        self.base_url = base_url.rstrip("/")
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._digest_thread: Optional[threading.Thread] = None

    # -- public API ---------------------------------------------------------

    def subscribe(
        self,
        email: str,
        events: list[str],
        digest: str = DigestMode.INSTANT,
        wallet: str = "",
    ) -> Subscriber:
        sub = Subscriber(email=email, events=events, digest=digest, wallet=wallet)
        self.store.subscribe(sub)
        # send welcome email
        try:
            html = _load_template("welcome.html")
            html = _render(html, {
                "email": email,
                "events": ", ".join(events),
                "digest": digest,
                "unsubscribe_url": self._unsub_url(email, sub.token),
            })
            self.sender.send(email, "Welcome to RustChain Alerts", html)
        except Exception:
            log.debug("Could not send welcome email (template or SMTP issue)")
        return sub

    def unsubscribe(self, email: str, token: str) -> bool:
        return self.store.unsubscribe(email, token)

    def list_subscribers(self) -> list[Subscriber]:
        return self.store.list_all()

    def start(self):
        if self._thread and self._thread.is_alive():
            log.warning("Alert service already running")
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        self._digest_thread = threading.Thread(target=self._digest_loop, daemon=True)
        self._digest_thread.start()
        log.info("RustChain email alert service started (interval=%ds)", self.poll_interval)

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)
        if self._digest_thread:
            self._digest_thread.join(timeout=10)
        self.store.close()
        log.info("RustChain email alert service stopped")

    # -- internals ----------------------------------------------------------

    def _unsub_url(self, email: str, token: str) -> str:
        return f"{self.base_url}/unsubscribe?email={email}&token={token}"

    def _poll_loop(self):
        while not self._stop.is_set():
            try:
                self._poll_once()
            except Exception:
                log.exception("Poll cycle error")
            self._stop.wait(self.poll_interval)

    def _poll_once(self):
        # check epoch
        event = self.poller.check_epoch()
        if event:
            self._dispatch(event)

        # check miners
        event = self.poller.check_miners()
        if event:
            self._dispatch(event)

        # check balances for each subscribed wallet
        wallets = set()
        for sub in self.store.get_subscribers(EventType.BALANCE_CHANGE):
            if sub.wallet:
                wallets.add((sub.wallet, sub.email))
        for wallet, _ in wallets:
            event = self.poller.check_balance(wallet)
            if event:
                self._dispatch(event)

    def _dispatch(self, event: Event):
        subscribers = self.store.get_subscribers(event.event_type)
        if not subscribers:
            return

        # for balance_change, filter to matching wallet
        if event.event_type == EventType.BALANCE_CHANGE:
            wallet = event.payload.get("wallet", "")
            subscribers = [s for s in subscribers if s.wallet == wallet]

        for sub in subscribers:
            if sub.digest == DigestMode.INSTANT:
                self._send_event(sub, event)
            else:
                self.store.queue_digest(sub.email, event)

    def _send_event(self, sub: Subscriber, event: Event):
        try:
            template_name = f"{event.event_type}.html"
            html = _load_template(template_name)
        except FileNotFoundError:
            html = _load_template("generic_event.html")

        ctx = {
            "email": sub.email,
            "event_type": event.event_type.replace("_", " ").title(),
            "timestamp": event.timestamp,
            "unsubscribe_url": self._unsub_url(sub.email, sub.token),
            **event.payload,
        }
        # flatten nested dicts
        for k, v in list(ctx.items()):
            if isinstance(v, (dict, list)):
                ctx[k] = json.dumps(v, indent=2)

        html = _render(html, ctx)
        subject = f"RustChain Alert: {ctx['event_type']}"
        try:
            self.sender.send(sub.email, subject, html)
        except Exception:
            log.exception("Failed to deliver alert to %s", sub.email)

    def _digest_loop(self):
        """Flush digest queues on schedule."""
        last_hourly = datetime.now(timezone.utc)
        last_daily = datetime.now(timezone.utc)

        while not self._stop.is_set():
            now = datetime.now(timezone.utc)

            # hourly flush
            if (now - last_hourly) >= timedelta(hours=1):
                self._flush_digests(DigestMode.HOURLY)
                last_hourly = now

            # daily flush
            if (now - last_daily) >= timedelta(days=1):
                self._flush_digests(DigestMode.DAILY)
                last_daily = now

            self._stop.wait(60)

    def _flush_digests(self, mode: str):
        subs = [s for s in self.store.list_all() if s.active and s.digest == mode]
        for sub in subs:
            events = self.store.flush_digest(sub.email)
            if not events:
                continue
            self._send_digest(sub, events)

    def _send_digest(self, sub: Subscriber, events: list[Event]):
        try:
            html = _load_template("digest.html")
        except FileNotFoundError:
            html = _load_template("generic_event.html")

        rows = ""
        for ev in events:
            rows += (
                f"<tr><td>{ev.timestamp}</td>"
                f"<td>{ev.event_type.replace('_', ' ').title()}</td>"
                f"<td><pre>{json.dumps(ev.payload, indent=2)}</pre></td></tr>\n"
            )

        ctx = {
            "email": sub.email,
            "event_count": str(len(events)),
            "digest_mode": sub.digest.title(),
            "event_rows": rows,
            "unsubscribe_url": self._unsub_url(sub.email, sub.token),
        }
        html = _render(html, ctx)
        subject = f"RustChain {sub.digest.title()} Digest — {len(events)} events"
        try:
            self.sender.send(sub.email, subject, html)
        except Exception:
            log.exception("Failed to send digest to %s", sub.email)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(description="RustChain Email Alert Service")
    sub = parser.add_subparsers(dest="command")

    # --- run ---------------------------------------------------------------
    run_p = sub.add_parser("run", help="Start the alert polling service")
    run_p.add_argument("--node-url", default=DEFAULT_NODE_URL)
    run_p.add_argument("--interval", type=int, default=DEFAULT_POLL_INTERVAL)
    run_p.add_argument("--db", default=str(DEFAULT_DB_PATH))

    # --- subscribe ---------------------------------------------------------
    sub_p = sub.add_parser("subscribe", help="Add a subscriber")
    sub_p.add_argument("email")
    sub_p.add_argument(
        "--events",
        nargs="+",
        default=["new_epoch", "miner_change", "balance_change"],
    )
    sub_p.add_argument("--digest", choices=["instant", "hourly", "daily"], default="instant")
    sub_p.add_argument("--wallet", default="")
    sub_p.add_argument("--db", default=str(DEFAULT_DB_PATH))

    # --- unsubscribe -------------------------------------------------------
    unsub_p = sub.add_parser("unsubscribe", help="Remove a subscriber")
    unsub_p.add_argument("email")
    unsub_p.add_argument("token")
    unsub_p.add_argument("--db", default=str(DEFAULT_DB_PATH))

    # --- list --------------------------------------------------------------
    list_p = sub.add_parser("list", help="List all subscribers")
    list_p.add_argument("--db", default=str(DEFAULT_DB_PATH))

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.command == "run":
        svc = RustChainEmailAlerts(
            node_url=args.node_url,
            db_path=Path(args.db),
            poll_interval=args.interval,
        )
        svc.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            svc.stop()

    elif args.command == "subscribe":
        svc = RustChainEmailAlerts(db_path=Path(args.db))
        sub = svc.subscribe(args.email, args.events, args.digest, args.wallet)
        print(f"Subscribed {sub.email} (token={sub.token})")

    elif args.command == "unsubscribe":
        store = SubscriberStore(Path(args.db))
        ok = store.unsubscribe(args.email, args.token)
        print("Unsubscribed" if ok else "Invalid token")
        store.close()

    elif args.command == "list":
        store = SubscriberStore(Path(args.db))
        for s in store.list_all():
            status = "active" if s.active else "inactive"
            print(f"  {s.email}  events={s.events}  digest={s.digest}  [{status}]")
        store.close()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
