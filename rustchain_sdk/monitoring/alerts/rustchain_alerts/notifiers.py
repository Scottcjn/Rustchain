"""Notification backends: email (SMTP) and SMS (Twilio)."""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


class EmailNotifier:
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        from_addr: str,
        to_addrs: list[str],
        use_tls: bool = True,
    ) -> None:
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_addr = from_addr
        self.to_addrs = to_addrs
        self.use_tls = use_tls

    def send(self, subject: str, body: str) -> bool:
        if not self.to_addrs:
            logger.warning("Email: no recipients configured")
            return False
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_addr
            msg["To"] = ", ".join(self.to_addrs)
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.from_addr, self.to_addrs, msg.as_string())

            logger.info("Email sent: %s → %s", subject, self.to_addrs)
            return True
        except Exception as exc:
            logger.error("Email send failed: %s", exc)
            return False


class SmsNotifier:
    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str,
        to_numbers: list[str],
    ) -> None:
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self.to_numbers = to_numbers
        self._client = None

    def _get_client(self):  # type: ignore[return]
        if self._client is None:
            try:
                from twilio.rest import Client  # type: ignore[import]
                self._client = Client(self.account_sid, self.auth_token)
            except ImportError:
                logger.error("twilio package not installed. Run: pip install twilio")
                raise
        return self._client

    def send(self, body: str) -> bool:
        if not self.to_numbers:
            logger.warning("SMS: no recipients configured")
            return False
        try:
            client = self._get_client()
            for number in self.to_numbers:
                client.messages.create(
                    body=body,
                    from_=self.from_number,
                    to=number,
                )
                logger.info("SMS sent to %s", number)
            return True
        except Exception as exc:
            logger.error("SMS send failed: %s", exc)
            return False


class NullNotifier:
    """No-op notifier used when a channel is disabled."""

    def send(self, subject_or_body: str, body: str = "") -> bool:
        return True
