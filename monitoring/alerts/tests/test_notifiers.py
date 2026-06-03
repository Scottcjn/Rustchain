"""Tests for alert notification backends."""

from unittest.mock import Mock

from rustchain_alerts.notifiers import EmailNotifier, NullNotifier, SmsNotifier


def test_null_notifier_always_reports_success():
    notifier = NullNotifier()

    assert notifier.send("subject") is True
    assert notifier.send("subject", "body") is True


def test_email_notifier_returns_false_without_recipients():
    notifier = EmailNotifier(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="",
        smtp_password="",
        from_addr="alerts@example.com",
        to_addrs=[],
    )

    assert notifier.send("Alert", "body") is False


def test_email_notifier_sends_plain_text_message_with_tls_and_login(monkeypatch):
    smtp = Mock()
    smtp_context = Mock()
    smtp_context.__enter__ = Mock(return_value=smtp)
    smtp_context.__exit__ = Mock(return_value=None)
    smtp_factory = Mock(return_value=smtp_context)
    monkeypatch.setattr("rustchain_alerts.notifiers.smtplib.SMTP", smtp_factory)

    notifier = EmailNotifier(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="bot",
        smtp_password="secret",
        from_addr="alerts@example.com",
        to_addrs=["ops@example.com", "admin@example.com"],
        use_tls=True,
    )

    assert notifier.send("Node down", "Check node-1") is True

    smtp_factory.assert_called_once_with("smtp.example.com", 587)
    smtp.starttls.assert_called_once_with()
    smtp.login.assert_called_once_with("bot", "secret")
    smtp.sendmail.assert_called_once()
    from_addr, recipients, message = smtp.sendmail.call_args.args
    assert from_addr == "alerts@example.com"
    assert recipients == ["ops@example.com", "admin@example.com"]
    assert "Subject: Node down" in message
    assert "Check node-1" in message


def test_sms_notifier_returns_false_without_recipients():
    notifier = SmsNotifier(
        account_sid="ACtest",
        auth_token="token",
        from_number="+15550000000",
        to_numbers=[],
    )

    assert notifier.send("Alert body") is False
