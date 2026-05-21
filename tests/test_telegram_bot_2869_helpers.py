# SPDX-License-Identifier: MIT
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "telegram-bot-2869" / "bot.py"


class DummyApplication:
    @staticmethod
    def builder():
        return DummyApplication()

    def token(self, *_args, **_kwargs):
        return self

    def post_init(self, *_args, **_kwargs):
        return self

    def build(self):
        return self

    def add_handler(self, *_args, **_kwargs):
        return None

    def run_polling(self):
        return None


sys.modules.setdefault(
    "telegram",
    SimpleNamespace(BotCommand=object, Update=object),
)
sys.modules.setdefault(
    "telegram.ext",
    SimpleNamespace(
        Application=DummyApplication,
        CommandHandler=lambda *args, **kwargs: (args, kwargs),
        ContextTypes=SimpleNamespace(DEFAULT_TYPE=object),
    ),
)
sys.modules.setdefault(
    "httpx",
    SimpleNamespace(
        AsyncClient=lambda *args, **kwargs: SimpleNamespace(aclose=lambda: None),
        Timeout=lambda *args, **kwargs: None,
        ConnectError=Exception,
        TimeoutException=Exception,
        HTTPStatusError=Exception,
    ),
)

spec = importlib.util.spec_from_file_location("telegram_bot_2869", MODULE_PATH)
telegram_bot = importlib.util.module_from_spec(spec)
sys.modules["telegram_bot_2869"] = telegram_bot
spec.loader.exec_module(telegram_bot)


def test_rate_limiter_allows_first_hit_blocks_second_and_reports_retry(monkeypatch):
    times = iter([100.0, 101.5, 101.5])
    monkeypatch.setattr(telegram_bot.time, "monotonic", lambda: next(times))
    limiter = telegram_bot.RateLimiter(window=5)

    assert limiter.is_allowed(42) is True
    assert limiter.is_allowed(42) is False
    assert limiter.retry_after(42) == 3.5


def test_rate_limiter_allows_after_window(monkeypatch):
    times = iter([100.0, 106.0])
    monkeypatch.setattr(telegram_bot.time, "monotonic", lambda: next(times))
    limiter = telegram_bot.RateLimiter(window=5)

    assert limiter.is_allowed(7) is True
    assert limiter.is_allowed(7) is True


def test_format_uptime_breaks_seconds_into_days_hours_minutes():
    assert telegram_bot._fmt_uptime(0) == "0d 0h 0m"
    assert telegram_bot._fmt_uptime(3661) == "0d 1h 1m"
    assert telegram_bot._fmt_uptime(90061) == "1d 1h 1m"


def test_error_text_prefers_internal_error_then_api_error():
    assert telegram_bot._error_text({"_error": "node down", "error": "ignored"}) == "node down"
    assert telegram_bot._error_text({"error": "bad wallet"}) == "bad wallet"
    assert telegram_bot._error_text({"ok": True}) == ""


def test_price_command_handles_null_epoch_supply(monkeypatch):
    class FakeApi:
        async def swap_info(self):
            return {"reference_price_usd": 0.25}

        async def epoch(self):
            return {"total_supply_rtc": None}

    class FakeDxClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def get(self, *_args, **_kwargs):
            return SimpleNamespace(status_code=503, json=lambda: {})

    class FakeMessage:
        def __init__(self):
            self.replies = []

        async def reply_text(self, text, **kwargs):
            self.replies.append((text, kwargs))

    message = FakeMessage()
    update = SimpleNamespace(effective_user=SimpleNamespace(id=99), message=message)
    ctx = SimpleNamespace()

    monkeypatch.setattr(telegram_bot, "api", FakeApi())
    monkeypatch.setattr(telegram_bot.rate_limiter, "is_allowed", lambda user_id: True)
    monkeypatch.setattr(telegram_bot.httpx, "AsyncClient", lambda *args, **kwargs: FakeDxClient())

    import asyncio

    asyncio.run(telegram_bot.cmd_price(update, ctx))

    assert message.replies
    assert "Total Supply: `N/A RTC`" in message.replies[0][0]
    assert "Market Cap: `$0.00`" in message.replies[0][0]
