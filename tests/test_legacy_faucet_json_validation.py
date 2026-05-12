import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

import faucet


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(faucet, "DATABASE", str(tmp_path / "faucet.db"))
    faucet.init_db()
    faucet.app.config.update(TESTING=True)
    return faucet.app.test_client()


def test_legacy_faucet_rejects_malformed_json(client):
    response = client.post(
        "/faucet/drip",
        data="{",
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "Invalid JSON body"}


def test_legacy_faucet_rejects_non_object_json(client):
    response = client.post("/faucet/drip", json=["wallet"])

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "Invalid JSON body"}


def test_legacy_faucet_rejects_non_string_wallet(client):
    response = client.post("/faucet/drip", json={"wallet": ["0x123456789"]})

    assert response.status_code == 400
    assert response.get_json() == {"ok": False, "error": "Invalid wallet address"}


def test_legacy_faucet_records_only_one_concurrent_drip(client):
    start = threading.Event()
    wallet = "0x1234567890abcdef"

    def post_drip():
        start.wait()
        with faucet.app.test_client() as thread_client:
            response = thread_client.post("/faucet/drip", json={"wallet": wallet})
            return response.status_code

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(post_drip) for _ in range(8)]
        start.set()
        statuses = [future.result(timeout=10) for future in futures]

    assert statuses.count(200) == 1
    assert statuses.count(429) == 7

    with sqlite3.connect(faucet.DATABASE) as conn:
        count = conn.execute("SELECT COUNT(*) FROM drip_requests").fetchone()[0]

    assert count == 1
