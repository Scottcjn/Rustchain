# SPDX-License-Identifier: Apache-2.0
"""
RustChain API Load Test Suite
Issue: https://github.com/Scottcjn/rustchain-bounties/issues/1614

Tests read-only endpoints gently (max 10 users).
POST /wallet/transfer/signed is NOT executed — included as a commented mock only.
"""

import json
import time
import random
import urllib3
from locust import HttpUser, task, between, events
from locust.env import Environment

# Suppress SSL warnings — API uses self-signed cert
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Test miner IDs to rotate through for balance checks
TEST_MINER_IDS = [
    "loadtest-benchmark",
]


class RustChainUser(HttpUser):
    """Simulates a typical RustChain API consumer."""

    # Wait 1–3 seconds between tasks — gentle load
    wait_time = between(1, 3)

    # Disable SSL verification for self-signed cert
    def on_start(self) -> None:
        self.client.verify = False

    @task(3)
    def health_check(self) -> None:
        """GET /health — highest frequency, used by monitors."""
        with self.client.get(
            "/health",
            name="GET /health",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if "ok" not in data:
                    resp.failure(f"Missing 'ok' field: {resp.text}")
                else:
                    resp.success()
            else:
                resp.failure(f"HTTP {resp.status_code}")

    @task(2)
    def get_epoch(self) -> None:
        """GET /epoch — chain state info."""
        with self.client.get(
            "/epoch",
            name="GET /epoch",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if "epoch" not in data:
                    resp.failure(f"Missing 'epoch' field: {resp.text}")
                else:
                    resp.success()
            else:
                resp.failure(f"HTTP {resp.status_code}")

    @task(1)
    def get_wallet_balance(self) -> None:
        """GET /wallet/balance — balance lookup."""
        miner_id = random.choice(TEST_MINER_IDS)
        with self.client.get(
            f"/wallet/balance?miner_id={miner_id}",
            name="GET /wallet/balance",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 404):
                # 404 is acceptable — miner may not exist
                resp.success()
            else:
                resp.failure(f"HTTP {resp.status_code}")

    # -------------------------------------------------------------------------
    # MOCK ONLY — Do NOT uncomment in production load tests.
    # POST /wallet/transfer/signed would send real blockchain transactions.
    # -------------------------------------------------------------------------
    # @task(0)
    # def mock_transfer(self) -> None:
    #     """POST /wallet/transfer/signed — NOT executed, mock shape only."""
    #     payload = {
    #         "from": "MOCK_FROM_ADDRESS",
    #         "to": "MOCK_TO_ADDRESS",
    #         "amount": 0.001,
    #         "fee": 0.0001,
    #         "signature": "MOCK_SIGNATURE_NOT_VALID",
    #         "timestamp": int(time.time()),
    #     }
    #     # self.client.post("/wallet/transfer/signed", json=payload)


class RustChainReadHeavyUser(HttpUser):
    """Simulates a read-heavy client (explorer, dashboard)."""

    wait_time = between(0.5, 2)

    def on_start(self) -> None:
        self.client.verify = False

    @task(5)
    def health_check(self) -> None:
        with self.client.get("/health", name="GET /health", catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"HTTP {resp.status_code}")

    @task(3)
    def get_epoch(self) -> None:
        with self.client.get("/epoch", name="GET /epoch", catch_response=True) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"HTTP {resp.status_code}")

    @task(2)
    def get_wallet_balance(self) -> None:
        with self.client.get(
            "/wallet/balance?miner_id=loadtest-benchmark",
            name="GET /wallet/balance",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"HTTP {resp.status_code}")
