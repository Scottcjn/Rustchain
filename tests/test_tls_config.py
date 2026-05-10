# SPDX-License-Identifier: MIT
import ssl
from pathlib import Path

from node import tls_config


def test_verified_tls_clients_default_to_certificate_hostname():
    assert 'os.environ.get("RUSTCHAIN_NODE_URL", "https://rustchain.org")' in Path(
        "agent_reputation.py"
    ).read_text(encoding="utf-8")
    assert 'os.environ.get("RUSTCHAIN_NODE_URL", "https://rustchain.org")' in Path(
        "websocket_feed.py"
    ).read_text(encoding="utf-8")
    assert (
        "os.environ.get('RUSTCHAIN_NODE_URL', os.environ.get('RUSTCHAIN_API_BASE', 'https://rustchain.org'))"
        in Path("explorer/explorer_websocket_server.py").read_text(encoding="utf-8")
    )


def test_ssl_context_verifies_by_default(monkeypatch):
    monkeypatch.delenv("RUSTCHAIN_TLS_VERIFY", raising=False)
    monkeypatch.delenv("RUSTCHAIN_CA_BUNDLE", raising=False)
    monkeypatch.setattr(tls_config.os.path, "exists", lambda path: False)

    context = tls_config.get_ssl_context()

    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True


def test_ssl_context_can_use_explicit_local_opt_out(monkeypatch):
    monkeypatch.setenv("RUSTCHAIN_TLS_VERIFY", "false")
    monkeypatch.delenv("RUSTCHAIN_CA_BUNDLE", raising=False)

    context = tls_config.get_ssl_context()

    assert context.verify_mode == ssl.CERT_NONE
    assert context.check_hostname is False
