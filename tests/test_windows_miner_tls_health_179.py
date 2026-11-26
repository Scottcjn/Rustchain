# SPDX-License-Identifier: MIT
"""Regression tests for Windows miner HTTPS default, TLS verification, and /health."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import setup_miner


ROOT = Path(__file__).resolve().parents[1]
MINER_PATH = ROOT / "miners" / "windows" / "rustchain_windows_miner.py"
SETUP_BAT_PATH = ROOT / "miners" / "windows" / "rustchain_miner_setup.bat"


class _StubResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.ok = 200 <= status_code < 400
        self._payload = payload
        self.text = ""

    def json(self):
        return self._payload


def _load_miner():
    spec = importlib.util.spec_from_file_location("windows_miner_tls_179", MINER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_defaults_to_https_and_upgrades_legacy_dead_port():
    module = _load_miner()

    assert module.RUSTCHAIN_API == "https://rustchain.org"
    assert module._normalize_node_url(None) == "https://rustchain.org"
    assert module._normalize_node_url("http://50.28.86.131:8088") == "https://rustchain.org"
    assert module._normalize_node_url("https://testnet.rustchain.org/") == "https://testnet.rustchain.org"

    miner = module.RustChainMiner(
        "RTCfe0ac752b80e543048c0d91e7dddd1277678b8a5",
        node_url="http://50.28.86.131:8088",
    )
    assert miner.node_url == "https://rustchain.org"


def test_tls_verification_never_disables_and_honors_pin_and_ca_bundle(monkeypatch, tmp_path):
    module = _load_miner()
    pinned_cert = tmp_path / "node_cert.pem"
    ca_bundle = tmp_path / "ca.pem"

    monkeypatch.delenv("RUSTCHAIN_CA_BUNDLE", raising=False)
    monkeypatch.setenv("RUSTCHAIN_TLS_VERIFY", "0")
    monkeypatch.setattr(module, "_CERT_PATH", str(pinned_cert))

    # Default: system CA verification (True), never False even if opt-out env is set.
    assert module._tls_verify() is True
    assert module._request_kwargs(10) == {"timeout": 10}

    # Pinned cert file present -> passes verify=<pinned_cert>.
    pinned_cert.write_text("pinned", encoding="utf-8")
    assert module._tls_verify() == str(pinned_cert)
    assert module._request_kwargs(10) == {"timeout": 10, "verify": str(pinned_cert)}

    # Explicit RUSTCHAIN_CA_BUNDLE overrides pinned cert path.
    ca_bundle.write_text("bundle", encoding="utf-8")
    monkeypatch.setenv("RUSTCHAIN_CA_BUNDLE", str(ca_bundle))
    assert module._tls_verify() == str(ca_bundle)
    assert module._request_kwargs(15) == {"timeout": 15, "verify": str(ca_bundle)}


def test_check_node_health_parses_success_and_failures(monkeypatch, tmp_path):
    module = _load_miner()
    ca_bundle = tmp_path / "ca.pem"
    ca_bundle.write_text("bundle", encoding="utf-8")
    monkeypatch.setenv("RUSTCHAIN_CA_BUNDLE", str(ca_bundle))

    miner = module.RustChainMiner("RTCfe0ac752b80e543048c0d91e7dddd1277678b8a5")
    seen = []

    def fake_get_ok(url, **kwargs):
        seen.append((url, kwargs))
        return _StubResponse(200, {"ok": True, "version": "2.2.1-rip200"})

    monkeypatch.setattr(module.requests, "get", fake_get_ok)
    ok_res = miner.check_node_health()
    assert ok_res["ok"] is True
    assert ok_res["status_code"] == 200
    assert ok_res["data"]["version"] == "2.2.1-rip200"
    assert seen == [("https://rustchain.org/health", {"timeout": 10, "verify": str(ca_bundle)})]

    monkeypatch.setattr(
        module.requests,
        "get",
        lambda *_a, **_kw: _StubResponse(503, {"error": "restarting"}),
    )
    err_res = miner.check_node_health()
    assert err_res["ok"] is False
    assert err_res["status_code"] == 503
    assert "HTTP 503" in err_res["error"]

    def fake_get_boom(*_a, **_kw):
        raise OSError("certificate verify failed")

    monkeypatch.setattr(module.requests, "get", fake_get_boom)
    exc_res = miner.check_node_health()
    assert exc_res["ok"] is False
    assert exc_res["status_code"] == 0
    assert "certificate verify failed" in exc_res["error"]


def test_attest_and_enroll_pass_ca_bundle_verify(monkeypatch, tmp_path):
    module = _load_miner()
    ca_bundle = tmp_path / "ca.pem"
    ca_bundle.write_text("bundle", encoding="utf-8")
    monkeypatch.setenv("RUSTCHAIN_CA_BUNDLE", str(ca_bundle))
    monkeypatch.setattr(module, "FINGERPRINT_AVAILABLE", False)
    monkeypatch.setattr(module, "CRYPTO_AVAILABLE", False)

    miner = module.RustChainMiner("RTCfe0ac752b80e543048c0d91e7dddd1277678b8a5")
    calls = []

    def fake_post(url, **kwargs):
        calls.append(("POST", url, kwargs))
        if url.endswith("/attest/challenge"):
            return _StubResponse(200, {"nonce": "n1"})
        return _StubResponse(200, {"ok": True})

    def fake_get(url, **kwargs):
        calls.append(("GET", url, kwargs))
        return _StubResponse(200, {"epoch": 7})

    monkeypatch.setattr(module.requests, "post", fake_post)
    monkeypatch.setattr(module.requests, "get", fake_get)

    assert miner.attest() is True
    assert miner.enroll() is True
    assert [c[1] for c in calls] == [
        "https://rustchain.org/attest/challenge",
        "https://rustchain.org/attest/submit",
        "https://rustchain.org/epoch",
        "https://rustchain.org/epoch/enroll",
    ]
    for _method, _url, kwargs in calls:
        assert kwargs["verify"] == str(ca_bundle)


def test_pinned_checksums_match_windows_miner():
    expected = hashlib.sha256(MINER_PATH.read_bytes()).hexdigest()
    bat_text = SETUP_BAT_PATH.read_text(encoding="utf-8")

    assert f'set "MINER_SHA256={expected}"' in bat_text
    assert setup_miner.MINER_ARTIFACTS["Windows"]["sha256"] == expected
