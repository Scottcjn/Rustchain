# SPDX-License-Identifier: MIT
import importlib
import struct
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RIPS_PATH = str(ROOT / "rips")
if RIPS_PATH not in sys.path:
    sys.path.insert(0, RIPS_PATH)

p2p = importlib.import_module("rustchain-core.networking.p2p")


class FakeMTLSConfig:
    def __init__(self, client_context=None, server_context=None):
        self.client_context = client_context or FakeSSLContext()
        self.server_context = server_context or FakeSSLContext()

    def missing_values(self):
        return []

    def missing_files(self):
        return []

    def build_client_context(self):
        return self.client_context

    def build_server_context(self):
        return self.server_context


class FakeSSLContext:
    def __init__(self):
        self.wrap_calls = []

    def wrap_socket(self, raw_sock, server_hostname=None, server_side=False):
        self.wrap_calls.append({
            "server_hostname": server_hostname,
            "server_side": server_side,
        })
        return raw_sock


class FakeSocket:
    def __init__(self, recv_bytes=b""):
        self.sent = b""
        self.recv_bytes = recv_bytes
        self.closed = False
        self._closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def sendall(self, data):
        self.sent += data

    def recv(self, size):
        chunk = self.recv_bytes[:size]
        self.recv_bytes = self.recv_bytes[size:]
        return chunk

    def close(self):
        self.closed = True
        self._closed = True


def _clear_mtls_env(monkeypatch):
    monkeypatch.delenv(p2p.P2P_TLS_CERT_ENV, raising=False)
    monkeypatch.delenv(p2p.P2P_TLS_KEY_ENV, raising=False)
    monkeypatch.delenv(p2p.P2P_TLS_CA_ENV, raising=False)
    monkeypatch.delenv(p2p.P2P_REQUIRE_MTLS_ENV, raising=False)


def test_p2p_start_fails_closed_without_mtls_material(monkeypatch):
    _clear_mtls_env(monkeypatch)
    manager = p2p.NetworkManager()

    with pytest.raises(RuntimeError) as exc:
        manager.start()

    message = str(exc.value)
    assert "P2P mTLS is required" in message
    assert p2p.P2P_TLS_CERT_ENV in message
    assert p2p.P2P_TLS_KEY_ENV in message
    assert p2p.P2P_TLS_CA_ENV in message
    assert manager.running is False


def test_p2p_connect_fails_closed_without_mtls_material(monkeypatch):
    _clear_mtls_env(monkeypatch)
    manager = p2p.NetworkManager()

    with pytest.raises(RuntimeError, match="P2P mTLS is required"):
        manager.connect_to_peer(p2p.PeerId("127.0.0.1", 8085))

    assert manager.outbound_queue.empty()


def test_p2p_reports_missing_mtls_files(monkeypatch, tmp_path):
    missing_cert = tmp_path / "node.crt"
    missing_key = tmp_path / "node.key"
    missing_ca = tmp_path / "ca.crt"
    monkeypatch.setenv(p2p.P2P_TLS_CERT_ENV, str(missing_cert))
    monkeypatch.setenv(p2p.P2P_TLS_KEY_ENV, str(missing_key))
    monkeypatch.setenv(p2p.P2P_TLS_CA_ENV, str(missing_ca))
    monkeypatch.delenv(p2p.P2P_REQUIRE_MTLS_ENV, raising=False)

    manager = p2p.NetworkManager()

    with pytest.raises(RuntimeError) as exc:
        manager.start()

    message = str(exc.value)
    assert "P2P mTLS file(s) not found" in message
    assert str(missing_cert) in message
    assert str(missing_key) in message
    assert str(missing_ca) in message


def test_p2p_allows_explicit_local_insecure_mode(monkeypatch):
    _clear_mtls_env(monkeypatch)
    manager = p2p.NetworkManager(listen_port=0, require_mtls=False, auto_send=False)

    manager.start()
    manager.connect_to_peer(p2p.PeerId("127.0.0.1", 8085))

    assert manager.running is True
    assert manager.outbound_queue.qsize() == 1
    manager.stop()


def test_configured_p2p_send_wraps_peer_connection_in_tls(monkeypatch):
    client_context = FakeSSLContext()
    fake_config = FakeMTLSConfig(client_context=client_context)
    fake_socket = FakeSocket()
    created = []

    def fake_create_connection(target, timeout):
        created.append((target, timeout))
        return fake_socket

    monkeypatch.setattr(p2p.socket, "create_connection", fake_create_connection)

    manager = p2p.NetworkManager(mtls_config=fake_config)
    peer = p2p.PeerId("peer.example", 27180)

    assert manager.send_message(peer, p2p.MessageType.HELLO, {"version": "test"}) is True

    assert created == [(("peer.example", 27180), 5.0)]
    assert client_context.wrap_calls == [{
        "server_hostname": "peer.example",
        "server_side": False,
    }]
    size = struct.unpack("!I", fake_socket.sent[:4])[0]
    assert size == len(fake_socket.sent) - 4
    assert b'"HELLO"' in fake_socket.sent


def test_configured_p2p_receive_wraps_inbound_socket_in_tls():
    server_context = FakeSSLContext()
    fake_config = FakeMTLSConfig(server_context=server_context)
    manager = p2p.NetworkManager(mtls_config=fake_config, auto_send=False)

    message = p2p.Message(
        msg_type=p2p.MessageType.NEW_TX,
        sender=p2p.PeerId("peer.example", 27180),
        payload={"tx": "abc"},
    )
    payload = message.to_bytes()
    fake_socket = FakeSocket(struct.pack("!I", len(payload)) + payload)

    assert manager.receive_message_from_socket(fake_socket, ("peer.example", 27180)) is True

    assert server_context.wrap_calls == [{
        "server_hostname": None,
        "server_side": True,
    }]


def test_configured_p2p_rejects_oversized_wire_frame():
    server_context = FakeSSLContext()
    fake_config = FakeMTLSConfig(server_context=server_context)
    manager = p2p.NetworkManager(mtls_config=fake_config, auto_send=False)
    oversized = p2p.WIRE_MESSAGE_MAX_BYTES + 1
    fake_socket = FakeSocket(struct.pack("!I", oversized))

    with pytest.raises(ValueError, match="invalid P2P message frame size"):
        manager.receive_message_from_socket(fake_socket, ("peer.example", 27180))
