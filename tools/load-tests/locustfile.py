"""
RustChain API Load Test Suite — Locust
=======================================
Targets the five core read endpoints on a RustChain node.

Usage:
    locust -f locustfile.py --host https://50.28.86.131 \
           --users 50 --spawn-rate 5 --run-time 2m \
           --headless --csv results/locust

    Or launch the web UI (default http://localhost:8089):
        locust -f locustfile.py --host https://50.28.86.131
"""

from locust import HttpUser, task, between, events
import urllib3, time, json, os

# The production node uses a self-signed cert
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------------------
# Optional: miner ID for the balance endpoint (override via env var)
# ---------------------------------------------------------------------------
MINER_ID = os.getenv("RUSTCHAIN_MINER_ID", "Ivan-houzhiwen")


class RustChainUser(HttpUser):
    """Simulates a consumer of the RustChain public API."""

    wait_time = between(0.5, 2)

    # ------------------------------------------------------------------
    # Health check — lightweight, always first
    # ------------------------------------------------------------------
    @task(3)
    def health(self):
        with self.client.get("/health", verify=True, catch_response=True) as r:
            if r.status_code == 200:
                body = r.json()
                if body.get("ok") is not True:
                    r.failure("health.ok is not True")
            else:
                r.failure(f"status {r.status_code}")

    # ------------------------------------------------------------------
    # Epoch info
    # ------------------------------------------------------------------
    @task(2)
    def epoch(self):
        with self.client.get("/epoch", verify=True, catch_response=True) as r:
            if r.status_code == 200:
                body = r.json()
                if "epoch" not in body:
                    r.failure("missing 'epoch' key")
            else:
                r.failure(f"status {r.status_code}")

    # ------------------------------------------------------------------
    # Chain tip header
    # ------------------------------------------------------------------
    @task(2)
    def headers_tip(self):
        with self.client.get("/headers/tip", verify=True, catch_response=True) as r:
            if r.status_code != 200:
                r.failure(f"status {r.status_code}")

    # ------------------------------------------------------------------
    # Active miners list
    # ------------------------------------------------------------------
    @task(2)
    def api_miners(self):
        with self.client.get("/api/miners", verify=True, catch_response=True) as r:
            if r.status_code != 200:
                r.failure(f"status {r.status_code}")

    # ------------------------------------------------------------------
    # Wallet balance query
    # ------------------------------------------------------------------
    @task(1)
    def wallet_balance(self):
        with self.client.get(
            f"/wallet/balance?miner_id={MINER_ID}",
            verify=True,
            catch_response=True,
        ) as r:
            if r.status_code == 200:
                body = r.json()
                if "amount_rtc" not in body:
                    r.failure("missing 'amount_rtc' key")
            else:
                r.failure(f"status {r.status_code}")


# ---------------------------------------------------------------------------
# Event hooks — dump a JSON summary when running headless
# ---------------------------------------------------------------------------
@events.quitting.add_listener
def _on_quit(environment, **_kwargs):
    stats = environment.runner.stats
    summary = {
        "total_requests": stats.total.num_requests,
        "total_failures": stats.total.num_failures,
        "avg_response_time_ms": round(stats.total.avg_response_time, 2),
        "median_ms": stats.total.median_response_time,
        "p95_ms": stats.total.get_response_time_percentile(0.95),
        "p99_ms": stats.total.get_response_time_percentile(0.99),
        "requests_per_sec": round(stats.total.current_rps, 2),
    }
    os.makedirs("results", exist_ok=True)
    with open("results/locust_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print("\n=== Locust summary written to results/locust_summary.json ===")
