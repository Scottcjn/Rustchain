"""
tests/test_rent_a_relic.py -- End-to-end tests for the Rent-a-Relic marketplace.

Coverage:
  - Reservation flow (reserve -> active -> complete)
  - Escrow lock and release (completion + timeout)
  - Provenance receipt generation and Ed25519 verification
  - Availability window validation
  - Time slot validation (only 1, 4, 24 allowed)
  - Leaderboard ordering
  - Machine registry integrity
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.rent_a_relic.models import (
    MACHINE_REGISTRY,
    VALID_DURATIONS_HOURS,
    EscrowStatus,
    EscrowTransaction,
    Machine,
    Reservation,
    ReservationStatus,
)
from tools.rent_a_relic.provenance import generate_receipt, verify_receipt

ADMIN_KEY = "test-admin-key"


@pytest.fixture()
def app(tmp_path, monkeypatch):
    from tools.rent_a_relic import server
    db_file = str(tmp_path / "test_relic.db")
    monkeypatch.setenv("RC_ADMIN_KEY", ADMIN_KEY)
    server.app.config["TESTING"] = True
    server.app.config["DB_PATH"]  = db_file
    server.init_db()
    with server.app.test_client() as client:
        yield client


def admin_headers(key: str = ADMIN_KEY) -> dict[str, str]:
    return {"X-Admin-Key": key}


@pytest.fixture()
def machine() -> Machine:
    return MACHINE_REGISTRY["g5-dual"]


@pytest.fixture()
def reservation(machine: Machine) -> Reservation:
    r = Reservation(
        session_id=str(uuid.uuid4()),
        machine_id=machine.machine_id,
        agent_id="agent_test_001",
        duration_hours=1,
        rtc_amount=10.0,
    )
    r.activate()
    return r


class TestMachineRegistry:
    def test_registry_has_all_archs(self):
        archs = {m.arch for m in MACHINE_REGISTRY.values()}
        expected = {"ppc32", "ppc64", "ppc64le", "sparc64", "alpha", "m68k", "riscv64"}
        assert expected.issubset(archs), f"Missing archs: {expected - archs}"

    def test_each_machine_has_passport(self):
        for mid, m in MACHINE_REGISTRY.items():
            assert len(m.passport_id()) == 32, f"{mid}: passport_id should be 32 hex chars"

    def test_each_machine_has_public_key(self):
        for mid, m in MACHINE_REGISTRY.items():
            assert len(m.public_key_hex()) == 64, f"{mid}: public_key should be 64 hex chars"

    def test_machine_to_dict_keys(self):
        d = MACHINE_REGISTRY["g3-beige"].to_dict()
        required = {"machine_id", "name", "arch", "year", "cpu_model", "ram_mb",
                    "ssh_endpoint", "photo_url", "attestation_count", "rtc_per_hour",
                    "available", "passport_id", "public_key_hex"}
        assert required.issubset(d.keys())

    def test_machine_count(self):
        assert len(MACHINE_REGISTRY) == 8


class TestTimeSlotValidation:
    def test_valid_durations(self):
        assert VALID_DURATIONS_HOURS == {1, 4, 24}

    def test_reserve_invalid_duration(self, app):
        resp = app.post("/relic/reserve", json={
            "agent_id": "a1", "machine_id": "g3-beige",
            "duration_hours": 3, "rtc_amount": 999,
        })
        assert resp.status_code == 400
        assert "duration_hours" in resp.json["error"]

    def test_reserve_valid_durations(self, app):
        for hours in [1, 4, 24]:
            resp = app.post("/relic/reserve", json={
                "agent_id":       f"agent_slot_{hours}",
                "machine_id":     "amiga-68k",
                "duration_hours": hours,
                "rtc_amount":     MACHINE_REGISTRY["amiga-68k"].rtc_per_hour * hours,
            })
            assert resp.status_code in (201, 409)


class TestReservationFlow:
    def test_reserve_machine(self, app):
        resp = app.post("/relic/reserve", json={
            "agent_id": "agent_flow_001", "machine_id": "riscv-hifive",
            "duration_hours": 1, "rtc_amount": 10.0,
        })
        assert resp.status_code == 201
        assert "session_id" in resp.json
        assert resp.json["reservation"]["status"] == "active"
        assert resp.json["escrow"]["status"] == "locked"
        assert "ssh_endpoint" in resp.json

    def test_reserve_sets_expires_at(self, app):
        before = time.time()
        resp = app.post("/relic/reserve", json={
            "agent_id": "agent_exp", "machine_id": "alpha-ds20",
            "duration_hours": 4, "rtc_amount": 28.0,
        })
        assert resp.status_code == 201
        assert resp.json["reservation"]["expires_at"] > before + 4 * 3600 - 5

    def test_double_reserve_returns_409(self, app):
        payload = {"agent_id": "dup1", "machine_id": "sparc-ultra",
                   "duration_hours": 1, "rtc_amount": 10.0}
        r1 = app.post("/relic/reserve", json=payload)
        r2 = app.post("/relic/reserve", json={**payload, "agent_id": "dup2"})
        assert r1.status_code == 201
        assert r2.status_code == 409

    def test_complete_session(self, app):
        r = app.post("/relic/reserve", json={
            "agent_id": "agent_cmp", "machine_id": "power8-ibm",
            "duration_hours": 1, "rtc_amount": 15.0,
        })
        assert r.status_code == 201
        cr = app.post(f"/relic/complete/{r.json['session_id']}",
                      json={"output_hash": hashlib.sha256(b"output").hexdigest()},
                      headers=admin_headers())
        assert cr.status_code == 200
        assert cr.json["status"] == "completed"

    def test_complete_rejects_non_object_json(self, app):
        r = app.post("/relic/reserve", json={
            "agent_id": "agent_bad_complete", "machine_id": "riscv-hifive",
            "duration_hours": 1, "rtc_amount": 10.0,
        })
        assert r.status_code == 201

        cr = app.post(f"/relic/complete/{r.json['session_id']}", json=["not", "object"],
                      headers=admin_headers())
        assert cr.status_code == 400
        assert cr.json["error"] == "JSON object required"

    def test_complete_requires_admin_key_and_preserves_escrow(self, app):
        r = app.post("/relic/reserve", json={
            "agent_id": "agent_no_admin", "machine_id": "riscv-hifive",
            "duration_hours": 1, "rtc_amount": 10.0,
        })
        sid = r.json["session_id"]

        cr = app.post(f"/relic/complete/{sid}")
        sr = app.get(f"/relic/reservation/{sid}")

        assert cr.status_code == 401
        assert sr.json["status"] == "active"
        assert sr.json["escrow"]["status"] == "locked"

    def test_complete_rejects_wrong_admin_key_and_preserves_escrow(self, app):
        r = app.post("/relic/reserve", json={
            "agent_id": "agent_bad_admin", "machine_id": "g5-dual",
            "duration_hours": 1, "rtc_amount": 8.0,
        })
        sid = r.json["session_id"]

        cr = app.post(f"/relic/complete/{sid}", headers=admin_headers("wrong-key"))
        sr = app.get(f"/relic/reservation/{sid}")

        assert cr.status_code == 401
        assert sr.json["status"] == "active"
        assert sr.json["escrow"]["status"] == "locked"

    def test_complete_rejects_non_ascii_admin_key_without_crashing(self, app):
        r = app.post("/relic/reserve", json={
            "agent_id": "agent_non_ascii_admin", "machine_id": "alpha-ds20",
            "duration_hours": 1, "rtc_amount": 7.0,
        })
        sid = r.json["session_id"]

        cr = app.post(f"/relic/complete/{sid}", headers=admin_headers("\u00e9"))
        sr = app.get(f"/relic/reservation/{sid}")

        assert cr.status_code == 401
        assert sr.json["status"] == "active"
        assert sr.json["escrow"]["status"] == "locked"

    def test_complete_fails_closed_when_admin_key_unconfigured(self, app, monkeypatch):
        r = app.post("/relic/reserve", json={
            "agent_id": "agent_unconfigured_admin", "machine_id": "sparc-ultra",
            "duration_hours": 1, "rtc_amount": 6.0,
        })
        sid = r.json["session_id"]
        monkeypatch.delenv("RC_ADMIN_KEY", raising=False)

        cr = app.post(f"/relic/complete/{sid}", headers=admin_headers())
        sr = app.get(f"/relic/reservation/{sid}")

        assert cr.status_code == 503
        assert sr.json["status"] == "active"
        assert sr.json["escrow"]["status"] == "locked"

    def test_status_endpoint(self, app):
        r = app.post("/relic/reserve", json={
            "agent_id": "agent_stat", "machine_id": "g4-quicksilver",
            "duration_hours": 1, "rtc_amount": 5.0,
        })
        assert r.status_code == 201
        sr = app.get(f"/relic/reservation/{r.json['session_id']}")
        assert sr.status_code == 200
        assert sr.json["session_id"] == r.json["session_id"]
        assert "machine" in sr.json

    def test_missing_agent_id_returns_400(self, app):
        resp = app.post("/relic/reserve", json={
            "machine_id": "g3-beige", "duration_hours": 1, "rtc_amount": 4.0,
        })
        assert resp.status_code == 400

    def test_reserve_rejects_non_object_json(self, app):
        resp = app.post("/relic/reserve", json=["not", "object"])
        assert resp.status_code == 400
        assert resp.json["error"] == "JSON object required"

    def test_unknown_machine_returns_404(self, app):
        resp = app.post("/relic/reserve", json={
            "agent_id": "a", "machine_id": "nonexistent",
            "duration_hours": 1, "rtc_amount": 10.0,
        })
        assert resp.status_code == 404

    def test_insufficient_rtc_returns_400(self, app):
        resp = app.post("/relic/reserve", json={
            "agent_id": "a", "machine_id": "g5-dual",
            "duration_hours": 4, "rtc_amount": 1.0,
        })
        assert resp.status_code == 400
        assert "RTC" in resp.json["error"]


class TestEscrow:
    def test_escrow_locked_on_reserve(self, app):
        resp = app.post("/relic/reserve", json={
            "agent_id": "escrow_a", "machine_id": "g3-beige",
            "duration_hours": 1, "rtc_amount": 4.0,
        })
        assert resp.status_code == 201
        assert resp.json["escrow"]["status"] == "locked"
        assert resp.json["escrow"]["amount"] == 4.0

    def test_escrow_released_on_complete(self, app):
        r = app.post("/relic/reserve", json={
            "agent_id": "escrow_rel", "machine_id": "riscv-hifive",
            "duration_hours": 1, "rtc_amount": 10.0,
        })
        sid = r.json["session_id"]
        app.post(f"/relic/complete/{sid}", headers=admin_headers())
        sr = app.get(f"/relic/reservation/{sid}")
        assert sr.json["escrow"]["status"] == "released"
        assert sr.json["escrow"]["release_reason"] == "completed"

    def test_escrow_released_on_timeout(self, app):
        from tools.rent_a_relic import server
        r = app.post("/relic/reserve", json={
            "agent_id": "escrow_to", "machine_id": "alpha-ds20",
            "duration_hours": 1, "rtc_amount": 7.0,
        })
        sid = r.json["session_id"]
        # Force expiry
        conn = sqlite3.connect(server.app.config["DB_PATH"])
        conn.execute("UPDATE reservations SET expires_at=? WHERE session_id=?",
                     (time.time() - 1, sid))
        conn.commit()
        conn.close()
        # Trigger sweep
        app.get("/relic/available")
        sr = app.get(f"/relic/reservation/{sid}")
        assert sr.json["status"] == "expired"
        assert sr.json["escrow"]["release_reason"] == "timeout"


class TestProvenanceReceipts:
    def test_generate_and_verify(self, machine, reservation):
        receipt = generate_receipt(machine, reservation)
        assert receipt.machine_passport_id == machine.passport_id()
        assert receipt.session_id == reservation.session_id
        assert verify_receipt(receipt) is True

    def test_tampered_output_hash_fails_verify(self, machine, reservation):
        receipt = generate_receipt(machine, reservation)
        receipt.output_hash = "deadbeef" * 8
        assert verify_receipt(receipt) is False

    def test_tampered_signature_fails_verify(self, machine, reservation):
        receipt = generate_receipt(machine, reservation)
        receipt.ed25519_signature = "00" * 64
        assert verify_receipt(receipt) is False

    def test_receipt_has_all_fields(self, machine, reservation):
        d = generate_receipt(machine, reservation).to_dict()
        required = {"receipt_id", "session_id", "machine_passport_id", "agent_id",
                    "machine_id", "duration_hours", "output_hash", "attestation_proof",
                    "ed25519_signature", "public_key_hex", "timestamp"}
        assert required.issubset(d.keys())

    def test_receipt_endpoint(self, app):
        r = app.post("/relic/reserve", json={
            "agent_id": "receipt_a", "machine_id": "g5-dual",
            "duration_hours": 1, "rtc_amount": 8.0,
        })
        assert r.status_code == 201
        rr = app.get(f"/relic/receipt/{r.json['session_id']}")
        assert rr.status_code == 200
        assert rr.json["verified"] is True
        assert len(rr.json["ed25519_signature"]) == 128

    def test_receipt_cached_on_second_request(self, app):
        r = app.post("/relic/reserve", json={
            "agent_id": "cache_a", "machine_id": "sparc-ultra",
            "duration_hours": 1, "rtc_amount": 6.0,
        })
        sid = r.json["session_id"]
        r1 = app.get(f"/relic/receipt/{sid}")
        r2 = app.get(f"/relic/receipt/{sid}")
        assert r1.status_code == 200
        assert r1.json["receipt_id"] == r2.json["receipt_id"]


class TestAvailabilityWindows:
    def test_available_endpoint(self, app):
        resp = app.get("/relic/available")
        assert resp.status_code == 200
        for m in resp.json["machines"]:
            slots = {w["slot_hours"] for w in m["availability_windows"]}
            assert slots == {1, 4, 24}

    def test_reserved_machine_not_in_available(self, app):
        app.post("/relic/reserve", json={
            "agent_id": "avail_a", "machine_id": "g3-beige",
            "duration_hours": 1, "rtc_amount": 4.0,
        })
        ids = [m["machine_id"] for m in app.get("/relic/available").json["machines"]]
        assert "g3-beige" not in ids

    def test_window_start_end_ordering(self, app):
        for m in app.get("/relic/available").json["machines"]:
            for w in m["availability_windows"]:
                assert w["end_epoch"] > w["start_epoch"]
                diff_h = (w["end_epoch"] - w["start_epoch"]) / 3600
                assert abs(diff_h - w["slot_hours"]) < 0.1


class TestLeaderboard:
    def test_leaderboard_endpoint(self, app):
        resp = app.get("/relic/leaderboard")
        assert resp.status_code == 200
        assert len(resp.json["leaderboard"]) == len(MACHINE_REGISTRY)

    def test_leaderboard_rank_ordering(self, app):
        for i in range(2):
            r = app.post("/relic/reserve", json={
                "agent_id": f"lb_{i}", "machine_id": "g4-quicksilver",
                "duration_hours": 1, "rtc_amount": 5.0,
            })
            if r.status_code == 201:
                app.post(f"/relic/complete/{r.json['session_id']}", headers=admin_headers())
        ranks = [e["rank"] for e in app.get("/relic/leaderboard").json["leaderboard"]]
        assert ranks == sorted(ranks)

    def test_leaderboard_has_required_fields(self, app):
        for entry in app.get("/relic/leaderboard").json["leaderboard"]:
            for key in ["rank", "machine_id", "name", "total_reservations", "total_rtc_earned"]:
                assert key in entry
