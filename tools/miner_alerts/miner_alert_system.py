#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Author: @xiangshangsir (大龙虾 AI)
# BCOS-Tier: L1
# Bounty: #28 - Email/SMS Alert System for Miners (75 RTC)
"""
RustChain Miner Alert System
=============================

Sends alerts to miners when:
- Miner goes offline (no attestation for >1 hour)
- Rewards received
- Large transfers from wallet
- Attestation failures

Supports:
- Email (SMTP)
- SMS (Twilio)
- Configurable thresholds
"""

import json
import logging
import os
import smtplib
import sqlite3
import time
from dataclasses import dataclass, field
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional, Set
from datetime import datetime

# Try to import Twilio (optional dependency)
try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False

# Configuration
DB_PATH = os.environ.get("RUSTCHAIN_DB", "/root/rustchain/rustchain_v2.db")
CONFIG_PATH = os.environ.get("ALERT_CONFIG", "alert_config.json")
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "300"))  # 5 minutes
LARGE_TRANSFER_THRESHOLD = float(os.environ.get("LARGE_TRANSFER_THRESHOLD", "100"))  # RTC
OFFLINE_THRESHOLD_SECONDS = int(os.environ.get("OFFLINE_THRESHOLD", "3600"))  # 1 hour

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [ALERT] %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class AlertConfig:
    """Alert configuration for a miner"""
    miner_id: str
    email: Optional[str] = None
    phone: Optional[str] = None
    alert_types: Set[str] = field(default_factory=lambda: {
        'offline', 'reward', 'large_transfer', 'attestation_failure'
    })
    enabled: bool = True


@dataclass
class AlertEvent:
    """Represents an alert event"""
    miner_id: str
    alert_type: str  # offline, reward, large_transfer, attestation_failure
    message: str
    timestamp: int
    details: Dict = field(default_factory=dict)


class AlertDatabase:
    """Manages alert preferences and history in SQLite"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_tables()
    
    def _init_tables(self):
        """Create alert tables if not exist"""
        with sqlite3.connect(self.db_path) as conn:
            # Alert preferences
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alert_preferences (
                    miner_id TEXT PRIMARY KEY,
                    email TEXT,
                    phone TEXT,
                    alert_types TEXT,  -- JSON array
                    enabled INTEGER DEFAULT 1,
                    created_at INTEGER NOT NULL
                )
            """)
            
            # Alert history
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alert_history (
                    id INTEGER PRIMARY KEY,
                    miner_id TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    sent_at INTEGER NOT NULL,
                    channel TEXT,  -- email, sms
                    status TEXT,  -- sent, failed
                    error TEXT
                )
            """)
            
            # Alert rate limiting (prevent spam)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alert_rate_limit (
                    miner_id TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    last_sent INTEGER NOT NULL,
                    count_24h INTEGER DEFAULT 1,
                    PRIMARY KEY (miner_id, alert_type)
                )
            """)
            
            conn.commit()
    
    def get_miner_preferences(self, miner_id: str) -> Optional[AlertConfig]:
        """Get alert preferences for a miner"""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM alert_preferences WHERE miner_id = ?",
                (miner_id,)
            ).fetchone()
            
            if not row:
                return None
            
            return AlertConfig(
                miner_id=row[0],
                email=row[1],
                phone=row[2],
                alert_types=set(json.loads(row[3] or '[]')),
                enabled=bool(row[4]),
            )
    
    def get_all_preferences(self) -> List[AlertConfig]:
        """Get all miner alert preferences"""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM alert_preferences WHERE enabled = 1"
            ).fetchall()
            
            configs = []
            for row in rows:
                configs.append(AlertConfig(
                    miner_id=row[0],
                    email=row[1],
                    phone=row[2],
                    alert_types=set(json.loads(row[3] or '[]')),
                    enabled=bool(row[4]),
                ))
            return configs
    
    def save_preferences(self, config: AlertConfig):
        """Save alert preferences for a miner"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO alert_preferences 
                (miner_id, email, phone, alert_types, enabled, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                config.miner_id,
                config.email,
                config.phone,
                json.dumps(list(config.alert_types)),
                1 if config.enabled else 0,
                int(time.time())
            ))
            conn.commit()
    
    def record_alert(self, miner_id: str, alert_type: str, message: str,
                     channel: str, status: str, error: str = None):
        """Record alert in history"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO alert_history 
                (miner_id, alert_type, message, sent_at, channel, status, error)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                miner_id, alert_type, message, int(time.time()),
                channel, status, error
            ))
            conn.commit()
    
    def check_rate_limit(self, miner_id: str, alert_type: str, 
                         max_per_24h: int = 10) -> bool:
        """Check if alert should be rate limited. Returns True if allowed."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("""
                SELECT last_sent, count_24h FROM alert_rate_limit
                WHERE miner_id = ? AND alert_type = ?
            """, (miner_id, alert_type)).fetchone()
            
            now = int(time.time())
            day_ago = now - 86400
            
            if not row:
                # First alert of this type
                conn.execute("""
                    INSERT INTO alert_rate_limit 
                    (miner_id, alert_type, last_sent, count_24h)
                    VALUES (?, ?, ?, 1)
                """, (miner_id, alert_type, now))
                conn.commit()
                return True
            
            last_sent, count = row[1], row[2]
            
            # Reset counter if new day
            if last_sent < day_ago:
                conn.execute("""
                    UPDATE alert_rate_limit 
                    SET last_sent = ?, count_24h = 1
                    WHERE miner_id = ? AND alert_type = ?
                """, (now, miner_id, alert_type))
                conn.commit()
                return True
            
            # Check limit
            if count >= max_per_24h:
                logger.warning(f"Rate limit exceeded for {miner_id} {alert_type}")
                return False
            
            # Increment counter
            conn.execute("""
                UPDATE alert_rate_limit 
                SET last_sent = ?, count_24h = count_24h + 1
                WHERE miner_id = ? AND alert_type = ?
            """, (now, miner_id, alert_type))
            conn.commit()
            return True


class EmailSender:
    """Send alerts via email (SMTP)"""
    
    def __init__(self, smtp_host: str, smtp_port: int, 
                 username: str, password: str, from_email: str):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_email = from_email
    
    def send(self, to_email: str, subject: str, body: str, 
             html: bool = False) -> tuple[bool, Optional[str]]:
        """Send email. Returns (success, error_message)"""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = to_email
            
            content_type = 'html' if html else 'plain'
            msg.attach(MIMEText(body, content_type))
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.sendmail(self.from_email, [to_email], msg.as_string())
            
            logger.info(f"Email sent to {to_email}: {subject}")
            return True, None
        except Exception as e:
            logger.error(f"Email failed to {to_email}: {e}")
            return False, str(e)


class SMSSender:
    """Send alerts via SMS (Twilio)"""
    
    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        if not TWILIO_AVAILABLE:
            raise ImportError("Twilio library not installed. Run: pip install twilio")
        
        self.client = TwilioClient(account_sid, auth_token)
        self.from_number = from_number
    
    def send(self, to_number: str, body: str) -> tuple[bool, Optional[str]]:
        """Send SMS. Returns (success, error_message)"""
        try:
            message = self.client.messages.create(
                body=body,
                from_=self.from_number,
                to=to_number
            )
            logger.info(f"SMS sent to {to_number}: {message.sid}")
            return True, None
        except Exception as e:
            logger.error(f"SMS failed to {to_number}: {e}")
            return False, str(e)


class MinerAlertSystem:
    """Main alert system orchestrator"""
    
    def __init__(self, db_path: str, config_path: str):
        self.db_path = db_path
        self.config_path = config_path
        self.alert_db = AlertDatabase(db_path)
        self.email_sender = None
        self.sms_sender = None
        self._load_config()
    
    def _load_config(self):
        """Load alert system configuration"""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            # Email config
            if 'email' in config:
                email_cfg = config['email']
                self.email_sender = EmailSender(
                    smtp_host=email_cfg.get('smtp_host', 'smtp.gmail.com'),
                    smtp_port=email_cfg.get('smtp_port', 587),
                    username=email_cfg.get('username'),
                    password=email_cfg.get('password'),
                    from_email=email_cfg.get('from_email')
                )
                logger.info("Email sender configured")
            
            # SMS config
            if 'sms' in config and TWILIO_AVAILABLE:
                sms_cfg = config['sms']
                self.sms_sender = SMSSender(
                    account_sid=sms_cfg.get('account_sid'),
                    auth_token=sms_cfg.get('auth_token'),
                    from_number=sms_cfg.get('from_number')
                )
                logger.info("SMS sender configured")
        except FileNotFoundError:
            logger.warning(f"Config file not found: {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
    
    def check_offline_miners(self) -> List[AlertEvent]:
        """Check for miners that went offline"""
        alerts = []
        now = int(time.time())
        
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT miner, last_attest FROM miner_attest_recent
                WHERE last_attest < ?
            """, (now - OFFLINE_THRESHOLD_SECONDS,)).fetchall()
        
        for miner_id, last_attest in rows:
            config = self.alert_db.get_miner_preferences(miner_id)
            if not config or not config.enabled:
                continue
            
            if 'offline' not in config.alert_types:
                continue
            
            if not self.alert_db.check_rate_limit(miner_id, 'offline'):
                continue
            
            hours_offline = (now - last_attest) / 3600
            message = f"⚠️ Miner {miner_id} has been offline for {hours_offline:.1f} hours"
            
            alerts.append(AlertEvent(
                miner_id=miner_id,
                alert_type='offline',
                message=message,
                timestamp=now,
                details={'last_attest': last_attest, 'hours_offline': hours_offline}
            ))
        
        return alerts
    
    def check_new_rewards(self, since_timestamp: int) -> List[AlertEvent]:
        """Check for new rewards received"""
        alerts = []
        
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT miner_id, amount_rtc, epoch FROM epoch_rewards
                WHERE created_at > ?
            """, (since_timestamp,)).fetchall()
        
        for miner_id, amount, epoch in rows:
            config = self.alert_db.get_miner_preferences(miner_id)
            if not config or not config.enabled:
                continue
            
            if 'reward' not in config.alert_types:
                continue
            
            if not self.alert_db.check_rate_limit(miner_id, 'reward'):
                continue
            
            message = f"💰 Reward received: {amount:.2f} RTC (Epoch {epoch})"
            
            alerts.append(AlertEvent(
                miner_id=miner_id,
                alert_type='reward',
                message=message,
                timestamp=int(time.time()),
                details={'amount': amount, 'epoch': epoch}
            ))
        
        return alerts
    
    def check_large_transfers(self, since_timestamp: int) -> List[AlertEvent]:
        """Check for large transfers from wallets"""
        alerts = []
        
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT from_miner, amount_rtc, tx_hash FROM ledger
                WHERE created_at > ? AND amount_rtc > ?
            """, (since_timestamp, LARGE_TRANSFER_THRESHOLD)).fetchall()
        
        for miner_id, amount, tx_hash in rows:
            config = self.alert_db.get_miner_preferences(miner_id)
            if not config or not config.enabled:
                continue
            
            if 'large_transfer' not in config.alert_types:
                continue
            
            if not self.alert_db.check_rate_limit(miner_id, 'large_transfer'):
                continue
            
            message = f"🚨 Large transfer: {amount:.2f} RTC (TX: {tx_hash[:16]}...)"
            
            alerts.append(AlertEvent(
                miner_id=miner_id,
                alert_type='large_transfer',
                message=message,
                timestamp=int(time.time()),
                details={'amount': amount, 'tx_hash': tx_hash}
            ))
        
        return alerts
    
    def check_attestation_failures(self, since_timestamp: int) -> List[AlertEvent]:
        """Check for attestation failures"""
        alerts = []
        
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT miner_id, error_reason, failed_at FROM attestation_failures
                WHERE created_at > ?
            """, (since_timestamp,)).fetchall()
        
        for miner_id, error, failed_at in rows:
            config = self.alert_db.get_miner_preferences(miner_id)
            if not config or not config.enabled:
                continue
            
            if 'attestation_failure' not in config.alert_types:
                continue
            
            if not self.alert_db.check_rate_limit(miner_id, 'attestation_failure'):
                continue
            
            message = f"❌ Attestation failed: {error}"
            
            alerts.append(AlertEvent(
                miner_id=miner_id,
                alert_type='attestation_failure',
                message=message,
                timestamp=int(time.time()),
                details={'error': error, 'failed_at': failed_at}
            ))
        
        return alerts
    
    def send_alert(self, alert: AlertEvent, config: AlertConfig):
        """Send alert via configured channels"""
        subject = f"RustChain Alert: {alert.alert_type.replace('_', ' ').title()}"
        
        # Send email
        if config.email and self.email_sender:
            success, error = self.email_sender.send(
                to_email=config.email,
                subject=subject,
                body=alert.message,
                html=False
            )
            self.alert_db.record_alert(
                alert.miner_id, alert.alert_type, alert.message,
                'email', 'sent' if success else 'failed', error
            )
        
        # Send SMS (for critical alerts only)
        if config.phone and self.sms_sender:
            if alert.alert_type in ('offline', 'large_transfer'):
                success, error = self.sms_sender.send(
                    to_number=config.phone,
                    body=f"RustChain: {alert.message}"
                )
                self.alert_db.record_alert(
                    alert.miner_id, alert.alert_type, alert.message,
                    'sms', 'sent' if success else 'failed', error
                )
    
    def run_check_cycle(self, last_check_time: int) -> int:
        """Run one check cycle. Returns new timestamp."""
        logger.info(f"Running alert check cycle (since {last_check_time})")
        
        now = int(time.time())
        alerts_found = 0
        
        # Check all alert types
        alert_checks = [
            ('offline', self.check_offline_miners),
            ('reward', lambda: self.check_new_rewards(last_check_time)),
            ('large_transfer', lambda: self.check_large_transfers(last_check_time)),
            ('attestation_failure', lambda: self.check_attestation_failures(last_check_time)),
        ]
        
        for alert_type, check_func in alert_checks:
            try:
                alerts = check_func()
                for alert in alerts:
                    config = self.alert_db.get_miner_preferences(alert.miner_id)
                    if config:
                        self.send_alert(alert, config)
                        alerts_found += 1
                        logger.info(f"Alert sent: {alert.miner_id} - {alert.alert_type}")
            except Exception as e:
                logger.error(f"Failed to check {alert_type}: {e}")
        
        logger.info(f"Check cycle complete. {alerts_found} alerts sent.")
        return now
    
    def run_continuous(self):
        """Run continuous alert monitoring"""
        logger.info("=" * 50)
        logger.info("RustChain Miner Alert System Starting")
        logger.info(f"DB Path: {self.db_path}")
        logger.info(f"Check Interval: {CHECK_INTERVAL}s")
        logger.info(f"Offline Threshold: {OFFLINE_THRESHOLD_SECONDS}s")
        logger.info(f"Large Transfer Threshold: {LARGE_TRANSFER_THRESHOLD} RTC")
        logger.info("=" * 50)
        
        last_check = int(time.time()) - CHECK_INTERVAL
        
        while True:
            try:
                last_check = self.run_check_cycle(last_check)
            except Exception as e:
                logger.error(f"Check cycle failed: {e}")
            
            time.sleep(CHECK_INTERVAL)


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='RustChain Miner Alert System')
    parser.add_argument('--config', default=CONFIG_PATH, help='Config file path')
    parser.add_argument('--db', default=DB_PATH, help='Database path')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    args = parser.parse_args()
    
    alert_system = MinerAlertSystem(args.db, args.config)
    
    if args.once:
        alert_system.run_check_cycle(int(time.time()) - CHECK_INTERVAL)
    else:
        alert_system.run_continuous()


if __name__ == "__main__":
    main()
