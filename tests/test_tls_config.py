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


def test_public_sdk_and_macos_defaults_avoid_raw_node_ip():
    legacy_public_node = "https://" + "50.28.86.131"
    default_surfaces = [
        "sdk/python/README.md",
        "sdk/python/rustchain_sdk/__init__.py",
        "sdk/python/rustchain_sdk/client.py",
        "sdk/python/rustchain_sdk/cli.py",
        "sdk/python/test_rustchain_sdk.py",
        "miners/macos/rustchain_mac_miner_v2.5.py",
    ]

    for relpath in default_surfaces:
        text = Path(relpath).read_text(encoding="utf-8")
        assert legacy_public_node not in text, relpath
        assert "https://rustchain.org" in text or "DEFAULT_NODE_URL" in text, relpath


def test_ssl_context_verifies_by_default(monkeypatch):
    monkeypatch.delenv("RUSTCHAIN_TLS_VERIFY", raising=False)
    monkeypatch.delenv("RUSTCHAIN_CA_BUNDLE", raising=False)
    monkeypatch.setattr(tls_config.os.path, "exists", lambda path: False)

    context = tls_config.get_ssl_context()

    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True


def test_requests_tls_verify_honors_explicit_ca_bundle(monkeypatch, tmp_path):
    ca_bundle = tmp_path / "ca.pem"
    ca_bundle.write_text("test-ca", encoding="utf-8")
    monkeypatch.delenv("RUSTCHAIN_TLS_VERIFY", raising=False)
    monkeypatch.setenv("RUSTCHAIN_CA_BUNDLE", str(ca_bundle))

    assert tls_config.get_tls_verify() == str(ca_bundle)


def test_requests_tls_verify_can_use_explicit_local_opt_out(monkeypatch):
    monkeypatch.setenv("RUSTCHAIN_TLS_VERIFY", "false")
    monkeypatch.setenv("RUSTCHAIN_CA_BUNDLE", "/tmp/ca.pem")
    monkeypatch.setattr(tls_config.os.path, "exists", lambda path: True)

    assert tls_config.get_tls_verify() is False


def test_ssl_context_can_use_explicit_local_opt_out(monkeypatch):
    monkeypatch.setenv("RUSTCHAIN_TLS_VERIFY", "false")
    monkeypatch.delenv("RUSTCHAIN_CA_BUNDLE", raising=False)

    context = tls_config.get_ssl_context()

    assert context.verify_mode == ssl.CERT_NONE
    assert context.check_hostname is False
