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
        "_get",
        lambda endpoint: {
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

    monkeypatch.setattr(client, "_get", lambda endpoint: {"pagination": {"total": 0}})

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
