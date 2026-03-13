"""
RustChain API Load Test Suite (Locust)

Usage:
    # Install dependencies
    pip install -r locust-requirements.txt
    
    # Run with web UI
    locust -f locust-load-test.py --host=https://rustchain.org
    
    # Run headless
    locust -f locust-load-test.py --host=https://rustchain.org --headless \
        -u 10 -r 2 --run-time 5m --html=locust-report.html
    
    # Run with custom configuration
    locust -f locust-load-test.py --host=$TARGET_URL --headless \
        -u $USERS -r $SPAWN_RATE --run-time $DURATION

Environment Variables:
    TARGET_URL    - API base URL (default: https://rustchain.org)
    MINER_ID      - Miner wallet ID for testing (default: scott)
"""

import os
import json
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner, WorkerRunner


class RustChainAPIUser(HttpUser):
    """
    Locust user class for RustChain API load testing.
    Simulates a client making various API calls.
    """
    
    # Wait time between tasks (1-3 seconds)
    wait_time = between(1, 3)
    
    # Disable SSL verification for self-signed certificates
    verify = False
    
    def on_start(self):
        """Called when a simulated user starts"""
        self.miner_id = os.environ.get('MINER_ID', 'scott')
        self.base_url = self.host or 'https://rustchain.org'
        
    @task(5)
    def test_health(self):
        """Test the /health endpoint - high frequency"""
        with self.client.get(
            "/health",
            name="GET /health",
            catch_response=True
        ) as response:
            try:
                data = response.json()
                if response.status_code == 200 and data.get('ok') is True:
                    response.success()
                else:
                    response.failure(f"Health check failed: {data}")
            except json.JSONDecodeError:
                response.failure("Invalid JSON response")
    
    @task(4)
    def test_epoch(self):
        """Test the /epoch endpoint - high frequency"""
        with self.client.get(
            "/epoch",
            name="GET /epoch",
            catch_response=True
        ) as response:
            try:
                data = response.json()
                if response.status_code == 200 and 'epoch' in data:
                    response.success()
                else:
                    response.failure(f"Epoch check failed: {data}")
            except json.JSONDecodeError:
                response.failure("Invalid JSON response")
    
    @task(4)
    def test_miners(self):
        """Test the /api/miners endpoint - high frequency"""
        with self.client.get(
            "/api/miners",
            name="GET /api/miners",
            catch_response=True
        ) as response:
            try:
                data = response.json()
                if response.status_code == 200 and isinstance(data, list):
                    response.success()
                else:
                    response.failure(f"Miners check failed: {data}")
            except json.JSONDecodeError:
                response.failure("Invalid JSON response")
    
    @task(3)
    def test_balance(self):
        """Test the /wallet/balance endpoint - medium frequency"""
        with self.client.get(
            f"/wallet/balance?miner_id={self.miner_id}",
            name="GET /wallet/balance",
            catch_response=True
        ) as response:
            try:
                data = response.json()
                if response.status_code == 200 and 'ok' in data:
                    response.success()
                else:
                    response.failure(f"Balance check failed: {data}")
            except json.JSONDecodeError:
                response.failure("Invalid JSON response")
    
    @task(3)
    def test_ready(self):
        """Test the /ready endpoint - medium frequency"""
        with self.client.get(
            "/ready",
            name="GET /ready",
            catch_response=True
        ) as response:
            try:
                data = response.json()
                if response.status_code == 200 and data.get('ready') is True:
                    response.success()
                else:
                    response.failure(f"Ready check failed: {data}")
            except json.JSONDecodeError:
                response.failure("Invalid JSON response")
    
    @task(2)
    def test_nodes(self):
        """Test the /api/nodes endpoint - lower frequency"""
        with self.client.get(
            "/api/nodes",
            name="GET /api/nodes",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Nodes check failed: {response.status_code}")
    
    @task(2)
    def test_governance(self):
        """Test the /governance/proposals endpoint - lower frequency"""
        with self.client.get(
            "/governance/proposals",
            name="GET /governance/proposals",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Governance check failed: {response.status_code}")
    
    @task(1)
    def test_lottery_eligibility(self):
        """Test the /lottery/eligibility endpoint - low frequency"""
        with self.client.get(
            f"/lottery/eligibility?miner_id={self.miner_id}",
            name="GET /lottery/eligibility",
            catch_response=True
        ) as response:
            try:
                data = response.json()
                if response.status_code == 200 and 'eligible' in data:
                    response.success()
                else:
                    response.failure(f"Eligibility check failed: {data}")
            except json.JSONDecodeError:
                response.failure("Invalid JSON response")


class HeavyLoadUser(HttpUser):
    """
    Heavy load user - more aggressive request patterns.
    Use this for stress testing.
    """
    
    wait_time = between(0.1, 0.5)
    verify = False
    
    @task
    def rapid_health_check(self):
        """Rapid health checks for stress testing"""
        self.client.get("/health", name="GET /health [stress]")
    
    @task
    def rapid_epoch_check(self):
        """Rapid epoch checks for stress testing"""
        self.client.get("/epoch", name="GET /epoch [stress]")


class WriteLoadUser(HttpUser):
    """
    User class for testing write operations (if available).
    Note: Most write operations require authentication.
    """
    
    wait_time = between(2, 5)
    verify = False
    
    @task
    def test_attest_submit(self):
        """Test attestation submission (will fail without valid signature)"""
        payload = {
            "miner_id": os.environ.get('MINER_ID', 'scott'),
            "timestamp": 1771187406,
            "device_info": {
                "arch": "x86_64",
                "family": "test"
            },
            "fingerprint": {
                "clock_skew": {"drift_ppm": 24.3, "jitter_ns": 1247},
                "cache_timing": {"l1_latency_ns": 5, "l2_latency_ns": 15}
            },
            "signature": "test_signature_placeholder"
        }

        with self.client.post(
            "/attest/submit",
            json=payload,
            name="POST /attest/submit",
            catch_response=True
        ) as response:
            # This is expected to fail without valid signature
            # We're testing the endpoint availability and response format
            if response.status_code in [200, 400, 401]:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")


# Event handlers for custom reporting
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when load test starts"""
    print(f"\n{'='*60}")
    print("RustChain API Load Test Starting")
    print(f"{'='*60}")
    print(f"Target URL: {environment.host or 'https://rustchain.org'}")
    print(f"Miner ID: {os.environ.get('MINER_ID', 'scott')}")
    print(f"{'='*60}\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when load test stops"""
    stats = environment.stats
    
    print(f"\n{'='*60}")
    print("RustChain API Load Test Complete")
    print(f"{'='*60}")
    print(f"Total Requests: {stats.total.num_requests}")
    print(f"Total Failures: {stats.total.num_failures}")
    print(f"Failure Rate: {(stats.total.num_failures / max(stats.total.num_requests, 1)) * 100:.2f}%")
    print(f"Average Response Time: {stats.total.avg_response_time:.2f}ms")
    print(f"Requests/sec: {stats.total.current_rps:.2f}")
    print(f"{'='*60}\n")


# Configuration for running without web UI
def setup_locust_config():
    """
    Setup configuration for headless runs.
    Can be imported and used in custom scripts.
    """
    return {
        'host': os.environ.get('TARGET_URL', 'https://rustchain.org'),
        'users': int(os.environ.get('USERS', '10')),
        'spawn_rate': int(os.environ.get('SPAWN_RATE', '2')),
        'run_time': os.environ.get('DURATION', '5m'),
    }


# For programmatic usage
if __name__ == "__main__":
    import subprocess
    import sys
    
    config = setup_locust_config()
    
    cmd = [
        sys.executable, "-m", "locust",
        "-f", __file__,
        "--host", config['host'],
        "--headless",
        "-u", str(config['users']),
        "-r", str(config['spawn_rate']),
        "--run-time", config['run_time'],
        "--html", "locust-report.html",
        "--json", "locust-results.json"
    ]
    
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd)
