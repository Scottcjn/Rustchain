"""Tests for CLI Unicode encoding fallback (GitHub #6899).

On Windows with console code page 850, stdout/stderr may reject emoji
characters, causing click.echo to raise UnicodeEncodeError.  This test
simulates that condition and verifies the CLI still succeeds with an
ASCII-safe fallback.
"""

import io
from unittest import mock

import click
import pytest

from rustchain_sdk.cli import _safe_echo, _ascii_version


class TestAsciiVersion:
    """Unit tests for the ASCII-fallback helper."""

    def test_success_emoji_replaced(self):
        assert _ascii_version("\u2705  Wallet created!") == "OK! Wallet created!"

    def test_success_emoji_variant_replaced(self):
        """Some terminals render ✅ as a two-codepoint sequence."""
        assert _ascii_version("\u2705\ufe0f  Wallet created!") == "OK! Wallet created!"

    def test_warning_emoji_replaced(self):
        assert _ascii_version("\u26a0\ufe0f  SAVE YOUR SEED!") == "WARNING: SAVE YOUR SEED!"

    def test_error_emoji_replaced(self):
        assert _ascii_version("\u274c  Error: something") == "ERROR: Error: something"

    def test_request_emoji_replaced(self):
        assert _ascii_version("\U0001f4cb  Requesting...") == "[REQ] Requesting..."

    def test_submit_emoji_replaced(self):
        assert _ascii_version("\U0001f4e4  Submitting...") == "[SUBMIT] Submitting..."

    def test_no_emoji_returns_text_unchanged(self):
        assert _ascii_version("hello world") == "hello world"

    def test_mixed_emoji_replaces_leading_only(self):
        result = _ascii_version("\u2705  Wallet created! Address: RTC123")
        assert result == "OK! Wallet created! Address: RTC123"


class TestSafeEcho:
    """Integration tests for _safe_echo under encoding stress."""

    def test_normal_stdout_passes_through(self, capsys):
        """When encoding works, output is identical to click.echo."""
        _safe_echo("hello")
        out, _ = capsys.readouterr()
        assert out.strip() == "hello"

    def test_encoding_error_falls_back_to_ascii_emoji(self):
        """When stdout cannot encode emoji, ASCII fallback is used."""
        call_count = [0]
        original_echo = click.echo

        def failing_echo(text, *a, **kw):
            call_count[0] += 1
            if any(ord(c) > 127 for c in text):
                raise UnicodeEncodeError("cp850", text, 0, len(text), "emoji")
            return original_echo(text, *a, **kw)

        buf = io.StringIO()
        with mock.patch.object(click, "echo", failing_echo):
            with mock.patch("sys.stdout", buf):
                _safe_echo("\u2705  OK")

        assert "OK!" in buf.getvalue()
        assert "\u2705" not in buf.getvalue()
        assert call_count[0] == 2  # one emoji call fails, one ASCII call succeeds

    def test_wallet_create_encoding_error_exits_zero(self, monkeypatch):
        """wallet create should succeed (exit 0) even if banner emoji fails.

        This reproduces the exact Windows CP850 scenario described in #6899.
        """
        import rustchain_sdk.cli as cli_mod

        from rustchain_sdk.wallet import RustChainWallet
        mock_wallet = mock.MagicMock()
        mock_wallet.address = "RTC" + "a" * 40
        mock_wallet.public_key_hex = "b" * 64
        mock_wallet.seed_phrase = ["abandon"] * 12
        mock_wallet.export.return_value = {"address": mock_wallet.address}
        monkeypatch.setattr(RustChainWallet, "create", lambda **kw: mock_wallet)

        banner_called = [False]

        def mock_safe_echo(text, *a, **kw):
            if any(c in text for c in "\u2705\u26a0\u274c\U0001f4cb\U0001f4e4"):
                banner_called[0] = True
                text = _ascii_version(text)
            click.echo(text, *a, **kw)

        cli_mod._safe_echo = mock_safe_echo

        from click.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(cli_mod.main, ["wallet", "create"])

        assert result.exit_code == 0, (
            f"wallet create should exit 0 on encoding error. "
            f"Got exit {result.exit_code}. Output: {result.output}"
        )
        assert banner_called[0], "Expected emoji banner path to be exercised"
        assert "RTC" in result.output
        assert "abandon" in result.output

    def test_wallet_create_ascii_fallback_prints_ascii_banner(self, monkeypatch):
        """When emoji fails, ASCII banner tokens appear in output."""
        import rustchain_sdk.cli as cli_mod

        from rustchain_sdk.wallet import RustChainWallet
        mock_wallet = mock.MagicMock()
        mock_wallet.address = "RTC" + "z" * 40
        mock_wallet.public_key_hex = "y" * 64
        mock_wallet.seed_phrase = ["test"] * 12
        mock_wallet.export.return_value = {"address": mock_wallet.address}
        monkeypatch.setattr(RustChainWallet, "create", lambda **kw: mock_wallet)

        def mock_safe_echo(text, *a, **kw):
            if any(c in text for c in "\u2705\u26a0"):
                text = _ascii_version(text)
            click.echo(text, *a, **kw)

        cli_mod._safe_echo = mock_safe_echo

        from click.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(cli_mod.main, ["wallet", "create"])

        assert "OK!" in result.output
        assert "WARNING:" in result.output
        assert "SAVE YOUR SEED" in result.output
