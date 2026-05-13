# SPDX-License-Identifier: MIT
import importlib
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RIPS_PATH = str(ROOT / "rips")
if RIPS_PATH not in sys.path:
    sys.path.insert(0, RIPS_PATH)

p2p = importlib.import_module("rustchain-core.networking.p2p")


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
    manager = p2p.NetworkManager(require_mtls=False)

    manager.start()
    manager.connect_to_peer(p2p.PeerId("127.0.0.1", 8085))

    assert manager.running is True
    assert manager.outbound_queue.qsize() == 1
    manager.stop()
