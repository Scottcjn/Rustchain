from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("floppy_miner.py")


def load_module():
    spec = importlib.util.spec_from_file_location("floppy_miner_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_default_ssl_context_uses_platform_verification():
    module = load_module()

    assert module.create_ssl_context() is None


def test_insecure_ssl_context_is_explicit():
    module = load_module()

    context = module.create_ssl_context(False)

    assert context is not None
    assert context.check_hostname is False
    assert context.verify_mode == module.ssl.CERT_NONE


def test_submit_attestation_uses_verified_tls_by_default(monkeypatch):
    module = load_module()
    calls = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self):
            return b'{"ok": true}'

    def fake_urlopen(req, *, timeout, context):
        calls.append((req.full_url, timeout, context))
        return FakeResponse()

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

    result = module.submit_attestation("https://rustchain.example", {"miner": "m1"})

    assert result == {"ok": True}
    assert calls == [("https://rustchain.example/attest/submit", 10, None)]


def test_get_epoch_uses_verified_tls_by_default(monkeypatch):
    module = load_module()
    calls = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self):
            return b'{"epoch": 7}'

    def fake_urlopen(req, *, timeout, context):
        calls.append((req.full_url, timeout, context))
        return FakeResponse()

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

    assert module.get_epoch("https://rustchain.example") == {"epoch": 7}
    assert calls == [("https://rustchain.example/epoch", 5, None)]
