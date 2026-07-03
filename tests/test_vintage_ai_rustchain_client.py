"""Tests for the vintage AI video RustChain client."""

import importlib.util
from pathlib import Path


def load_client_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "vintage_ai_video_pipeline" / "rustchain_client.py"
    spec = importlib.util.spec_from_file_location("vintage_rustchain_client", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_get_miners_accepts_envelope_payloads(monkeypatch):
    module = load_client_module()
    client = module.RustChainClient(base_url="https://node.example")

    monkeypatch.setattr(
        client,
        "_get_public",
        lambda endpoint, params=None: {
            "items": [
                {"miner": "alice", "hardware_type": "PowerPC G4"},
                {"miner": "bob", "hardware_type": "x86-64"},
            ],
            "pagination": {"total": 2},
        },
    )

    assert client.get_miners() == [
        {"miner": "alice", "hardware_type": "PowerPC G4"},
        {"miner": "bob", "hardware_type": "x86-64"},
    ]


def test_get_miners_returns_empty_list_for_unexpected_payload(monkeypatch):
    module = load_client_module()
    client = module.RustChainClient(base_url="https://node.example")

    monkeypatch.setattr(client, "_get_public", lambda endpoint, params=None: {"pagination": {"total": 0}})

    assert client.get_miners() == []


# --- Issue #7351: Unhandled JSONDecodeError on Empty 200 OK Responses ---


def test_request_handles_empty_200_ok_body(monkeypatch):
    """Issue #7351: 200 OK with empty body must NOT raise JSONDecodeError.

    The original code only checked `if response_data else {}`, which missed
    whitespace-only bodies (a common nginx/proxy response pattern).
    """
    module = load_client_module()
    client = module.RustChainClient(base_url="https://node.example")

    fake_response = _make_fake_response(b"")
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *a, **kw: fake_response
    )

    result = client._request("GET", "/api/health")
    assert result == {}, f"expected {{}}, got {result!r}"


def test_request_handles_whitespace_only_200_ok_body(monkeypatch):
    """Issue #7351: 200 OK with whitespace-only body must NOT raise.

    A whitespace-only body is JSON-invalid but semantically empty. The fix
    strips before checking, so the response is treated as no-payload.
    """
    module = load_client_module()
    client = module.RustChainClient(base_url="https://node.example")

    fake_response = _make_fake_response(b"   \n\t  ")
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *a, **kw: fake_response
    )

    result = client._request("GET", "/api/health")
    assert result == {}, f"expected {{}}, got {result!r}"


def test_request_handles_valid_json(monkeypatch):
    """Regression: normal JSON response still parses correctly."""
    module = load_client_module()
    client = module.RustChainClient(base_url="https://node.example")

    fake_response = _make_fake_response(b'{"status": "ok", "epoch": 191}')
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *a, **kw: fake_response
    )

    result = client._request("GET", "/api/health")
    assert result == {"status": "ok", "epoch": 191}


def test_request_propagates_invalid_json(monkeypatch):
    """Regression: non-empty non-JSON body still raises (per retry/raise policy).

    The fix only narrows the 'empty / whitespace' case. Real JSON errors
    must still surface so callers see upstream misconfiguration.
    """
    module = load_client_module()
    client = module.RustChainClient(
        base_url="https://node.example", retry_count=1, retry_delay=0
    )

    fake_response = _make_fake_response(b"<html>nginx error page</html>")
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *a, **kw: fake_response
    )

    raised = False
    try:
        client._request("GET", "/api/health")
    except Exception as exc:
        raised = True
        assert "Invalid JSON" in str(exc) or "JSON" in str(exc), (
            f"expected JSON-related error, got: {exc!r}"
        )
    assert raised, "non-JSON non-empty body should still raise after retries"


def _make_fake_response(body: bytes):
    """Build a context-manager fake that mimics urllib's response.read()."""
    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return body

    return FakeResp()


# --- Issue #6624: _request_public must NOT include admin key headers ---


def test_request_public_uses_public_headers(monkeypatch):
    """_request_public must use _get_public_headers (no admin key)."""
    module = load_client_module()
    client = module.RustChainClient(
        base_url="https://node.example", admin_key="secret-admin-key-123"
    )

    captured_headers = {}

    class FakeResp:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return b'{"ok": true}'

    def fake_urlopen(req, **kwargs):
        captured_headers.update(req.headers)
        return FakeResp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = client._request_public("GET", "/health")
    assert result == {"ok": True}
    assert "X-Admin-Key" not in captured_headers, (
        f"_request_public must not send admin key; got headers: {captured_headers}"
    )
    assert captured_headers.get("Accept") == "application/json"


def test_request_with_admin_key_sends_header(monkeypatch):
    """_request (authenticated) must include X-Admin-Key when configured."""
    module = load_client_module()
    client = module.RustChainClient(
        base_url="https://node.example", admin_key="secret-admin-key-123"
    )

    captured_headers = {}

    class FakeResp:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return b'{"ok": true}'

    def fake_urlopen(req, **kwargs):
        captured_headers.update(req.headers)
        return FakeResp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = client._request("POST", "/api/submit", data={"key": "val"})
    assert result == {"ok": True}
    headers_lower = {k.lower(): v for k, v in captured_headers.items()}
    assert headers_lower.get("x-admin-key") == "secret-admin-key-123"


def test_read_methods_use_public_no_admin_key(monkeypatch):
    """Read methods (health, get_epoch, get_miners, etc.) must not send admin key."""
    module = load_client_module()
    client = module.RustChainClient(
        base_url="https://node.example", admin_key="secret-admin-key-123"
    )

    captured_headers = {}

    class FakeResp:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return b'{"result": "ok"}'

    def fake_urlopen(req, **kwargs):
        captured_headers.clear()
        captured_headers.update(req.headers)
        return FakeResp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    read_endpoints = [
        lambda: client.health(),
        lambda: client.get_epoch(),
        lambda: client.get_wallet_balance("miner_123"),
        lambda: client.get_wallet_history("miner_123"),
        lambda: client.get_stats(),
        lambda: client.get_hall_of_fame(),
        lambda: client.get_miner_eligibility("miner_123"),
    ]

    for call in read_endpoints:
        call()
        assert "X-Admin-Key" not in captured_headers, (
            f"Read method must not send admin key; got: {captured_headers}"
        )


def test_admin_key_not_set_no_header_sent(monkeypatch):
    """When admin_key is None, no X-Admin-Key header is sent even on write requests."""
    module = load_client_module()
    client = module.RustChainClient(base_url="https://node.example")

    captured_headers = {}

    class FakeResp:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return b'{"ok": true}'

    def fake_urlopen(req, **kwargs):
        captured_headers.update(req.headers)
        return FakeResp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    client._request("POST", "/api/submit", data={"key": "val"})
    assert "X-Admin-Key" not in captured_headers


def test_get_public_headers_never_includes_admin_key():
    """_get_public_headers() must never include admin key regardless of config."""
    module = load_client_module()
    client = module.RustChainClient(
        base_url="https://node.example", admin_key="super-secret"
    )
    headers = client._get_public_headers()
    assert "X-Admin-Key" not in headers
    assert "Accept" in headers


def test_get_headers_includes_admin_key_when_set():
    """_get_headers() includes admin key when configured."""
    module = load_client_module()
    client = module.RustChainClient(
        base_url="https://node.example", admin_key="my-admin-key"
    )
    headers = client._get_headers()
    assert headers["X-Admin-Key"] == "my-admin-key"


def test_get_headers_no_admin_key_when_unset():
    """_get_headers() omits admin key when not configured."""
    module = load_client_module()
    client = module.RustChainClient(base_url="https://node.example")
    headers = client._get_headers()
    assert "X-Admin-Key" not in headers
