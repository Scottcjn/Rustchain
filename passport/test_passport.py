# SPDX-License-Identifier: MIT
"""Unit tests for RustChain Machine Passport Ledger (Bounty #2309)."""

import json
import os
import tempfile
import pytest

from passport_ledger import (
    MachinePassport,
    PassportLedger,
    RepairEntry,
    BenchmarkSignature,
    AttestationHistory,
)
from passport_server import app


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def tmp_ledger(tmp_path):
    return PassportLedger(data_dir=str(tmp_path))


@pytest.fixture
def sample_passport():
    return MachinePassport(
        machine_id="a3f8c92e1b7d04e5deadbeef",
        name="Old Faithful",
        manufacture_year=2004,
        architecture="G4",
        cpu_model="PowerPC G4 7447A",
        rom_hash="abc123def456",
        provenance="eBay lot #4521",
        owner_address="RTC2fe3c33c77666ff76a1cd0999fd4466ee81250ff",
        attestation_history=AttestationHistory(
            first_seen_epoch=100,
            last_seen_epoch=5000,
            total_epochs=4200,
            total_rtc_earned=1050.5,
            multiplier=2.5,
        ),
    )


@pytest.fixture
def client(tmp_path):
    os.environ["PASSPORT_DATA_DIR"] = str(tmp_path)
    app.config["TESTING"] = True
    # Re-init ledger
    from passport_server import ledger
    ledger.__init__(data_dir=str(tmp_path))
    with app.test_client() as c:
        yield c


# ── MachinePassport Tests ─────────────────────────────────────────

class TestMachinePassport:
    def test_create_passport(self, sample_passport):
        assert sample_passport.machine_id == "a3f8c92e1b7d04e5deadbeef"
        assert sample_passport.name == "Old Faithful"
        assert sample_passport.architecture == "G4"

    def test_hardware_age(self, sample_passport):
        age = sample_passport.hardware_age()
        assert age == 2026 - 2004  # 22 years

    def test_tier_vintage(self, sample_passport):
        assert sample_passport.tier() == "vintage"  # 22 years = vintage (20-24)

    def test_tier_ancient(self):
        p = MachinePassport(machine_id="test", manufacture_year=1990)
        assert p.tier() == "ancient"  # 36 years

    def test_tier_recent(self):
        p = MachinePassport(machine_id="test", manufacture_year=2024)
        assert p.tier() == "recent"

    def test_add_repair(self, sample_passport):
        sample_passport.add_repair("2024-03-15", "Replaced PRAM battery", parts=["CR2032"])
        assert len(sample_passport.repair_log) == 1
        assert sample_passport.repair_log[0].description == "Replaced PRAM battery"
        assert "CR2032" in sample_passport.repair_log[0].parts

    def test_add_benchmark(self, sample_passport):
        sig = BenchmarkSignature(
            cache_timing_profile={"l1": 1.2, "l2": 4.8},
            simd_identity={"altivec": True},
            clock_drift_hash="abc123",
        )
        sample_passport.add_benchmark(sig)
        assert len(sample_passport.benchmark_signatures) == 1
        assert sample_passport.benchmark_signatures[0].collected_at != ""

    def test_passport_hash_deterministic(self, sample_passport):
        h1 = sample_passport.compute_passport_hash()
        h2 = sample_passport.compute_passport_hash()
        assert h1 == h2
        assert len(h1) == 64  # SHA-256

    def test_passport_hash_changes_on_repair(self, sample_passport):
        h_before = sample_passport.compute_passport_hash()
        sample_passport.add_repair("2025-01-01", "Recapped PSU")
        h_after = sample_passport.compute_passport_hash()
        assert h_before != h_after

    def test_to_json_and_back(self, sample_passport):
        sample_passport.add_repair("2024-03-15", "Test repair")
        json_str = sample_passport.to_json()
        restored = MachinePassport.from_json(json_str)
        assert restored.machine_id == sample_passport.machine_id
        assert restored.name == sample_passport.name
        assert len(restored.repair_log) == 1

    def test_to_dict(self, sample_passport):
        d = sample_passport.to_dict()
        assert isinstance(d, dict)
        assert d["machine_id"] == "a3f8c92e1b7d04e5deadbeef"
        assert d["attestation_history"]["total_rtc_earned"] == 1050.5


# ── PassportLedger Tests ──────────────────────────────────────────

class TestPassportLedger:
    def test_save_and_get(self, tmp_ledger, sample_passport):
        h = tmp_ledger.save(sample_passport)
        assert len(h) == 64
        retrieved = tmp_ledger.get(sample_passport.machine_id)
        assert retrieved is not None
        assert retrieved.name == "Old Faithful"

    def test_list_all(self, tmp_ledger, sample_passport):
        tmp_ledger.save(sample_passport)
        ids = tmp_ledger.list_all()
        assert sample_passport.machine_id in ids

    def test_count(self, tmp_ledger, sample_passport):
        assert tmp_ledger.count == 0
        tmp_ledger.save(sample_passport)
        assert tmp_ledger.count == 1

    def test_get_nonexistent(self, tmp_ledger):
        assert tmp_ledger.get("nonexistent") is None

    def test_delete(self, tmp_ledger, sample_passport):
        tmp_ledger.save(sample_passport)
        assert tmp_ledger.delete(sample_passport.machine_id) is True
        assert tmp_ledger.get(sample_passport.machine_id) is None
        assert tmp_ledger.count == 0

    def test_search_by_architecture(self, tmp_ledger, sample_passport):
        tmp_ledger.save(sample_passport)
        results = tmp_ledger.search(architecture="G4")
        assert len(results) == 1
        assert results[0].name == "Old Faithful"

    def test_search_by_name(self, tmp_ledger, sample_passport):
        tmp_ledger.save(sample_passport)
        results = tmp_ledger.search(name="faithful")
        assert len(results) == 1

    def test_search_no_results(self, tmp_ledger, sample_passport):
        tmp_ledger.save(sample_passport)
        results = tmp_ledger.search(architecture="SPARC")
        assert len(results) == 0


# ── API Tests ─────────────────────────────────────────────────────

class TestAPI:
    def test_index_page(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_api_list_empty(self, client):
        resp = client.get("/api/passports")
        assert resp.status_code == 200
        assert json.loads(resp.data) == []

    def test_api_create_passport(self, client):
        resp = client.post("/api/passport", json={
            "machine_id": "test123",
            "name": "Test Machine",
            "architecture": "G4",
            "manufacture_year": 2003,
        })
        assert resp.status_code == 201
        data = json.loads(resp.data)
        assert "passport_hash" in data

    def test_api_get_passport(self, client):
        client.post("/api/passport", json={
            "machine_id": "test456",
            "name": "Relic",
            "architecture": "SPARC",
            "manufacture_year": 1998,
        })
        resp = client.get("/api/passport/test456")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["name"] == "Relic"
        assert data["tier"] == "sacred"
        assert "passport_hash" in data

    def test_api_get_404(self, client):
        resp = client.get("/api/passport/nonexistent")
        assert resp.status_code == 404

    def test_api_add_repair(self, client):
        client.post("/api/passport", json={"machine_id": "repair-test", "name": "Fixme"})
        resp = client.post("/api/passport/repair-test/repair", json={
            "date": "2025-01-15",
            "description": "Recapped PSU",
            "parts": ["100uF", "220uF"],
        })
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["repairs"] == 1

    def test_api_add_benchmark(self, client):
        client.post("/api/passport", json={"machine_id": "bench-test", "name": "Benchy"})
        resp = client.post("/api/passport/bench-test/benchmark", json={
            "cache_timing_profile": {"l1": 1.5, "l2": 5.0},
            "clock_drift_hash": "abc",
        })
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["benchmarks"] == 1

    def test_api_search(self, client):
        client.post("/api/passport", json={"machine_id": "s1", "name": "Alpha", "architecture": "G4"})
        client.post("/api/passport", json={"machine_id": "s2", "name": "Beta", "architecture": "SPARC"})
        resp = client.get("/api/search?architecture=G4")
        data = json.loads(resp.data)
        assert len(data) == 1
        assert data[0]["name"] == "Alpha"

    def test_api_update_passport(self, client):
        client.post("/api/passport", json={"machine_id": "upd1", "name": "Before"})
        resp = client.post("/api/passport", json={"machine_id": "upd1", "name": "After"})
        assert resp.status_code == 201
        get_resp = client.get("/api/passport/upd1")
        data = json.loads(get_resp.data)
        assert data["name"] == "After"

    def test_api_create_requires_machine_id(self, client):
        resp = client.post("/api/passport", json={"name": "No ID"})
        assert resp.status_code == 400

    def test_api_json_routes_reject_non_object_bodies(self, client):
        client.post("/api/passport", json={"machine_id": "json-test", "name": "JSON Test"})

        routes = (
            "/api/passport",
            "/api/passport/json-test/repair",
            "/api/passport/json-test/benchmark",
        )

        for route in routes:
            resp = client.post(route, json=["not", "object"])
            assert resp.status_code == 400
            assert resp.get_json() == {"error": "JSON object required"}

    def test_passport_view_page(self, client):
        resp = client.get("/passport/test123")
        assert resp.status_code == 200

    def test_api_list_with_data(self, client):
        client.post("/api/passport", json={
            "machine_id": "list-test",
            "name": "Listed",
            "architecture": "MIPS",
            "manufacture_year": 2000,
        })
        resp = client.get("/api/passports")
        data = json.loads(resp.data)
        assert len(data) >= 1
        assert any(p["machine_id"] == "list-test" for p in data)
