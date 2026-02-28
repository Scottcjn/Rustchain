"""
RustChain Miner Alert System
Bounty: 75 RTC
Issue: #28

Monitors RustChain network and alerts miners via email (+ optional SMS via Twilio) when:
- Miner goes offline (no attestation within threshold)
- Rewards received (balance increase detected)
- Large transfers from wallet (balance decrease above threshold)
- Attestation failures (miner disappears from active list)

Architecture:
- Polling daemon that checks /api/miners and /balance endpoints periodically
- SQLite database for tracking miner state, alert history, and subscriptions
- SMTP email delivery (works with Gmail, SendGrid, any SMTP provider)
- Optional Twilio SMS integration
- CLI for managing subscriptions
"""

import argparse
import hashlib
import json
import logging
import os
import smtplib
import sqlite3
import sys
import time
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

# Load .env
load_dotenv()

# ─── Configuration ────────────────────────────────────────────────────────────

RUSTCHAIN_API = os.getenv("RUSTCHAIN_API", "https://rustchain.org")
VERIFY_SSL = os.getenv("RUSTCHAIN_VERIFY_SSL", "false").lower() == "true"

# Polling intervals (seconds)
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "120"))  # 2 minutes default
OFFLINE_THRESHOLD = int(os.getenv("OFFLINE_THRESHOLD", "600"))  # 10 min no attestation

# Large transfer threshold (RTC)
LARGE_TRANSFER_THRESHOLD = float(os.getenv("LARGE_TRANSFER_THRESHOLD", "10.0"))

# SMTP configuration
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"

# Optional: Twilio SMS
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM = os.getenv("TWILIO_FROM_NUMBER", "")

# Database
DB_PATH = os.getenv("ALERT_DB_PATH", str(Path.home() / ".rustchain" / "alerts.db"))

# Logging
logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("miner_alerts")


# ─── Database ─────────────────────────────────────────────────────────────────

class AlertDB:
    """SQLite database for subscriptions, miner state, and alert history."""

    def __init__(self, db_path: str = DB_PATH):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        cur = self.conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                miner_id TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                alert_offline INTEGER DEFAULT 1,
                alert_rewards INTEGER DEFAULT 1,
                alert_large_transfer INTEGER DEFAULT 1,
                alert_attestation_fail INTEGER DEFAULT 1,
                created_at INTEGER NOT NULL,
                active INTEGER DEFAULT 1,
                UNIQUE(miner_id, email)
            );

            CREATE TABLE IF NOT EXISTS miner_state (
                miner_id TEXT PRIMARY KEY,
                last_attest INTEGER,
                balance_rtc REAL DEFAULT 0,
                is_online INTEGER DEFAULT 1,
                last_checked INTEGER,
                last_balance_change REAL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS alert_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                miner_id TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                message TEXT NOT NULL,
                channel TEXT NOT NULL,
                recipient TEXT NOT NULL,
                sent_at INTEGER NOT NULL,
                success INTEGER DEFAULT 1
            );

            CREATE INDEX IF NOT EXISTS idx_sub_miner ON subscriptions(miner_id);
            CREATE INDEX IF NOT EXISTS idx_history_miner ON alert_history(miner_id, sent_at);
        """)
        self.conn.commit()

    def add_subscription(
        self,
        miner_id: str,
        email: str = None,
        phone: str = None,
        alerts: dict = None,
    ) -> int:
        """Add or update a subscription. Returns the subscription ID."""
        if not email and not phone:
            raise ValueError("At least one of email or phone is required")

        now = int(time.time())
        defaults = {
            "alert_offline": 1,
            "alert_rewards": 1,
            "alert_large_transfer": 1,
            "alert_attestation_fail": 1,
        }
        if alerts:
            defaults.update(alerts)

        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO subscriptions
                (miner_id, email, phone, alert_offline, alert_rewards,
                 alert_large_transfer, alert_attestation_fail, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(miner_id, email) DO UPDATE SET
                phone = excluded.phone,
                alert_offline = excluded.alert_offline,
                alert_rewards = excluded.alert_rewards,
                alert_large_transfer = excluded.alert_large_transfer,
                alert_attestation_fail = excluded.alert_attestation_fail,
                active = 1
        """, (
            miner_id, email, phone,
            defaults["alert_offline"],
            defaults["alert_rewards"],
            defaults["alert_large_transfer"],
            defaults["alert_attestation_fail"],
            now,
        ))
        self.conn.commit()
        return cur.lastrowid

    def get_subscriptions(self, miner_id: str, alert_type: str = None) -> List[dict]:
        """Get active subscriptions for a miner, optionally filtered by alert type."""
        cur = self.conn.cursor()
        if alert_type:
            col = f"alert_{alert_type}"
            cur.execute(
                f"SELECT * FROM subscriptions WHERE miner_id = ? AND active = 1 AND {col} = 1",
                (miner_id,),
            )
        else:
            cur.execute(
                "SELECT * FROM subscriptions WHERE miner_id = ? AND active = 1",
                (miner_id,),
            )
        return [dict(row) for row in cur.fetchall()]

    def list_subscriptions(self) -> List[dict]:
        """List all active subscriptions."""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM subscriptions WHERE active = 1")
        return [dict(row) for row in cur.fetchall()]

    def remove_subscription(self, miner_id: str, email: str) -> bool:
        """Deactivate a subscription."""
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE subscriptions SET active = 0 WHERE miner_id = ? AND email = ?",
            (miner_id, email),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def get_miner_state(self, miner_id: str) -> Optional[dict]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM miner_state WHERE miner_id = ?", (miner_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def update_miner_state(
        self,
        miner_id: str,
        last_attest: int = None,
        balance_rtc: float = None,
        is_online: int = None,
    ):
        now = int(time.time())
        cur = self.conn.cursor()

        existing = self.get_miner_state(miner_id)
        if existing is None:
            cur.execute("""
                INSERT INTO miner_state (miner_id, last_attest, balance_rtc, is_online, last_checked)
                VALUES (?, ?, ?, ?, ?)
            """, (miner_id, last_attest or 0, balance_rtc or 0, is_online or 1, now))
        else:
            updates = ["last_checked = ?"]
            params = [now]
            if last_attest is not None:
                updates.append("last_attest = ?")
                params.append(last_attest)
            if balance_rtc is not None:
                balance_change = balance_rtc - (existing["balance_rtc"] or 0)
                updates.append("balance_rtc = ?")
                params.append(balance_rtc)
                updates.append("last_balance_change = ?")
                params.append(balance_change)
            if is_online is not None:
                updates.append("is_online = ?")
                params.append(is_online)
            params.append(miner_id)
            cur.execute(
                f"UPDATE miner_state SET {', '.join(updates)} WHERE miner_id = ?",
                params,
            )
        self.conn.commit()

    def log_alert(
        self,
        miner_id: str,
        alert_type: str,
        message: str,
        channel: str,
        recipient: str,
        success: bool = True,
    ):
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO alert_history (miner_id, alert_type, message, channel, recipient, sent_at, success)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (miner_id, alert_type, message, channel, recipient, int(time.time()), int(success)))
        self.conn.commit()

    def recent_alert_exists(self, miner_id: str, alert_type: str, cooldown_s: int = 3600) -> bool:
        """Check if a similar alert was sent recently (avoid spam)."""
        cur = self.conn.cursor()
        since = int(time.time()) - cooldown_s
        cur.execute(
            "SELECT COUNT(*) FROM alert_history WHERE miner_id = ? AND alert_type = ? AND sent_at > ? AND success = 1",
            (miner_id, alert_type, since),
        )
        return cur.fetchone()[0] > 0

    def close(self):
        self.conn.close()


# ─── Notification Channels ────────────────────────────────────────────────────

def send_email(to_email: str, subject: str, body_html: str, body_text: str = None) -> bool:
    """Send an email via SMTP."""
    if not SMTP_USER or not SMTP_PASS:
        logger.warning("SMTP not configured, skipping email")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM or SMTP_USER
        msg["To"] = to_email

        if body_text:
            msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(body_html, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            if SMTP_USE_TLS:
                server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)

        logger.info(f"Email sent to {to_email}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


def send_sms(to_phone: str, message: str) -> bool:
    """Send an SMS via Twilio."""
    if not TWILIO_SID or not TWILIO_TOKEN or not TWILIO_FROM:
        logger.warning("Twilio not configured, skipping SMS")
        return False

    try:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json"
        resp = requests.post(
            url,
            data={
                "From": TWILIO_FROM,
                "To": to_phone,
                "Body": message,
            },
            auth=(TWILIO_SID, TWILIO_TOKEN),
            timeout=15,
        )
        resp.raise_for_status()
        logger.info(f"SMS sent to {to_phone}")
        return True
    except Exception as e:
        logger.error(f"Failed to send SMS to {to_phone}: {e}")
        return False


def send_alert(
    db: AlertDB,
    miner_id: str,
    alert_type: str,
    subject: str,
    body_html: str,
    body_text: str,
):
    """Send alert to all subscribers of this miner for the given alert type."""
    subs = db.get_subscriptions(miner_id, alert_type)
    if not subs:
        return

    for sub in subs:
        # Email
        if sub.get("email"):
            success = send_email(sub["email"], subject, body_html, body_text)
            db.log_alert(miner_id, alert_type, body_text, "email", sub["email"], success)

        # SMS
        if sub.get("phone"):
            sms_text = f"[RustChain] {body_text[:140]}"
            success = send_sms(sub["phone"], sms_text)
            db.log_alert(miner_id, alert_type, sms_text, "sms", sub["phone"], success)


# ─── Alert Templates ──────────────────────────────────────────────────────────

def _html_wrap(title: str, content: str) -> str:
    """Wrap content in a simple HTML email template."""
    return f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
      <div style="background: #1a1a2e; color: #eee; padding: 15px 20px; border-radius: 8px 8px 0 0;">
        <h2 style="margin: 0; color: #58a6ff;">RustChain Alert</h2>
      </div>
      <div style="background: #16213e; color: #ccc; padding: 20px; border-radius: 0 0 8px 8px;">
        <h3 style="color: #f0a500;">{title}</h3>
        {content}
        <hr style="border-color: #333; margin: 20px 0;">
        <p style="font-size: 12px; color: #666;">
          RustChain Miner Alert System |
          <a href="https://rustchain.org" style="color: #58a6ff;">rustchain.org</a>
        </p>
      </div>
    </div>
    """


def alert_offline(db: AlertDB, miner_id: str, last_attest: int):
    """Alert: miner went offline."""
    if db.recent_alert_exists(miner_id, "offline"):
        return

    dt = datetime.fromtimestamp(last_attest, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    minutes_ago = (int(time.time()) - last_attest) // 60

    text = f"Miner {miner_id} appears OFFLINE. Last attestation: {dt} ({minutes_ago} min ago)."
    html = _html_wrap(
        "Miner Offline",
        f"<p>Your miner <code>{miner_id}</code> has not submitted an attestation "
        f"in <strong>{minutes_ago} minutes</strong>.</p>"
        f"<p>Last attestation: {dt}</p>"
        f"<p>Please check your mining hardware and network connection.</p>",
    )
    send_alert(db, miner_id, "offline", f"[RustChain] Miner Offline: {miner_id}", html, text)


def alert_back_online(db: AlertDB, miner_id: str):
    """Alert: miner came back online."""
    text = f"Miner {miner_id} is back ONLINE."
    html = _html_wrap(
        "Miner Back Online",
        f"<p>Your miner <code>{miner_id}</code> is back online and attesting normally.</p>",
    )
    send_alert(db, miner_id, "offline", f"[RustChain] Miner Online: {miner_id}", html, text)


def alert_rewards(db: AlertDB, miner_id: str, amount: float, new_balance: float):
    """Alert: rewards received."""
    if db.recent_alert_exists(miner_id, "rewards", cooldown_s=300):
        return

    text = f"Miner {miner_id} received {amount:.4f} RTC. New balance: {new_balance:.4f} RTC."
    html = _html_wrap(
        "Rewards Received",
        f"<p>Your miner <code>{miner_id}</code> received:</p>"
        f"<p style='font-size: 24px; color: #3fb950;'><strong>+{amount:.4f} RTC</strong></p>"
        f"<p>New balance: <strong>{new_balance:.4f} RTC</strong></p>",
    )
    send_alert(db, miner_id, "rewards", f"[RustChain] +{amount:.4f} RTC Received", html, text)


def alert_large_transfer(db: AlertDB, miner_id: str, amount: float, new_balance: float):
    """Alert: large outgoing transfer."""
    if db.recent_alert_exists(miner_id, "large_transfer"):
        return

    text = f"Large transfer from {miner_id}: {abs(amount):.4f} RTC. Remaining: {new_balance:.4f} RTC."
    html = _html_wrap(
        "Large Transfer Detected",
        f"<p>A large transfer was detected from your wallet <code>{miner_id}</code>:</p>"
        f"<p style='font-size: 24px; color: #f85149;'><strong>-{abs(amount):.4f} RTC</strong></p>"
        f"<p>Remaining balance: <strong>{new_balance:.4f} RTC</strong></p>"
        f"<p>If you did not authorize this transfer, investigate immediately.</p>",
    )
    send_alert(
        db, miner_id, "large_transfer",
        f"[RustChain] Large Transfer: -{abs(amount):.4f} RTC", html, text,
    )


def alert_attestation_fail(db: AlertDB, miner_id: str, reason: str):
    """Alert: attestation failure (miner dropped from list)."""
    if db.recent_alert_exists(miner_id, "attestation_fail"):
        return

    text = f"Attestation issue for {miner_id}: {reason}"
    html = _html_wrap(
        "Attestation Failure",
        f"<p>An attestation issue was detected for miner <code>{miner_id}</code>:</p>"
        f"<p><strong>{reason}</strong></p>"
        f"<p>Your miner may need to re-enroll or the hardware may need attention.</p>",
    )
    send_alert(
        db, miner_id, "attestation_fail",
        f"[RustChain] Attestation Issue: {miner_id}", html, text,
    )


# ─── API Helpers ──────────────────────────────────────────────────────────────

def fetch_miners() -> List[dict]:
    """Fetch all active miners from the node."""
    try:
        resp = requests.get(
            f"{RUSTCHAIN_API}/api/miners",
            verify=VERIFY_SSL,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"Failed to fetch miners: {e}")
        return []


def fetch_balance(miner_id: str) -> Optional[float]:
    """Fetch balance for a miner."""
    try:
        resp = requests.get(
            f"{RUSTCHAIN_API}/balance",
            params={"miner_id": miner_id},
            verify=VERIFY_SSL,
            timeout=10,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        return float(data.get("balance", data.get("balance_rtc", 0)))
    except Exception as e:
        logger.error(f"Failed to fetch balance for {miner_id}: {e}")
        return None


# ─── Monitor Loop ─────────────────────────────────────────────────────────────

def monitor_loop(db: AlertDB):
    """Main monitoring loop. Runs indefinitely."""
    logger.info(f"Starting monitor loop (interval: {POLL_INTERVAL}s, offline threshold: {OFFLINE_THRESHOLD}s)")

    # Get all subscribed miner IDs
    subscriptions = db.list_subscriptions()
    monitored_miners = set(sub["miner_id"] for sub in subscriptions)

    if not monitored_miners:
        logger.warning("No subscriptions found. Add miners with: python miner_alerts.py subscribe <miner_id> <email>")
        return

    logger.info(f"Monitoring {len(monitored_miners)} miners: {', '.join(monitored_miners)}")

    while True:
        try:
            now = int(time.time())

            # Refresh subscriptions periodically
            subscriptions = db.list_subscriptions()
            monitored_miners = set(sub["miner_id"] for sub in subscriptions)

            # Fetch current miner data
            all_miners = fetch_miners()
            active_miner_ids = set(m["miner"] for m in all_miners)
            miner_data = {m["miner"]: m for m in all_miners}

            for miner_id in monitored_miners:
                prev_state = db.get_miner_state(miner_id)

                # Check if miner is in active list
                if miner_id in active_miner_ids:
                    miner = miner_data[miner_id]
                    last_attest = miner.get("last_attest", 0) or 0

                    # Check offline status
                    if last_attest > 0:
                        age = now - last_attest
                        is_online = age < OFFLINE_THRESHOLD

                        if not is_online and (prev_state is None or prev_state["is_online"]):
                            alert_offline(db, miner_id, last_attest)

                        if is_online and prev_state and not prev_state["is_online"]:
                            alert_back_online(db, miner_id)

                        db.update_miner_state(miner_id, last_attest=last_attest, is_online=int(is_online))

                    # Check balance changes
                    balance = fetch_balance(miner_id)
                    if balance is not None and prev_state and prev_state.get("balance_rtc") is not None:
                        old_balance = prev_state["balance_rtc"]
                        change = balance - old_balance

                        if change > 0.0001:
                            # Rewards or incoming transfer
                            alert_rewards(db, miner_id, change, balance)

                        elif change < -LARGE_TRANSFER_THRESHOLD:
                            # Large outgoing transfer
                            alert_large_transfer(db, miner_id, change, balance)

                    if balance is not None:
                        db.update_miner_state(miner_id, balance_rtc=balance)

                else:
                    # Miner not in active list
                    if prev_state and prev_state["is_online"]:
                        alert_attestation_fail(
                            db, miner_id,
                            "Miner no longer appears in the active miners list. "
                            "It may have been dropped due to missed attestations.",
                        )
                        db.update_miner_state(miner_id, is_online=0)

            logger.debug(f"Poll complete. Sleeping {POLL_INTERVAL}s...")

        except KeyboardInterrupt:
            logger.info("Shutting down...")
            break
        except Exception as e:
            logger.error(f"Error in monitor loop: {e}", exc_info=True)

        time.sleep(POLL_INTERVAL)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def cli():
    parser = argparse.ArgumentParser(
        description="RustChain Miner Alert System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Subscribe to alerts for a miner
  python miner_alerts.py subscribe modern-sophia-Pow-9862e3be user@example.com

  # Subscribe with SMS
  python miner_alerts.py subscribe modern-sophia-Pow-9862e3be user@example.com --phone +15551234567

  # List subscriptions
  python miner_alerts.py list

  # Unsubscribe
  python miner_alerts.py unsubscribe modern-sophia-Pow-9862e3be user@example.com

  # Start the monitor daemon
  python miner_alerts.py monitor

  # Test email delivery
  python miner_alerts.py test-email user@example.com
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command")

    # subscribe
    sub_parser = subparsers.add_parser("subscribe", help="Subscribe to miner alerts")
    sub_parser.add_argument("miner_id", help="Miner ID to monitor")
    sub_parser.add_argument("email", help="Email address for alerts")
    sub_parser.add_argument("--phone", help="Phone number for SMS alerts (optional)")
    sub_parser.add_argument("--no-offline", action="store_true", help="Disable offline alerts")
    sub_parser.add_argument("--no-rewards", action="store_true", help="Disable reward alerts")
    sub_parser.add_argument("--no-transfer", action="store_true", help="Disable large transfer alerts")
    sub_parser.add_argument("--no-attestation", action="store_true", help="Disable attestation failure alerts")

    # unsubscribe
    unsub_parser = subparsers.add_parser("unsubscribe", help="Unsubscribe from alerts")
    unsub_parser.add_argument("miner_id", help="Miner ID")
    unsub_parser.add_argument("email", help="Email to unsubscribe")

    # list
    subparsers.add_parser("list", help="List all active subscriptions")

    # monitor
    subparsers.add_parser("monitor", help="Start the monitoring daemon")

    # test-email
    test_parser = subparsers.add_parser("test-email", help="Send a test email")
    test_parser.add_argument("email", help="Email address to test")

    # test-sms
    sms_parser = subparsers.add_parser("test-sms", help="Send a test SMS")
    sms_parser.add_argument("phone", help="Phone number to test")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    db = AlertDB()

    try:
        if args.command == "subscribe":
            alerts = {
                "alert_offline": 0 if args.no_offline else 1,
                "alert_rewards": 0 if args.no_rewards else 1,
                "alert_large_transfer": 0 if args.no_transfer else 1,
                "alert_attestation_fail": 0 if args.no_attestation else 1,
            }
            sub_id = db.add_subscription(
                miner_id=args.miner_id,
                email=args.email,
                phone=args.phone,
                alerts=alerts,
            )
            print(f"Subscribed! ID: {sub_id}")
            print(f"  Miner: {args.miner_id}")
            print(f"  Email: {args.email}")
            if args.phone:
                print(f"  Phone: {args.phone}")
            enabled = [k.replace("alert_", "") for k, v in alerts.items() if v]
            print(f"  Alerts: {', '.join(enabled)}")

        elif args.command == "unsubscribe":
            if db.remove_subscription(args.miner_id, args.email):
                print(f"Unsubscribed {args.email} from {args.miner_id}")
            else:
                print("Subscription not found")

        elif args.command == "list":
            subs = db.list_subscriptions()
            if not subs:
                print("No active subscriptions.")
                return
            print(f"{'Miner ID':<40} {'Email':<30} {'Phone':<15} {'Alerts'}")
            print("-" * 100)
            for s in subs:
                alerts = []
                if s["alert_offline"]:
                    alerts.append("offline")
                if s["alert_rewards"]:
                    alerts.append("rewards")
                if s["alert_large_transfer"]:
                    alerts.append("transfer")
                if s["alert_attestation_fail"]:
                    alerts.append("attest")
                print(
                    f"{s['miner_id']:<40} {s.get('email',''):<30} "
                    f"{s.get('phone','') or '':<15} {', '.join(alerts)}"
                )

        elif args.command == "monitor":
            monitor_loop(db)

        elif args.command == "test-email":
            html = _html_wrap(
                "Test Alert",
                "<p>This is a test alert from the RustChain Miner Alert System.</p>"
                "<p>If you received this, email delivery is working correctly.</p>",
            )
            ok = send_email(args.email, "[RustChain] Test Alert", html, "Test alert from RustChain.")
            print("Email sent!" if ok else "Failed to send email. Check SMTP settings.")

        elif args.command == "test-sms":
            ok = send_sms(args.phone, "[RustChain] Test alert. SMS delivery is working.")
            print("SMS sent!" if ok else "Failed to send SMS. Check Twilio settings.")

    finally:
        db.close()


if __name__ == "__main__":
    cli()
