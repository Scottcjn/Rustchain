"""
RustChain Email Notification Service

Monitors RustChain miner activity and delivers email notifications for:
- Balance changes (deposits and withdrawals)
- New epoch reward distributions
- Attestation failures and miner offline events
- Daily mining summary digests

Designed for self-hosted deployment with configurable SMTP backends
(Gmail, SendGrid, AWS SES, or any standard SMTP provider).
"""

import argparse
import json
import logging
import os
import smtplib
import sqlite3
import ssl
import sys
import time
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from string import Template
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

# ─── Configuration ────────────────────────────────────────────────────────────

RUSTCHAIN_API = os.getenv("RUSTCHAIN_API", "https://rustchain.org")
VERIFY_SSL = os.getenv("RUSTCHAIN_VERIFY_SSL", "false").lower() == "true"

# Polling intervals (seconds)
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "60"))
EPOCH_CHECK_INTERVAL = int(os.getenv("EPOCH_CHECK_INTERVAL", "300"))
DIGEST_HOUR_UTC = int(os.getenv("DIGEST_HOUR_UTC", "8"))

# Thresholds
OFFLINE_THRESHOLD = int(os.getenv("OFFLINE_THRESHOLD", "600"))
BALANCE_CHANGE_MIN = float(os.getenv("BALANCE_CHANGE_MIN", "0.01"))

# SMTP
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "false").lower() == "true"

# Database
DB_PATH = os.getenv(
    "EMAIL_NOTIFIER_DB",
    str(Path.home() / ".rustchain" / "email_notifier.db"),
)

# Template directory
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

# Logging
logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
)
logger = logging.getLogger("email_notifier")


# ─── Template Engine ──────────────────────────────────────────────────────────

class TemplateEngine:
    """Loads and renders HTML email templates from the templates/ directory."""

    def __init__(self, template_dir: Path = TEMPLATE_DIR):
        self._dir = template_dir
        self._cache: Dict[str, Template] = {}

    def _load(self, name: str) -> Template:
        if name not in self._cache:
            path = self._dir / f"{name}.html"
            if not path.exists():
                raise FileNotFoundError(f"Template not found: {path}")
            self._cache[name] = Template(path.read_text(encoding="utf-8"))
        return self._cache[name]

    def render(self, name: str, **kwargs) -> str:
        tpl = self._load(name)
        kwargs.setdefault("year", datetime.now(timezone.utc).year)
        kwargs.setdefault("timestamp", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
        return tpl.safe_substitute(**kwargs)


# ─── Database ─────────────────────────────────────────────────────────────────

class NotifierDB:
    """SQLite store for subscribers, miner state snapshots, and delivery log."""

    def __init__(self, db_path: str = DB_PATH):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self):
        cur = self.conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS subscribers (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                miner_id      TEXT    NOT NULL,
                email         TEXT    NOT NULL,
                notify_balance    INTEGER DEFAULT 1,
                notify_epoch      INTEGER DEFAULT 1,
                notify_attestation INTEGER DEFAULT 1,
                notify_digest     INTEGER DEFAULT 1,
                created_at    INTEGER NOT NULL,
                active        INTEGER DEFAULT 1,
                UNIQUE(miner_id, email)
            );

            CREATE TABLE IF NOT EXISTS miner_snapshots (
                miner_id        TEXT PRIMARY KEY,
                balance_rtc     REAL    DEFAULT 0,
                last_epoch      INTEGER DEFAULT 0,
                last_attest_ts  INTEGER DEFAULT 0,
                is_online       INTEGER DEFAULT 1,
                epoch_rewards   REAL    DEFAULT 0,
                checked_at      INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS epoch_state (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                epoch_number    INTEGER NOT NULL UNIQUE,
                total_reward    REAL    DEFAULT 0,
                miner_count     INTEGER DEFAULT 0,
                settled_at      INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS delivery_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                subscriber_id INTEGER NOT NULL,
                event_type  TEXT    NOT NULL,
                subject     TEXT    NOT NULL,
                sent_at     INTEGER NOT NULL,
                success     INTEGER DEFAULT 1,
                error_msg   TEXT
            );

            CREATE TABLE IF NOT EXISTS daily_stats (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                miner_id    TEXT    NOT NULL,
                date_utc    TEXT    NOT NULL,
                blocks_mined    INTEGER DEFAULT 0,
                rewards_earned  REAL    DEFAULT 0,
                attestations    INTEGER DEFAULT 0,
                uptime_pct      REAL    DEFAULT 100.0,
                UNIQUE(miner_id, date_utc)
            );

            CREATE INDEX IF NOT EXISTS idx_sub_miner ON subscribers(miner_id);
            CREATE INDEX IF NOT EXISTS idx_log_sub   ON delivery_log(subscriber_id, sent_at);
            CREATE INDEX IF NOT EXISTS idx_stats_date ON daily_stats(miner_id, date_utc);
        """)
        self.conn.commit()

    # ── Subscribers ───────────────────────────────────────────────────────

    def subscribe(
        self,
        miner_id: str,
        email: str,
        notify_balance: bool = True,
        notify_epoch: bool = True,
        notify_attestation: bool = True,
        notify_digest: bool = True,
    ) -> int:
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO subscribers
                (miner_id, email, notify_balance, notify_epoch,
                 notify_attestation, notify_digest, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(miner_id, email) DO UPDATE SET
                notify_balance = excluded.notify_balance,
                notify_epoch = excluded.notify_epoch,
                notify_attestation = excluded.notify_attestation,
                notify_digest = excluded.notify_digest,
                active = 1
        """, (
            miner_id, email,
            int(notify_balance), int(notify_epoch),
            int(notify_attestation), int(notify_digest),
            int(time.time()),
        ))
        self.conn.commit()
        return cur.lastrowid

    def unsubscribe(self, miner_id: str, email: str):
        self.conn.execute(
            "UPDATE subscribers SET active = 0 WHERE miner_id = ? AND email = ?",
            (miner_id, email),
        )
        self.conn.commit()

    def get_subscribers(self, miner_id: str, event_type: str = None) -> List[dict]:
        query = "SELECT * FROM subscribers WHERE miner_id = ? AND active = 1"
        params = [miner_id]
        if event_type:
            col = f"notify_{event_type}"
            query += f" AND {col} = 1"
        rows = self.conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def get_all_active_miners(self) -> List[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT miner_id FROM subscribers WHERE active = 1"
        ).fetchall()
        return [r["miner_id"] for r in rows]

    # ── Miner state ──────────────────────────────────────────────────────

    def get_snapshot(self, miner_id: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM miner_snapshots WHERE miner_id = ?", (miner_id,)
        ).fetchone()
        return dict(row) if row else None

    def upsert_snapshot(self, miner_id: str, **fields):
        fields["checked_at"] = int(time.time())
        cols = ", ".join(fields.keys())
        placeholders = ", ".join(["?"] * len(fields))
        updates = ", ".join(f"{k} = excluded.{k}" for k in fields)
        self.conn.execute(f"""
            INSERT INTO miner_snapshots (miner_id, {cols})
            VALUES (?, {placeholders})
            ON CONFLICT(miner_id) DO UPDATE SET {updates}
        """, (miner_id, *fields.values()))
        self.conn.commit()

    # ── Epoch state ───────────────────────────────────────────────────────

    def get_last_epoch(self) -> int:
        row = self.conn.execute(
            "SELECT MAX(epoch_number) as e FROM epoch_state"
        ).fetchone()
        return row["e"] or 0

    def record_epoch(self, epoch_number: int, total_reward: float, miner_count: int):
        self.conn.execute("""
            INSERT OR IGNORE INTO epoch_state (epoch_number, total_reward, miner_count, settled_at)
            VALUES (?, ?, ?, ?)
        """, (epoch_number, total_reward, miner_count, int(time.time())))
        self.conn.commit()

    # ── Daily stats ───────────────────────────────────────────────────────

    def increment_daily_stats(self, miner_id: str, **fields):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        existing = self.conn.execute(
            "SELECT * FROM daily_stats WHERE miner_id = ? AND date_utc = ?",
            (miner_id, today),
        ).fetchone()

        if existing:
            updates = []
            params = []
            for k, v in fields.items():
                updates.append(f"{k} = {k} + ?")
                params.append(v)
            params.extend([miner_id, today])
            self.conn.execute(
                f"UPDATE daily_stats SET {', '.join(updates)} "
                f"WHERE miner_id = ? AND date_utc = ?",
                params,
            )
        else:
            fields["miner_id"] = miner_id
            fields["date_utc"] = today
            cols = ", ".join(fields.keys())
            placeholders = ", ".join(["?"] * len(fields))
            self.conn.execute(
                f"INSERT INTO daily_stats ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
        self.conn.commit()

    def get_daily_stats(self, miner_id: str, date_utc: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM daily_stats WHERE miner_id = ? AND date_utc = ?",
            (miner_id, date_utc),
        ).fetchone()
        return dict(row) if row else None

    # ── Delivery log ─────────────────────────────────────────────────────

    def log_delivery(
        self, subscriber_id: int, event_type: str, subject: str,
        success: bool = True, error_msg: str = None,
    ):
        self.conn.execute("""
            INSERT INTO delivery_log (subscriber_id, event_type, subject, sent_at, success, error_msg)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (subscriber_id, event_type, subject, int(time.time()), int(success), error_msg))
        self.conn.commit()


# ─── SMTP Mailer ──────────────────────────────────────────────────────────────

class Mailer:
    """Sends HTML emails via SMTP with TLS/SSL support and delivery retry."""

    MAX_RETRIES = 3
    RETRY_DELAY = 5

    def __init__(
        self,
        host: str = SMTP_HOST,
        port: int = SMTP_PORT,
        user: str = SMTP_USER,
        password: str = SMTP_PASS,
        from_addr: str = SMTP_FROM,
        use_tls: bool = SMTP_USE_TLS,
        use_ssl: bool = SMTP_USE_SSL,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.from_addr = from_addr or user
        self.use_tls = use_tls
        self.use_ssl = use_ssl

    def _connect(self) -> smtplib.SMTP:
        ctx = ssl.create_default_context()
        if self.use_ssl:
            server = smtplib.SMTP_SSL(self.host, self.port, context=ctx)
        else:
            server = smtplib.SMTP(self.host, self.port, timeout=30)
            if self.use_tls:
                server.starttls(context=ctx)
        if self.user and self.password:
            server.login(self.user, self.password)
        return server

    def send(self, to_addr: str, subject: str, html_body: str, plain_body: str = None) -> bool:
        msg = MIMEMultipart("alternative")
        msg["From"] = self.from_addr
        msg["To"] = to_addr
        msg["Subject"] = subject

        if plain_body:
            msg.attach(MIMEText(plain_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                server = self._connect()
                server.sendmail(self.from_addr, [to_addr], msg.as_string())
                server.quit()
                logger.info("Email sent to %s: %s", to_addr, subject)
                return True
            except smtplib.SMTPException as exc:
                logger.warning(
                    "SMTP attempt %d/%d failed for %s: %s",
                    attempt, self.MAX_RETRIES, to_addr, exc,
                )
                if attempt < self.MAX_RETRIES:
                    time.sleep(self.RETRY_DELAY * attempt)
            except Exception as exc:
                logger.error("Unexpected mailer error: %s", exc)
                return False
        return False


# ─── RustChain API Client ─────────────────────────────────────────────────────

class RustChainAPI:
    """Thin wrapper around the RustChain node HTTP API."""

    def __init__(self, base_url: str = RUSTCHAIN_API, verify_ssl: bool = VERIFY_SSL):
        self.base = base_url.rstrip("/")
        self.verify = verify_ssl
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "RustChain-EmailNotifier/1.0"

    def _get(self, path: str, params: dict = None) -> Optional[dict]:
        try:
            r = self.session.get(
                f"{self.base}{path}",
                params=params,
                verify=self.verify,
                timeout=15,
            )
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            logger.error("API request failed [%s]: %s", path, exc)
            return None

    def get_balance(self, miner_id: str) -> Optional[float]:
        data = self._get("/balance", {"address": miner_id})
        if data and "balance" in data:
            return float(data["balance"])
        return None

    def get_miner_status(self, miner_id: str) -> Optional[dict]:
        data = self._get(f"/api/miners/{miner_id}")
        return data

    def get_active_miners(self) -> Optional[List[dict]]:
        return self._get("/api/miners")

    def get_current_epoch(self) -> Optional[dict]:
        return self._get("/api/epoch/current")

    def get_epoch_rewards(self, epoch: int) -> Optional[dict]:
        return self._get(f"/api/epoch/{epoch}/rewards")

    def get_attestation_status(self, miner_id: str) -> Optional[dict]:
        data = self._get(f"/api/miners/{miner_id}/attestation")
        return data


# ─── Event Monitors ──────────────────────────────────────────────────────────

class BalanceMonitor:
    """Detects balance changes and fires notifications."""

    def __init__(self, db: NotifierDB, api: RustChainAPI, mailer: Mailer, tpl: TemplateEngine):
        self.db = db
        self.api = api
        self.mailer = mailer
        self.tpl = tpl

    def check(self, miner_id: str):
        balance = self.api.get_balance(miner_id)
        if balance is None:
            return

        snapshot = self.db.get_snapshot(miner_id)
        prev_balance = snapshot["balance_rtc"] if snapshot else 0.0
        delta = balance - prev_balance

        self.db.upsert_snapshot(miner_id, balance_rtc=balance)

        if abs(delta) < BALANCE_CHANGE_MIN:
            return

        direction = "increased" if delta > 0 else "decreased"
        event_type = "balance"
        subject = f"RustChain: Balance {direction} by {abs(delta):.4f} RTC"

        html = self.tpl.render(
            "balance_change",
            miner_id=miner_id,
            direction=direction,
            delta=f"{abs(delta):.4f}",
            new_balance=f"{balance:.4f}",
            prev_balance=f"{prev_balance:.4f}",
        )

        if delta > 0:
            self.db.increment_daily_stats(miner_id, rewards_earned=delta)

        for sub in self.db.get_subscribers(miner_id, event_type):
            ok = self.mailer.send(sub["email"], subject, html)
            self.db.log_delivery(sub["id"], event_type, subject, success=ok)


class EpochMonitor:
    """Watches for new epoch settlements and notifies subscribers."""

    def __init__(self, db: NotifierDB, api: RustChainAPI, mailer: Mailer, tpl: TemplateEngine):
        self.db = db
        self.api = api
        self.mailer = mailer
        self.tpl = tpl

    def check(self):
        epoch_data = self.api.get_current_epoch()
        if not epoch_data:
            return

        current_epoch = epoch_data.get("epoch", 0)
        last_known = self.db.get_last_epoch()

        if current_epoch <= last_known:
            return

        for epoch_num in range(last_known + 1, current_epoch + 1):
            rewards = self.api.get_epoch_rewards(epoch_num)
            total_reward = rewards.get("total_reward", 0) if rewards else 0
            miner_count = rewards.get("miner_count", 0) if rewards else 0
            per_miner = rewards.get("distributions", {}) if rewards else {}

            self.db.record_epoch(epoch_num, total_reward, miner_count)

            for miner_id in self.db.get_all_active_miners():
                miner_reward = per_miner.get(miner_id, 0)
                if miner_reward <= 0:
                    continue

                subject = f"RustChain: Epoch {epoch_num} reward — {miner_reward:.4f} RTC"
                html = self.tpl.render(
                    "epoch_reward",
                    miner_id=miner_id,
                    epoch_number=epoch_num,
                    miner_reward=f"{miner_reward:.4f}",
                    total_reward=f"{total_reward:.4f}",
                    miner_count=miner_count,
                )

                for sub in self.db.get_subscribers(miner_id, "epoch"):
                    ok = self.mailer.send(sub["email"], subject, html)
                    self.db.log_delivery(sub["id"], "epoch", subject, success=ok)


class AttestationMonitor:
    """Monitors attestation health and alerts on failures or offline events."""

    def __init__(self, db: NotifierDB, api: RustChainAPI, mailer: Mailer, tpl: TemplateEngine):
        self.db = db
        self.api = api
        self.mailer = mailer
        self.tpl = tpl

    def check(self, miner_id: str):
        status = self.api.get_miner_status(miner_id)
        if not status:
            return

        now = int(time.time())
        snapshot = self.db.get_snapshot(miner_id)
        was_online = snapshot["is_online"] if snapshot else 1
        prev_attest = snapshot["last_attest_ts"] if snapshot else 0

        last_attest = status.get("last_attestation", 0)
        is_active = status.get("active", False)

        # Detect attestation staleness
        attest_age = now - last_attest if last_attest else now
        is_online = 1 if (is_active and attest_age < OFFLINE_THRESHOLD) else 0

        self.db.upsert_snapshot(
            miner_id,
            last_attest_ts=last_attest,
            is_online=is_online,
        )

        if is_online:
            self.db.increment_daily_stats(miner_id, attestations=1)

        # Went offline
        if was_online and not is_online:
            subject = f"RustChain: Miner {miner_id[:12]}... went OFFLINE"
            html = self.tpl.render(
                "attestation_failure",
                miner_id=miner_id,
                status="OFFLINE",
                detail="No attestation received within the expected threshold.",
                last_attestation=datetime.fromtimestamp(
                    last_attest, tz=timezone.utc
                ).strftime("%Y-%m-%d %H:%M UTC") if last_attest else "Never",
                threshold_minutes=OFFLINE_THRESHOLD // 60,
            )
            for sub in self.db.get_subscribers(miner_id, "attestation"):
                ok = self.mailer.send(sub["email"], subject, html)
                self.db.log_delivery(sub["id"], "attestation", subject, success=ok)

        # Came back online
        if not was_online and is_online:
            subject = f"RustChain: Miner {miner_id[:12]}... is back ONLINE"
            html = self.tpl.render(
                "attestation_recovery",
                miner_id=miner_id,
                status="ONLINE",
                detail="Miner has resumed attesting successfully.",
                last_attestation=datetime.fromtimestamp(
                    last_attest, tz=timezone.utc
                ).strftime("%Y-%m-%d %H:%M UTC"),
            )
            for sub in self.db.get_subscribers(miner_id, "attestation"):
                ok = self.mailer.send(sub["email"], subject, html)
                self.db.log_delivery(sub["id"], "attestation", subject, success=ok)


class DigestGenerator:
    """Produces and sends a daily mining summary email."""

    def __init__(self, db: NotifierDB, api: RustChainAPI, mailer: Mailer, tpl: TemplateEngine):
        self.db = db
        self.api = api
        self.mailer = mailer
        self.tpl = tpl
        self._last_digest_date: Optional[str] = None

    def maybe_send(self):
        now = datetime.now(timezone.utc)
        today_str = now.strftime("%Y-%m-%d")

        if self._last_digest_date == today_str:
            return
        if now.hour != DIGEST_HOUR_UTC:
            return

        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")

        for miner_id in self.db.get_all_active_miners():
            subs = self.db.get_subscribers(miner_id, "digest")
            if not subs:
                continue

            stats = self.db.get_daily_stats(miner_id, yesterday)
            snapshot = self.db.get_snapshot(miner_id)
            balance = snapshot["balance_rtc"] if snapshot else 0.0

            blocks = stats["blocks_mined"] if stats else 0
            rewards = stats["rewards_earned"] if stats else 0.0
            attestations = stats["attestations"] if stats else 0
            uptime = stats["uptime_pct"] if stats else 0.0

            subject = f"RustChain Daily Digest — {yesterday}"
            html = self.tpl.render(
                "daily_digest",
                miner_id=miner_id,
                date=yesterday,
                current_balance=f"{balance:.4f}",
                blocks_mined=blocks,
                rewards_earned=f"{rewards:.4f}",
                attestations=attestations,
                uptime_pct=f"{uptime:.1f}",
                online_status="Online" if (snapshot and snapshot["is_online"]) else "Offline",
            )

            for sub in subs:
                ok = self.mailer.send(sub["email"], subject, html)
                self.db.log_delivery(sub["id"], "digest", subject, success=ok)

        self._last_digest_date = today_str
        logger.info("Daily digest sent for %s", yesterday)


# ─── Main Service Loop ───────────────────────────────────────────────────────

class EmailNotificationService:
    """Orchestrates all monitors in a single polling loop."""

    def __init__(self):
        self.db = NotifierDB()
        self.api = RustChainAPI()
        self.mailer = Mailer()
        self.tpl = TemplateEngine()

        self.balance_mon = BalanceMonitor(self.db, self.api, self.mailer, self.tpl)
        self.epoch_mon = EpochMonitor(self.db, self.api, self.mailer, self.tpl)
        self.attest_mon = AttestationMonitor(self.db, self.api, self.mailer, self.tpl)
        self.digest_gen = DigestGenerator(self.db, self.api, self.mailer, self.tpl)

    def run_once(self):
        miners = self.db.get_all_active_miners()
        if not miners:
            logger.debug("No active subscriptions, skipping cycle")
            return

        for miner_id in miners:
            try:
                self.balance_mon.check(miner_id)
                self.attest_mon.check(miner_id)
            except Exception as exc:
                logger.error("Error checking miner %s: %s", miner_id, exc)

        try:
            self.epoch_mon.check()
        except Exception as exc:
            logger.error("Error checking epoch state: %s", exc)

        try:
            self.digest_gen.maybe_send()
        except Exception as exc:
            logger.error("Error sending digest: %s", exc)

    def run(self):
        logger.info(
            "RustChain Email Notification Service started "
            "(poll=%ds, api=%s)", POLL_INTERVAL, RUSTCHAIN_API,
        )
        while True:
            try:
                self.run_once()
            except KeyboardInterrupt:
                logger.info("Shutting down.")
                break
            except Exception as exc:
                logger.error("Unhandled error in main loop: %s", exc)
            time.sleep(POLL_INTERVAL)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def cli():
    parser = argparse.ArgumentParser(
        description="RustChain Email Notification Service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s run                              Start the notification daemon
  %(prog)s subscribe -m MINER_ID -e a@b.com Subscribe to all alerts
  %(prog)s subscribe -m MINER_ID -e a@b.com --no-digest
  %(prog)s unsubscribe -m MINER_ID -e a@b.com
  %(prog)s test -e a@b.com                  Send a test email
        """,
    )
    sub = parser.add_subparsers(dest="command")

    # run
    sub.add_parser("run", help="Start the notification daemon")

    # subscribe
    sp_sub = sub.add_parser("subscribe", help="Add an email subscription")
    sp_sub.add_argument("-m", "--miner-id", required=True, help="Miner wallet address")
    sp_sub.add_argument("-e", "--email", required=True, help="Notification email address")
    sp_sub.add_argument("--no-balance", action="store_true", help="Disable balance alerts")
    sp_sub.add_argument("--no-epoch", action="store_true", help="Disable epoch alerts")
    sp_sub.add_argument("--no-attestation", action="store_true", help="Disable attestation alerts")
    sp_sub.add_argument("--no-digest", action="store_true", help="Disable daily digest")

    # unsubscribe
    sp_unsub = sub.add_parser("unsubscribe", help="Remove an email subscription")
    sp_unsub.add_argument("-m", "--miner-id", required=True)
    sp_unsub.add_argument("-e", "--email", required=True)

    # test
    sp_test = sub.add_parser("test", help="Send a test notification email")
    sp_test.add_argument("-e", "--email", required=True, help="Recipient email")

    args = parser.parse_args()

    if args.command == "run":
        svc = EmailNotificationService()
        svc.run()

    elif args.command == "subscribe":
        db = NotifierDB()
        sid = db.subscribe(
            miner_id=args.miner_id,
            email=args.email,
            notify_balance=not args.no_balance,
            notify_epoch=not args.no_epoch,
            notify_attestation=not args.no_attestation,
            notify_digest=not args.no_digest,
        )
        print(f"Subscribed (id={sid}): {args.email} -> {args.miner_id}")

    elif args.command == "unsubscribe":
        db = NotifierDB()
        db.unsubscribe(args.miner_id, args.email)
        print(f"Unsubscribed: {args.email} from {args.miner_id}")

    elif args.command == "test":
        mailer = Mailer()
        tpl = TemplateEngine()
        html = tpl.render(
            "balance_change",
            miner_id="TEST_MINER_0x1234567890abcdef",
            direction="increased",
            delta="5.0000",
            new_balance="105.0000",
            prev_balance="100.0000",
        )
        ok = mailer.send(args.email, "RustChain Email Notifier — Test", html)
        print("Test email sent successfully." if ok else "Failed to send test email.")

    else:
        parser.print_help()


if __name__ == "__main__":
    cli()
