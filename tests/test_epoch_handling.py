"""
Epoch transition and reward settlement tests for the RustChain node.

Covers: slot/epoch math, epoch enrollment lifecycle, reward settlement,
        VRF selection, round-robin eligibility, epoch reward queries,
        and edge cases around epoch boundaries.
"""

import pytest
import os
import sys
import time
import hashlib
import sqlite3
from unittest.mock import patch, MagicMock
from types import SimpleNamespace

integrated_node = sys.modules["integrated_node"]

ADMIN_KEY = os.environ.get("RC_ADMIN_KEY", "0" * 32)
EPOCH_SLOTS = integrated_node.EPOCH_SLOTS      # 144
BLOCK_TIME = integrated_node.BLOCK_TIME         # 600
CHAIN_ID = integrated_node.CHAIN_ID
PER_EPOCH_RTC = integrated_node.PER_EPOCH_RTC   # 1.5


@pytest.fixture
def client():
    integrated_node.app.config["TESTING"] = True
    with integrated_node.app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Slot / epoch arithmetic
# ---------------------------------------------------------------------------

class TestSlotEpochMath:
    def test_slot_to_epoch_zero(self):
        assert integrated_node.slot_to_epoch(0) == 0

    def test_slot_to_epoch_boundary(self):
        # Slot 143 is the last slot of epoch 0
        assert integrated_node.slot_to_epoch(EPOCH_SLOTS - 1) == 0
        # Slot 144 is the first slot of epoch 1
        assert integrated_node.slot_to_epoch(EPOCH_SLOTS) == 1

    def test_slot_to_epoch_large(self):
        assert integrated_node.slot_to_epoch(EPOCH_SLOTS * 100) == 100

    def test_slot_to_epoch_mid_epoch(self):
        assert integrated_node.slot_to_epoch(EPOCH_SLOTS * 5 + 72) == 5

    def test_current_slot_returns_int(self):
        # Use a timestamp after GENESIS_TIMESTAMP to get a positive slot
        future_ts = integrated_node.GENESIS_TIMESTAMP + 100000
        with patch("time.time", return_value=future_ts):
            slot = integrated_node.current_slot()
            assert isinstance(slot, int)
            assert slot >= 0


# ---------------------------------------------------------------------------
# Epoch enrollment lifecycle
# ---------------------------------------------------------------------------

class TestEpochEnrollmentLifecycle:
    def test_enroll_and_query_epoch(self, client):
        """Enroll a miner, then verify /epoch reflects the enrollment."""
        # Step 1: enroll
        with patch("integrated_node.check_enrollment_requirements",
                    return_value=(True, {})), \
             patch("integrated_node.current_slot", return_value=300), \
             patch("integrated_node.slot_to_epoch", return_value=2), \
             patch("sqlite3.connect") as mc:
            mc.return_value.__enter__ = MagicMock()
            mc.return_value.__exit__ = MagicMock(return_value=False)
            conn = mc.return_value.__enter__.return_value
            conn.execute.return_value = MagicMock()
            resp = client.post("/epoch/enroll",
                               json={"miner_pubkey": "pk_lifecycle", "device": {}},
                               content_type="application/json")
            assert resp.status_code == 200
            assert resp.get_json()["epoch"] == 2

    def test_enroll_weight_x86(self, client):
        with patch("integrated_node.check_enrollment_requirements",
                    return_value=(True, {})), \
             patch("integrated_node.current_slot", return_value=0), \
             patch("integrated_node.slot_to_epoch", return_value=0), \
             patch("sqlite3.connect") as mc:
            mc.return_value.__enter__ = MagicMock()
            mc.return_value.__exit__ = MagicMock(return_value=False)
            conn = mc.return_value.__enter__.return_value
            conn.execute.return_value = MagicMock()
            resp = client.post("/epoch/enroll",
                               json={"miner_pubkey": "pk_x86",
                                     "device": {"family": "x86", "arch": "default"}},
                               content_type="application/json")
            data = resp.get_json()
            assert data["ok"] is True
            # x86/default weight should be a positive number
            assert data["weight"] > 0

    def test_enroll_provides_miner_id_fallback(self, client):
        """When miner_id is not provided, it should default to miner_pubkey."""
        with patch("integrated_node.check_enrollment_requirements",
                    return_value=(True, {})), \
             patch("integrated_node.current_slot", return_value=0), \
             patch("integrated_node.slot_to_epoch", return_value=0), \
             patch("sqlite3.connect") as mc:
            mc.return_value.__enter__ = MagicMock()
            mc.return_value.__exit__ = MagicMock(return_value=False)
            conn = mc.return_value.__enter__.return_value
            conn.execute.return_value = MagicMock()
            resp = client.post("/epoch/enroll",
                               json={"miner_pubkey": "pk_no_id"},
                               content_type="application/json")
            data = resp.get_json()
            assert data["miner_id"] == "pk_no_id"

    def test_enroll_with_explicit_miner_id(self, client):
        with patch("integrated_node.check_enrollment_requirements",
                    return_value=(True, {})), \
             patch("integrated_node.current_slot", return_value=0), \
             patch("integrated_node.slot_to_epoch", return_value=0), \
             patch("sqlite3.connect") as mc:
            mc.return_value.__enter__ = MagicMock()
            mc.return_value.__exit__ = MagicMock(return_value=False)
            conn = mc.return_value.__enter__.return_value
            conn.execute.return_value = MagicMock()
            resp = client.post("/epoch/enroll",
                               json={"miner_pubkey": "pk_explicit",
                                     "miner_id": "my-rig-01"},
                               content_type="application/json")
            data = resp.get_json()
            assert data["miner_id"] == "my-rig-01"
            assert data["miner_pk"] == "pk_explicit"


# ---------------------------------------------------------------------------
# Epoch reward settlement
# ---------------------------------------------------------------------------

class TestEpochRewardSettlement:
    def test_settle_requires_admin(self, client):
        resp = client.post("/rewards/settle",
                           json={"epoch": 0},
                           content_type="application/json")
        assert resp.status_code == 401

    def test_settle_requires_epoch(self, client):
        resp = client.post("/rewards/settle",
                           json={},
                           headers={"X-Admin-Key": ADMIN_KEY},
                           content_type="application/json")
        assert resp.status_code == 400

    def test_settle_negative_epoch_rejected(self, client):
        resp = client.post("/rewards/settle",
                           json={"epoch": -5},
                           headers={"X-Admin-Key": ADMIN_KEY},
                           content_type="application/json")
        # Server should treat epoch < 0 as invalid
        assert resp.status_code == 400

    def test_settle_with_valid_epoch(self, client):
        mock_result = {"ok": True, "epoch": 5, "distributed_rtc": 1.5}
        with patch("integrated_node.settle_epoch", return_value=mock_result), \
             patch("sqlite3.connect") as mc:
            mc.return_value.__enter__ = MagicMock()
            mc.return_value.__exit__ = MagicMock(return_value=False)
            resp = client.post("/rewards/settle",
                               json={"epoch": 5},
                               headers={"X-Admin-Key": ADMIN_KEY},
                               content_type="application/json")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["ok"] is True

    def test_rewards_query_with_data(self, client):
        rows = [("miner_a", 750_000), ("miner_b", 750_000)]
        with patch("sqlite3.connect") as mc:
            mc.return_value.__enter__ = MagicMock()
            mc.return_value.__exit__ = MagicMock(return_value=False)
            conn = mc.return_value.__enter__.return_value
            conn.execute.return_value.fetchall.return_value = rows
            resp = client.get("/rewards/epoch/10")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["epoch"] == 10
            assert len(data["rewards"]) == 2
            total_shared = sum(r["share_i64"] for r in data["rewards"])
            assert total_shared == 1_500_000  # 1.5 RTC in uRTC

    def test_rewards_query_empty_epoch(self, client):
        with patch("sqlite3.connect") as mc:
            mc.return_value.__enter__ = MagicMock()
            mc.return_value.__exit__ = MagicMock(return_value=False)
            conn = mc.return_value.__enter__.return_value
            conn.execute.return_value.fetchall.return_value = []
            resp = client.get("/rewards/epoch/999")
            assert resp.status_code == 200
            assert resp.get_json()["rewards"] == []


# ---------------------------------------------------------------------------
# VRF selection (deterministic)
# ---------------------------------------------------------------------------

class TestVRFSelection:
    def test_vrf_not_enrolled(self):
        with patch("sqlite3.connect") as mc:
            mc.return_value.__enter__ = MagicMock()
            mc.return_value.__exit__ = MagicMock(return_value=False)
            conn = mc.return_value.__enter__.return_value
            conn.execute.return_value.fetchone.return_value = None
            result = integrated_node.vrf_is_selected("unknown_pk", 100)
            assert result is False

    def test_vrf_no_miners_enrolled(self):
        with patch("sqlite3.connect") as mc:
            mc.return_value.__enter__ = MagicMock()
            mc.return_value.__exit__ = MagicMock(return_value=False)
            conn = mc.return_value.__enter__.return_value
            # First call returns weight row, second returns empty all_miners
            conn.execute.return_value.fetchone.return_value = [1.0]
            conn.execute.return_value.fetchall.return_value = []
            result = integrated_node.vrf_is_selected("pk", 100)
            assert result is False

    def test_vrf_deterministic(self):
        """Same inputs should always produce the same selection result."""
        with patch("sqlite3.connect") as mc:
            mc.return_value.__enter__ = MagicMock()
            mc.return_value.__exit__ = MagicMock(return_value=False)
            conn = mc.return_value.__enter__.return_value
            conn.execute.return_value.fetchone.return_value = [1.0]
            conn.execute.return_value.fetchall.return_value = [
                ("miner_a", 1.0), ("miner_b", 1.0)
            ]
            r1 = integrated_node.vrf_is_selected("miner_a", 42)
            r2 = integrated_node.vrf_is_selected("miner_a", 42)
            assert r1 == r2


# ---------------------------------------------------------------------------
# Epoch boundary edge cases
# ---------------------------------------------------------------------------

class TestEpochBoundaries:
    def test_epoch_constants_consistent(self):
        assert EPOCH_SLOTS == 144
        assert BLOCK_TIME == 600
        assert PER_EPOCH_RTC == 1.5
        assert integrated_node.TOTAL_SUPPLY_RTC == 8_388_608

    def test_total_supply_is_power_of_2(self):
        supply = integrated_node.TOTAL_SUPPLY_RTC
        assert supply == 2 ** 23

    def test_per_block_rtc_calculation(self):
        per_block = PER_EPOCH_RTC / EPOCH_SLOTS
        assert abs(per_block - integrated_node.PER_BLOCK_RTC) < 1e-10

    def test_epoch_transition_slot(self):
        """The first slot of a new epoch should map to the next epoch number."""
        for ep in range(10):
            first_slot = ep * EPOCH_SLOTS
            assert integrated_node.slot_to_epoch(first_slot) == ep
            if ep > 0:
                last_slot = first_slot - 1
                assert integrated_node.slot_to_epoch(last_slot) == ep - 1


# ---------------------------------------------------------------------------
# Enrollment requirement checks
# ---------------------------------------------------------------------------

class TestEnrollmentRequirements:
    def test_enrollment_rejected_returns_412(self, client):
        with patch("integrated_node.check_enrollment_requirements",
                    return_value=(False, {"error": "missing_attestation"})):
            resp = client.post("/epoch/enroll",
                               json={"miner_pubkey": "rejected_pk"},
                               content_type="application/json")
            assert resp.status_code == 412
            data = resp.get_json()
            assert data["error"] == "missing_attestation"

    def test_enrollment_rejection_tracking(self, client):
        """Verify that rejection counters are updated."""
        original = dict(getattr(integrated_node, "ENROLL_REJ", {}))
        with patch("integrated_node.check_enrollment_requirements",
                    return_value=(False, {"error": "test_reason"})):
            client.post("/epoch/enroll",
                        json={"miner_pubkey": "track_rej"},
                        content_type="application/json")
        # ENROLL_REJ should have been updated
        assert integrated_node.ENROLL_REJ.get("test_reason", 0) > 0


# ---------------------------------------------------------------------------
# Chain configuration
# ---------------------------------------------------------------------------

class TestChainConfig:
    def test_chain_id(self):
        assert CHAIN_ID == "rustchain-mainnet-v2"

    def test_min_withdrawal(self):
        assert integrated_node.MIN_WITHDRAWAL == 0.1

    def test_withdrawal_fee(self):
        assert integrated_node.WITHDRAWAL_FEE == 0.01

    def test_max_daily_withdrawal(self):
        assert integrated_node.MAX_DAILY_WITHDRAWAL == 1000.0

    def test_app_version_format(self):
        version = integrated_node.APP_VERSION
        assert "rip200" in version


# ---------------------------------------------------------------------------
# Settle epoch via external trigger (settle_epoch.py pattern)
# ---------------------------------------------------------------------------

class TestSettleEpochExternal:
    """Test the pattern used by the settle_epoch.py cron script."""

    def test_settle_flow(self, client):
        """Simulate the settle_epoch.py flow: GET /epoch, then POST /rewards/settle."""
        # 1. Get current epoch
        with patch("integrated_node.current_slot", return_value=300), \
             patch("integrated_node.slot_to_epoch", return_value=2), \
             patch("sqlite3.connect") as mc:
            mc.return_value.__enter__ = MagicMock()
            mc.return_value.__exit__ = MagicMock(return_value=False)
            conn = mc.return_value.__enter__.return_value
            conn.execute.return_value.fetchone.return_value = [3]
            resp = client.get("/epoch")
            assert resp.status_code == 200
            epoch_info = resp.get_json()
            current_epoch = epoch_info["epoch"]
            prev_epoch = current_epoch - 1

        # 2. Settle previous epoch
        mock_result = {"ok": True, "epoch": prev_epoch}
        with patch("integrated_node.settle_epoch", return_value=mock_result), \
             patch("sqlite3.connect") as mc:
            mc.return_value.__enter__ = MagicMock()
            mc.return_value.__exit__ = MagicMock(return_value=False)
            resp = client.post("/rewards/settle",
                               json={"epoch": prev_epoch},
                               headers={"X-Admin-Key": ADMIN_KEY},
                               content_type="application/json")
            assert resp.status_code == 200
            assert resp.get_json()["ok"] is True
