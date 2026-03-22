import asyncio
import time
import httpx
import statistics
from typing import List, Dict, Any
from .miner_simulator import MinerSimulator

class StressHarness:
    """Orchestrates high-concurrency stress tests against RustChain node."""

    def __init__(self, node_url: str, concurrency: int = 50, timeout: int = 30):
        self.node_url = node_url.rstrip("/")
        self.concurrency = concurrency
        self.semaphore = asyncio.Semaphore(concurrency)
        self.timeout = timeout
        self.results = []
        self.client = httpx.AsyncClient(verify=False, timeout=timeout)

    async def run_miner_session(self, simulator: MinerSimulator, force_duplicate_id: str = None, malformed: bool = False) -> Dict[str, Any]:
        """Runs a complete attestation lifecycle for a single simulator."""
        if force_duplicate_id:
            simulator.miner_id = force_duplicate_id

        stats = {
            "miner_id": simulator.miner_id,
            "success": False,
            "steps": {},
            "total_time": 0,
            "retries": 0,
            "is_duplicate": force_duplicate_id is not None,
            "is_malformed": malformed
        }
        start_total = time.perf_counter()

        async with self.semaphore:
            try:
                # 1. Get Challenge (with backoff for 429)
                nonce_data = await self._perform_step_with_retry("challenge", f"{self.node_url}/attest/challenge", {}, stats)
                if not nonce_data: return stats
                nonce = nonce_data.get("nonce")

                # 2. Submit Attestation
                payload = simulator.build_malformed_payload(nonce, self.node_url) if malformed else simulator.build_attestation_payload(nonce, self.node_url)
                res = await self._perform_step_with_retry("submit", f"{self.node_url}/attest/submit", payload, stats)

                if malformed:
                    # For malformed, success means the server REJECTED it correctly
                    if res and not res.get("ok"):
                        stats["success"] = True
                        stats["notes"] = "Correctly rejected malformed payload"
                    return stats

                if not res or not res.get("ok"):
                    if res: stats["error"] = f"Submit rejected: {res}"
                    return stats

                # 3. Enroll in Epoch
                enroll_payload = simulator.build_enroll_payload()
                res = await self._perform_step_with_retry("enroll", f"{self.node_url}/epoch/enroll", enroll_payload, stats)
                if res and res.get("ok"):
                    stats["success"] = True
                else:
                    if res: stats["error"] = f"Enroll failed: {res}"

            except Exception as e:
                stats["error"] = str(e)
            finally:
                stats["total_time"] = time.perf_counter() - start_total

        return stats

    async def _perform_step_with_retry(self, name: str, url: str, payload: Any, stats: dict) -> Any:
        """Helper to perform a step with exponential backoff for 429 errors."""
        max_retries = 5
        backoff = 2 # seconds

        for i in range(max_retries):
            step_start = time.perf_counter()
            try:
                if isinstance(payload, str):
                    # Handle raw string for corrupt JSON testing
                    resp = await self.client.post(url, content=payload, headers={"Content-Type": "application/json"})
                else:
                    resp = await self.client.post(url, json=payload)

                stats["steps"][name] = stats["steps"].get(name, 0) + (time.perf_counter() - step_start)

                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code in [400, 403]:
                    # Correct rejection for malformed/security checks
                    return resp.json()
                elif resp.status_code == 429:
                    stats["retries"] += 1
                    # print(f"  [429] {stats['miner_id']} rate limited on {name}, retrying in {backoff}s...")
                    await asyncio.sleep(backoff)
                    backoff *= 2
                else:
                    stats["error"] = f"HTTP {resp.status_code}: {resp.text[:50]}"
                    return None
            except Exception as e:
                stats["error"] = str(e)
                return None

        stats["error"] = "Max retries exceeded (429)"
        return None

    async def run_test(self, num_miners: int, duplicate_ratio: float = 0.0, test_malformed: bool = False, test_epoch_boundary: bool = False):
        """Launches a massive attack with the specified number of miners."""
        print(f"🚀 Starting stress test with {num_miners} simulated miners...")
        print(f"   Target: {self.node_url}")
        print(f"   Concurrency Limit: {self.concurrency}")

        simulators = [MinerSimulator() for _ in range(num_miners)]

        # Setup scenarios
        force_ids = [None] * num_miners
        malformed_flags = [False] * num_miners

        if duplicate_ratio > 0:
            num_dupes = int(num_miners * duplicate_ratio)
            base_id = f"duplicate-miner-{uuid.uuid4().hex[:4]}"
            for i in range(num_dupes):
                force_ids[i] = base_id

        if test_malformed:
            # Make 20% of miners send malformed data
            for i in range(0, num_miners, 5):
                malformed_flags[i] = True

        if test_epoch_boundary:
            print("   [Mode] Epoch Boundary Simulation enabled (staggered start)")

        start_time = time.perf_counter()
        tasks = []
        for i in range(num_miners):
            if test_epoch_boundary and i > num_miners // 2:
                # Delay half of the miners to simulate boundary transition overlap
                delay = 5.0
            else:
                delay = 0

            tasks.append(self._delayed_session(delay, simulators[i], force_ids[i], malformed_flags[i]))

        self.results = await asyncio.gather(*tasks)
        duration = time.perf_counter() - start_time

        self.print_summary(num_miners, duration)
        await self.client.aclose()

    async def _delayed_session(self, delay, sim, fid, mal):
        if delay > 0:
            await asyncio.sleep(delay)
        return await self.run_miner_session(sim, fid, mal)

    def print_summary(self, total_miners: int, duration: float):
        """Calculates and prints performance metrics."""
        successes = [r for r in self.results if r["success"]]
        failures = [r for r in self.results if not r["success"]]

        total_times = [r["total_time"] for r in self.results if "total_time" in r]

        print("\n" + "="*50)
        print("STRESS TEST SUMMARY")
        print("="*50)
        print(f"Total Miners:     {total_miners}")
        print(f"Success Rate:     {len(successes)/total_miners*100:.1f}% ({len(successes)}/{total_miners})")
        print(f"Total Duration:   {duration:.2f}s")
        print(f"Avg Throughput:   {len(successes)/duration:.2f} miners/sec")

        if total_times:
            print(f"\nLatency (Total Session):")
            print(f"  P50 (Median):   {statistics.median(total_times):.3f}s")
            if len(total_times) > 1:
                total_times.sort()
                print(f"  P95:            {total_times[int(len(total_times)*0.95)]:.3f}s")
                print(f"  P99:            {total_times[int(len(total_times)*0.99)]:.3f}s")

        # Breakdown by step
        for step in ["challenge", "submit", "enroll"]:
            step_times = [r["steps"][step] for r in self.results if step in r["steps"]]
            if step_times:
                print(f"  Avg {step.capitalize()}:  {sum(step_times)/len(step_times):.3f}s")

        if failures:
            print("\nTop Errors:")
            error_counts = {}
            for r in failures:
                err = r.get("error", "Unknown error")
                error_counts[err] = error_counts.get(err, 0) + 1

            sorted_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)
            for err, count in sorted_errors[:5]:
                print(f"  - {count}x: {err}")
        print("="*50)
