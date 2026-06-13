import importlib.util
from pathlib import Path

import requests


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "rustchain-poa"
    / "tools"
    / "net"
    / "poa_tcp_listener.py"
)


def load_listener():
    spec = importlib.util.spec_from_file_location("poa_tcp_listener", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeConn:
    def __init__(self, payload):
        self.payload = payload
        self.sent = []
        self.closed = False

    def recv(self, _size):
        return self.payload

    def sendall(self, data):
        self.sent.append(data)

    def close(self):
        self.closed = True


def test_handle_client_forwards_with_timeout(monkeypatch):
    listener = load_listener()
    conn = FakeConn(b'{"miner_id": "m1"}')
    calls = []

    class Response:
        status_code = 202

    def fake_post(url, json, timeout):
        calls.append((url, json, timeout))
        return Response()

    monkeypatch.setattr(listener.requests, "post", fake_post)

    listener.handle_client(conn, ("127.0.0.1", 12345))

    assert calls == [
        (
            listener.FORWARD_URL,
            {"miner_id": "m1"},
            listener.REQUEST_TIMEOUT,
        )
    ]
    assert conn.sent == [b"PoA received. Status: 202\n"]
    assert conn.closed is True


def test_handle_client_reports_forward_failure(monkeypatch):
    listener = load_listener()
    conn = FakeConn(b'{"miner_id": "m1"}')

    def fake_post(*_args, **_kwargs):
        raise requests.Timeout("slow API")

    monkeypatch.setattr(listener.requests, "post", fake_post)

    listener.handle_client(conn, ("127.0.0.1", 12345))

    assert conn.sent == [b"PoA forward failed.\n"]
    assert conn.closed is True
