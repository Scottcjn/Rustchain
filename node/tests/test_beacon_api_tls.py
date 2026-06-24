from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "beacon_api.py"


def load_module():
    spec = importlib.util.spec_from_file_location("beacon_api_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_github_sync_ssl_context_uses_platform_verification_by_default(monkeypatch):
    module = load_module()
    monkeypatch.delenv("RC_DISABLE_SSL_VERIFY", raising=False)

    assert module.github_sync_ssl_context() is None


def test_github_sync_ssl_context_requires_explicit_disable_flag(monkeypatch):
    module = load_module()
    monkeypatch.setenv("RC_DISABLE_SSL_VERIFY", "1")

    context = module.github_sync_ssl_context()

    assert context is not None
    assert context.check_hostname is False
    assert context.verify_mode == module.ssl.CERT_NONE


def test_github_sync_ssl_context_ignores_non_one_values(monkeypatch):
    module = load_module()
    monkeypatch.setenv("RC_DISABLE_SSL_VERIFY", "true")

    assert module.github_sync_ssl_context() is None
