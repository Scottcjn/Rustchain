from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("rustchain_ae.py")


def load_module():
    spec = importlib.util.spec_from_file_location("rustchain_ae_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_default_tls_context_uses_platform_verification():
    module = load_module()

    assert module.VERIFY_SSL is True
    assert module.SSL_CTX is None
    assert module.create_ssl_context(True) is None


def test_insecure_tls_context_requires_explicit_helper_call():
    module = load_module()

    context = module.create_ssl_context(False)

    assert context is not None
    assert context.check_hostname is False
    assert context.verify_mode == module.ssl.CERT_NONE


def test_api_get_passes_verified_default_context(monkeypatch):
    module = load_module()
    calls = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self):
            return b'{"ok": true}'

    def fake_urlopen(req, *, context, timeout):
        calls.append((req.full_url, context, timeout))
        return FakeResponse()

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

    assert module.api_get("/agent/stats") == {"ok": True}
    assert calls == [("https://50.28.86.131/agent/stats", None, 15)]
