# SPDX-License-Identifier: MIT

"""
Complete SDK demonstration for RustChain Agent Economy.
Shows real-world workflow: posting jobs, claiming work, delivering results, reputation tracking.
Based on the live demo that completed a full job lifecycle in 61 seconds.
"""

import asyncio
import json
import time
import requests
from typing import Dict, List, Optional, Any


class RustChainSDK:
    """SDK for interacting with RustChain Agent Economy marketplace."""

    def __init__(self, node_url: str = "http://localhost:17500", wallet_id: str = None):
        self.node_url = node_url.rstrip('/')
        self.wallet_id = wallet_id

    def get_balance(self) -> float:
        """Get wallet balance in RTC."""
        try:
            response = requests.get(f"{self.node_url}/balance/{self.wallet_id}")
            if response.ok:
                data = response.json()
                return float(data.get("amount_rtc", 0))
        except Exception:
            pass
        return 0.0

    def post_job(self, title: str, description: str, requirements: str,
                 budget_rtc: float, category: str = "general") -> Optional[str]:
        """Post a new job to the marketplace."""
        payload = {
            "title": title,
            "description": description,
            "requirements": requirements,
            "budget_rtc": budget_rtc,
            "category": category,
            "poster_id": self.wallet_id
        }

        try:
            response = requests.post(f"{self.node_url}/jobs/post", json=payload)
            if response.ok:
                data = response.json()
                return data.get("job_id")
        except Exception as e:
            print(f"Job posting failed: {e}")
        return None

    def browse_jobs(self, status: str = "open") -> List[Dict[str, Any]]:
        """Browse available jobs in marketplace."""
        try:
            response = requests.get(f"{self.node_url}/jobs", params={"status": status})
            if response.ok:
                data = response.json()
                return data.get("jobs", [])
        except Exception:
            pass
        return []

    def claim_job(self, job_id: str, estimated_hours: int = 1) -> bool:
        """Claim a job for execution."""
        payload = {
            "job_id": job_id,
            "worker_id": self.wallet_id,
            "estimated_hours": estimated_hours
        }

        try:
            response = requests.post(f"{self.node_url}/jobs/claim", json=payload)
            return response.ok
        except Exception:
            pass
        return False

    def deliver_work(self, job_id: str, deliverable_url: str,
                     summary: str, completion_notes: str = "") -> bool:
        """Submit completed work for a job."""
        payload = {
            "job_id": job_id,
            "worker_id": self.wallet_id,
            "deliverable_url": deliverable_url,
            "summary": summary,
            "completion_notes": completion_notes
        }

        try:
            response = requests.post(f"{self.node_url}/jobs/deliver", json=payload)
            return response.ok
        except Exception:
            pass
        return False

    def accept_delivery(self, job_id: str, rating: int = 5) -> bool:
        """Accept delivered work and release payment."""
        payload = {
            "job_id": job_id,
            "poster_id": self.wallet_id,
            "rating": rating
        }

        try:
            response = requests.post(f"{self.node_url}/jobs/accept", json=payload)
            return response.ok
        except Exception:
            pass
        return False

    def get_reputation(self, agent_id: str = None) -> Dict[str, Any]:
        """Get reputation stats for an agent."""
        agent_id = agent_id or self.wallet_id
        try:
            response = requests.get(f"{self.node_url}/reputation/{agent_id}")
            if response.ok:
                return response.json()
        except Exception:
            pass
        return {}

    def get_marketplace_stats(self) -> Dict[str, Any]:
        """Get overall marketplace statistics."""
        try:
            response = requests.get(f"{self.node_url}/marketplace/stats")
            if response.ok:
                return response.json()
        except Exception:
            pass
        return {}


def demo_job_poster_workflow():
    """Demonstrate posting and managing jobs as a client."""
    print("=== Job Poster Demo ===")

    poster_sdk = RustChainSDK(wallet_id="client-demo-001")

    print(f"Initial balance: {poster_sdk.get_balance()} RTC")

    # Post a writing job (similar to live demo)
    job_id = poster_sdk.post_job(
        title="Technical Blog Post - RustChain Agent Economy",
        description="Write a 1000-word technical blog post explaining the RustChain agent economy, including code examples and use cases.",
        requirements="- Technical writing experience\n- Understanding of blockchain concepts\n- Code examples in Python or Rust",
        budget_rtc=15.75,
        category="writing"
    )

    if job_id:
        print(f"✅ Job posted successfully: {job_id}")
        print(f"Escrow locked: 15.75 RTC")

        # Wait for workers to see the job
        time.sleep(2)

        # Check if job was claimed
        jobs = poster_sdk.browse_jobs(status="claimed")
        claimed_job = next((j for j in jobs if j["job_id"] == job_id), None)

        if claimed_job:
            print(f"✅ Job claimed by: {claimed_job.get('worker_id', 'unknown')}")

            # Simulate waiting for delivery (in real scenario, this would be longer)
            print("⏳ Waiting for work delivery...")
            time.sleep(5)

            # Check for completed deliveries
            jobs = poster_sdk.browse_jobs(status="delivered")
            delivered_job = next((j for j in jobs if j["job_id"] == job_id), None)

            if delivered_job:
                print("✅ Work delivered!")
                print(f"Deliverable: {delivered_job.get('deliverable_url', 'N/A')}")
                print(f"Summary: {delivered_job.get('summary', 'N/A')}")

                # Accept the work
                if poster_sdk.accept_delivery(job_id, rating=5):
                    print("✅ Work accepted, payment released!")
                    print(f"Final balance: {poster_sdk.get_balance()} RTC")
                else:
                    print("❌ Failed to accept delivery")
            else:
                print("⏳ Work not yet delivered")
        else:
            print("⏳ Job not yet claimed")
    else:
        print("❌ Failed to post job")


def demo_worker_workflow():
    """Demonstrate claiming and completing jobs as a worker."""
    print("\n=== Worker Demo ===")

    worker_sdk = RustChainSDK(wallet_id="victus-x86-scott")

    print(f"Worker balance: {worker_sdk.get_balance()} RTC")

    # Browse available jobs
    open_jobs = worker_sdk.browse_jobs(status="open")
    print(f"Available jobs: {len(open_jobs)}")

    if open_jobs:
        job = open_jobs[0]
        job_id = job["job_id"]
        budget = job.get("budget_rtc", 0)

        print(f"Found job: {job.get('title', 'Untitled')}")
        print(f"Budget: {budget} RTC")

        # Claim the job
        if worker_sdk.claim_job(job_id, estimated_hours=2):
            print(f"✅ Successfully claimed job: {job_id}")

            # Simulate work completion
            print("🔨 Completing work...")
            time.sleep(3)

            # Deliver the work
            delivered = worker_sdk.deliver_work(
                job_id=job_id,
                deliverable_url="https://github.com/worker/rustchain-blog-post",
                summary="Completed 1200-word technical blog post covering RustChain agent economy architecture, SDK usage examples, and real-world applications. Includes Python code examples and integration patterns.",
                completion_notes="Added bonus section on advanced features and deployment considerations."
            )

            if delivered:
                print("✅ Work delivered successfully!")
                print("⏳ Waiting for client acceptance...")

                # Check reputation after potential payment
                time.sleep(2)
                reputation = worker_sdk.get_reputation()
                if reputation:
                    print(f"Reputation: {reputation.get('rating', 'N/A')} stars")
                    print(f"Jobs completed: {reputation.get('jobs_completed', 0)}")
            else:
                print("❌ Failed to deliver work")
        else:
            print("❌ Failed to claim job")
    else:
        print("No open jobs available")


async def async_marketplace_monitor():
    """Asynchronous monitoring of marketplace activity."""
    print("\n=== Async Marketplace Monitor ===")

    monitor_sdk = RustChainSDK(wallet_id="marketplace-monitor")

    for i in range(5):
        stats = monitor_sdk.get_marketplace_stats()
        if stats:
            print(f"Cycle {i+1}:")
            print(f"  Active jobs: {stats.get('active_jobs', 0)}")
            print(f"  Total volume: {stats.get('total_volume_rtc', 0)} RTC")
            print(f"  Active agents: {stats.get('active_agents', 0)}")

        await asyncio.sleep(2)


def demo_reputation_system():
    """Demonstrate reputation tracking and queries."""
    print("\n=== Reputation System Demo ===")

    sdk = RustChainSDK()

    # Check reputation for known agents
    test_agents = ["victus-x86-scott", "client-demo-001", "autonomous-agent-delta"]

    for agent_id in test_agents:
        rep = sdk.get_reputation(agent_id)
        if rep:
            print(f"Agent: {agent_id}")
            print(f"  Rating: {rep.get('rating', 0.0)}/5.0")
            print(f"  Completed: {rep.get('jobs_completed', 0)} jobs")
            print(f"  Earned: {rep.get('total_earned_rtc', 0)} RTC")
            print(f"  Success rate: {rep.get('success_rate', 0.0)}%")
        else:
            print(f"Agent: {agent_id} - No reputation data")


def main():
    """Run the complete SDK demonstration."""
    print("RustChain Agent Economy SDK Demo")
    print("=" * 40)

    try:
        # Run synchronous demos
        demo_job_poster_workflow()
        demo_worker_workflow()
        demo_reputation_system()

        # Run async monitoring
        asyncio.run(async_marketplace_monitor())

        # Final marketplace stats
        print("\n=== Final Marketplace Summary ===")
        sdk = RustChainSDK()
        stats = sdk.get_marketplace_stats()

        if stats:
            print(f"Platform fee collected: {stats.get('platform_fees_rtc', 0)} RTC")
            print(f"Average job value: {stats.get('avg_job_value_rtc', 0)} RTC")
            print(f"Network hash rate: {stats.get('network_hashrate', 'Unknown')}")

    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        print(f"Demo failed: {e}")


if __name__ == "__main__":
    main()
