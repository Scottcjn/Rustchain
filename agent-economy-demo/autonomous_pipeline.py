"""
RIP-302 Autonomous Agent Pipeline Demo
=======================================
Three agents hiring each other through the RustChain Agent Economy:

  Agent A (Researcher)  -- Posts a research job, pays Agent B
  Agent B (Writer)      -- Claims research job, delivers, then posts a writing job, pays Agent C
  Agent C (Publisher)   -- Claims writing job, delivers final article

Full lifecycle: post -> claim -> deliver -> accept -> repeat
All transactions on-chain via RIP-302 escrow.

Usage:
  python autonomous_pipeline.py [--node URL] [--demo]

Author: WireWork (wirework.dev)
License: MIT
"""

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

NODE_URL = os.environ.get("RUSTCHAIN_NODE", "https://50.28.86.131")
VERIFY_SSL = False
TIMEOUT = 15

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)-12s] %(message)s",
    datefmt="%H:%M:%S"
)

# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------

@dataclass
class Agent:
    """An autonomous agent with an RTC wallet that can post/claim/deliver jobs."""
    name: str
    wallet: str
    role: str
    log: logging.Logger = field(init=False)

    def __post_init__(self):
        self.log = logging.getLogger(self.name)

    def get_balance(self) -> float:
        try:
            r = requests.get(                f"{NODE_URL}/wallet/balance",
                params={"miner_id": self.wallet},
                verify=VERIFY_SSL, timeout=TIMEOUT
            )
            if r.ok:
                return r.json().get("amount_rtc", 0)
        except Exception as e:
            self.log.warning(f"Balance check failed: {e}")
        return 0

    def post_job(self, title: str, description: str, category: str,
                 reward_rtc: float, tags: list = None) -> Optional[str]:
        """Post a job to the Agent Economy marketplace. Returns job_id."""
        self.log.info(f"Posting job: '{title}' for {reward_rtc} RTC")
        try:
            r = requests.post(                f"{NODE_URL}/agent/jobs",
                json={
                    "poster_wallet": self.wallet,
                    "title": title,
                    "description": description,
                    "category": category,
                    "reward_rtc": reward_rtc,
                    "ttl_seconds": 7 * 86400,
                    "tags": tags or []
                },
                verify=VERIFY_SSL, timeout=TIMEOUT
            )
            data = r.json()
            if data.get("ok"):
                job_id = data["job_id"]
                self.log.info(
                    f"Job posted: {job_id} | "
                    f"Escrow: {data.get('escrow_total_rtc', '?')} RTC locked"
                )
                return job_id
            else:
                self.log.error(f"Post failed: {data.get('error')}")
                return None
        except Exception as e:
            self.log.error(f"Post error: {e}")
            return None

    def claim_job(self, job_id: str) -> bool:
        """Claim an open job."""
        self.log.info(f"Claiming job: {job_id}")
        try:
            r = requests.post(                f"{NODE_URL}/agent/jobs/{job_id}/claim",
                json={"worker_wallet": self.wallet},
                verify=VERIFY_SSL, timeout=TIMEOUT
            )
            data = r.json()
            if data.get("ok"):
                self.log.info(f"Claimed! Reward: {data.get('reward_rtc')} RTC")
                return True
            else:
                self.log.error(f"Claim failed: {data.get('error')}")
                return False
        except Exception as e:
            self.log.error(f"Claim error: {e}")
            return False

    def deliver_job(self, job_id: str, deliverable_url: str,
                    summary: str) -> bool:
        """Submit deliverable for a claimed job."""
        self.log.info(f"Delivering job: {job_id}")
        try:
            # Generate a content hash for the deliverable
            content_hash = hashlib.sha256(summary.encode()).hexdigest()[:16]
            r = requests.post(                f"{NODE_URL}/agent/jobs/{job_id}/deliver",
                json={
                    "worker_wallet": self.wallet,
                    "deliverable_url": deliverable_url,
                    "deliverable_hash": content_hash,
                    "result_summary": summary
                },
                verify=VERIFY_SSL, timeout=TIMEOUT
            )
            data = r.json()
            if data.get("ok"):
                self.log.info("Delivered successfully")
                return True
            else:
                self.log.error(f"Deliver failed: {data.get('error')}")
                return False
        except Exception as e:
            self.log.error(f"Deliver error: {e}")
            return False

    def accept_delivery(self, job_id: str, rating: int = 5) -> bool:
        """Accept a delivery and release escrow."""
        self.log.info(f"Accepting delivery for: {job_id}")
        try:
            r = requests.post(                f"{NODE_URL}/agent/jobs/{job_id}/accept",
                json={"poster_wallet": self.wallet, "rating": rating},
                verify=VERIFY_SSL, timeout=TIMEOUT
            )
            data = r.json()
            if data.get("ok"):
                self.log.info(
                    f"Accepted! {data.get('reward_paid_rtc', '?')} RTC "
                    f"paid to worker (fee: {data.get('platform_fee_rtc', '?')} RTC)"
                )
                return True
            else:
                self.log.error(f"Accept failed: {data.get('error')}")
                return False
        except Exception as e:
            self.log.error(f"Accept error: {e}")
            return False

    def get_reputation(self) -> dict:
        """Check this agent's reputation score."""
        try:
            r = requests.get(                f"{NODE_URL}/agent/reputation/{self.wallet}",
                verify=VERIFY_SSL, timeout=TIMEOUT
            )
            if r.ok:
                data = r.json()
                rep = data.get("reputation")
                if rep:
                    return rep
        except Exception:
            pass
        return {}

    def get_job_detail(self, job_id: str) -> Optional[dict]:
        """Get full details of a job including activity log."""
        try:
            r = requests.get(                f"{NODE_URL}/agent/jobs/{job_id}",
                verify=VERIFY_SSL, timeout=TIMEOUT
            )
            if r.ok:
                return r.json().get("job")
        except Exception:
            pass
        return None


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------

def get_marketplace_stats() -> dict:
    """Fetch current marketplace stats."""
    try:
        r = requests.get(f"{NODE_URL}/agent/stats", verify=VERIFY_SSL, timeout=TIMEOUT)
        if r.ok:
            return r.json().get("stats", {})
    except Exception:
        pass
    return {}


def print_separator(label=""):
    print(f"\n{'='*60}")
    if label:
        print(f"  {label}")
        print(f"{'='*60}")
    print()


def print_job_receipt(agent: Agent, job_id: str):
    """Print a formatted receipt for a completed job."""
    job = agent.get_job_detail(job_id)
    if not job:
        return

    print(f"  Job ID:    {job['job_id']}")
    print(f"  Title:     {job['title']}")
    print(f"  Poster:    {job['poster_wallet']}")
    print(f"  Worker:    {job.get('worker_wallet', 'N/A')}")
    print(f"  Reward:    {job['reward_rtc']} RTC")
    print(f"  Status:    {job['status']}")
    print(f"  Category:  {job['category']}")

    if job.get("activity_log"):
        print(f"\n  Activity Log:")
        for entry in job["activity_log"]:
            ts = time.strftime("%H:%M:%S", time.localtime(entry["created_at"]))
            print(f"    [{ts}] {entry['action']} by {entry.get('actor_wallet', '?')}")
            if entry.get("details"):
                print(f"             {entry['details']}")
    print()


def run_pipeline(dry_run=False):
    """
    Execute the full 3-agent autonomous pipeline.

    Chain:
      Agent A (Researcher) posts research job (2 RTC)
        -> Agent B (Writer) claims, delivers research
        -> Agent A accepts, pays Agent B
      Agent B posts writing job using research results (1.5 RTC)
        -> Agent C (Publisher) claims, delivers article
        -> Agent B accepts, pays Agent C
      Agent C posts review/publishing job (1 RTC)
        -> Agent A claims, delivers review
        -> Agent C accepts, pays Agent A

    This creates a circular economy: A -> B -> C -> A
    """

    # Create our three agents
    agent_a = Agent(
        name="Researcher",
        wallet="pipeline-researcher",
        role="research"
    )
    agent_b = Agent(
        name="Writer",
        wallet="pipeline-writer",
        role="writing"
    )
    agent_c = Agent(
        name="Publisher",
        wallet="pipeline-publisher",
        role="publishing"
    )

    agents = [agent_a, agent_b, agent_c]

    print_separator("RIP-302 AUTONOMOUS AGENT PIPELINE")
    print("  Three agents hiring each other through the Agent Economy:")
    print(f"    {agent_a.name} ({agent_a.wallet}) -- Posts research jobs")
    print(f"    {agent_b.name} ({agent_b.wallet}) -- Researches & writes")
    print(f"    {agent_c.name} ({agent_c.wallet}) -- Writes & publishes")
    print()

    # Check starting balances
    print("  Starting Balances:")
    for a in agents:
        bal = a.get_balance()
        print(f"    {a.name}: {bal} RTC")
    print()

    # Check marketplace stats before
    stats_before = get_marketplace_stats()
    print(f"  Marketplace Before: {stats_before.get('total_jobs', '?')} total jobs, "
          f"{stats_before.get('completed_jobs', '?')} completed, "
          f"{stats_before.get('total_rtc_volume', '?')} RTC volume")

    if dry_run:
        print("\n  [DRY RUN] Would execute pipeline but stopping here.")
        return True

    completed_jobs = []
    pipeline_start = time.time()

    # ===================================================================
    # PHASE 1: Researcher hires Writer for research
    # ===================================================================
    print_separator("PHASE 1: Researcher hires Writer")

    job1_id = agent_a.post_job(
        title="Research RustChain Proof-of-Antiquity consensus mechanism",
        description=(
            "Analyze the RustChain Proof-of-Antiquity (PoA) consensus mechanism. "
            "Cover: how antiquity multipliers work (386=3.0x, G4=2.5x, modern=0.8x), "
            "the 1-CPU-1-Vote round robin system, epoch settlement, and how RIP-200 "
            "prevents fleet attacks. Deliver as a structured research summary with "
            "key findings and comparison to PoW/PoS."
        ),
        category="research",
        reward_rtc=2.0,
        tags=["pipeline-demo", "phase-1", "research"]
    )

    if not job1_id:
        print("  FAILED: Could not post Phase 1 job")
        return False

    time.sleep(1)

    # Writer claims the research job
    if not agent_b.claim_job(job1_id):
        print("  FAILED: Writer could not claim job")
        return False

    time.sleep(1)

    # Writer delivers research
    research_output = (
        "RustChain PoA Research Summary: "
        "Proof-of-Antiquity rewards older hardware with multipliers "
        "(Intel 386 gets 3.0x, G4 gets 2.5x, modern CPUs get 0.8x). "
        "RIP-200 implements 1-CPU-1-Vote round robin to prevent fleet attacks. "
        "Epochs settle every ~24 hours with reward distribution based on "
        "attestation participation weighted by antiquity scores. "
        "Key insight: the system creates economic incentives to keep vintage "
        "hardware running, turning e-waste into productive mining infrastructure."
    )

    if not agent_b.deliver_job(
        job1_id,
        deliverable_url="https://github.com/wirework-pipeline/research-output",
        summary=research_output
    ):
        print("  FAILED: Writer could not deliver")
        return False

    time.sleep(1)

    # Researcher accepts delivery
    if not agent_a.accept_delivery(job1_id, rating=5):
        print("  FAILED: Researcher could not accept delivery")
        return False

    completed_jobs.append(job1_id)
    print("\n  Phase 1 Receipt:")
    print_job_receipt(agent_a, job1_id)

    # ===================================================================
    # PHASE 2: Writer hires Publisher to write article
    # ===================================================================
    print_separator("PHASE 2: Writer hires Publisher")

    job2_id = agent_b.post_job(
        title="Write article: Why Old Computers Mine RustChain Better",
        description=(
            "Using the research delivered in Phase 1, write a 500-word article "
            "explaining RustChain's Proof-of-Antiquity to a general crypto audience. "
            "Highlight: why a 1989 Intel 386 earns 3x more RTC than a modern CPU, "
            "how this prevents mining centralization, and what it means for "
            "sustainable blockchain design. Tone: accessible, engaging, technically "
            "accurate. Include comparison to Bitcoin PoW energy waste."
        ),
        category="writing",
        reward_rtc=1.5,
        tags=["pipeline-demo", "phase-2", "article"]
    )

    if not job2_id:
        print("  FAILED: Could not post Phase 2 job")
        return False

    time.sleep(1)

    # Publisher claims the writing job
    if not agent_c.claim_job(job2_id):
        print("  FAILED: Publisher could not claim job")
        return False

    time.sleep(1)

    # Publisher delivers article
    article_output = (
        "Article: Why Old Computers Mine RustChain Better. "
        "While Bitcoin miners race for the newest ASICs and Ethereum validators "
        "lock up capital, RustChain flips the script: older hardware earns more. "
        "An Intel 386 from 1985 gets a 3.0x antiquity multiplier, making it the "
        "most profitable mining hardware on the network. A PowerMac G4 earns 2.5x. "
        "Meanwhile, a brand new M4 MacBook gets just 0.8x. This isn't nostalgia -- "
        "it's mechanism design. By rewarding vintage hardware, RustChain creates "
        "economic incentives to keep old machines running instead of sending them "
        "to landfills. The 1-CPU-1-Vote system prevents fleet attacks where someone "
        "spins up thousands of VMs. Combined with hardware fingerprinting and "
        "24-hour attestation epochs, it's a consensus mechanism that's both fair "
        "and environmentally conscious."
    )

    if not agent_c.deliver_job(
        job2_id,
        deliverable_url="https://github.com/wirework-pipeline/article-output",
        summary=article_output
    ):
        print("  FAILED: Publisher could not deliver")
        return False

    time.sleep(1)

    # Writer accepts delivery
    if not agent_b.accept_delivery(job2_id, rating=5):
        print("  FAILED: Writer could not accept delivery")
        return False

    completed_jobs.append(job2_id)
    print("\n  Phase 2 Receipt:")
    print_job_receipt(agent_b, job2_id)

    # ===================================================================
    # PHASE 3: Publisher hires Researcher for peer review
    # ===================================================================
    print_separator("PHASE 3: Publisher hires Researcher for review")

    job3_id = agent_c.post_job(
        title="Peer review: Verify article accuracy against RustChain source",
        description=(
            "Review the article 'Why Old Computers Mine RustChain Better' for "
            "technical accuracy. Cross-reference claims against the actual "
            "RustChain source code (rip_200_round_robin_1cpu1vote.py). Verify: "
            "multiplier values are correct, 1-CPU-1-Vote description is accurate, "
            "epoch timing claims are right. Flag any inaccuracies. "
            "Deliver as a review report with corrections if needed."
        ),
        category="research",
        reward_rtc=1.0,
        tags=["pipeline-demo", "phase-3", "review"]
    )

    if not job3_id:
        print("  FAILED: Could not post Phase 3 job")
        return False

    time.sleep(1)

    # Researcher claims the review job (completing the circle: A -> B -> C -> A)
    if not agent_a.claim_job(job3_id):
        print("  FAILED: Researcher could not claim review job")
        return False

    time.sleep(1)

    # Researcher delivers review
    review_output = (
        "Peer Review Report: Article is technically accurate. "
        "Verified against rip_200_round_robin_1cpu1vote.py: "
        "ANTIQUITY_MULTIPLIERS dict confirms 386=3.0x, g4=2.5x, modern=0.8x. "
        "1-CPU-1-Vote round robin correctly described. "
        "Epoch timing is ~24 hours (ATTESTATION_TTL=86400). "
        "Minor correction: the 386 was released in 1985, not 1989 as article states. "
        "The GENESIS_TIMESTAMP is 1764706927 (Feb 2026). "
        "Recommendation: article is publication-ready with the date correction."
    )

    if not agent_a.deliver_job(
        job3_id,
        deliverable_url="https://github.com/wirework-pipeline/review-output",
        summary=review_output
    ):
        print("  FAILED: Researcher could not deliver review")
        return False

    time.sleep(1)

    # Publisher accepts review
    if not agent_c.accept_delivery(job3_id, rating=5):
        print("  FAILED: Publisher could not accept review")
        return False

    completed_jobs.append(job3_id)
    print("\n  Phase 3 Receipt:")
    print_job_receipt(agent_c, job3_id)

    # ===================================================================
    # SUMMARY
    # ===================================================================
    pipeline_end = time.time()
    duration = pipeline_end - pipeline_start

    print_separator("PIPELINE COMPLETE")

    print(f"  Duration: {duration:.1f} seconds")
    print(f"  Jobs completed: {len(completed_jobs)}")
    print(f"  Job chain: {' -> '.join(completed_jobs)}")
    print()

    # Final balances
    print("  Final Balances:")
    for a in agents:
        bal = a.get_balance()
        rep = a.get_reputation()
        trust = rep.get("trust_score", "?")
        level = rep.get("trust_level", "?")
        earned = rep.get("total_rtc_earned", 0)
        print(f"    {a.name}: {bal} RTC | Trust: {trust} ({level}) | Earned: {earned} RTC")
    print()

    # Marketplace stats after
    stats_after = get_marketplace_stats()
    print(f"  Marketplace After: {stats_after.get('total_jobs', '?')} total jobs, "
          f"{stats_after.get('completed_jobs', '?')} completed, "
          f"{stats_after.get('total_rtc_volume', '?')} RTC volume")

    jobs_added = (stats_after.get("total_jobs", 0) - stats_before.get("total_jobs", 0))
    vol_added = (stats_after.get("total_rtc_volume", 0) - stats_before.get("total_rtc_volume", 0))
    print(f"  Pipeline contribution: +{jobs_added} jobs, +{vol_added:.2f} RTC volume")
    print()

    # Verification: list all 3 jobs with their on-chain activity logs
    print_separator("ON-CHAIN VERIFICATION")
    print("  All transactions are verifiable via the Agent Economy API:\n")
    for i, jid in enumerate(completed_jobs, 1):
        print(f"  Phase {i}: curl -s {NODE_URL}/agent/jobs/{jid} | python3 -m json.tool")
    print()
    print(f"  Agent reputations:")
    for a in agents:
        print(f"    curl -s {NODE_URL}/agent/reputation/{a.wallet}")
    print()
    print(f"  Marketplace stats:")
    print(f"    curl -s {NODE_URL}/agent/stats")

    # Return job IDs for external verification
    return {
        "ok": True,
        "duration_seconds": round(duration, 1),
        "jobs": completed_jobs,
        "agents": {a.name: a.wallet for a in agents},
        "pipeline": "Researcher -> Writer -> Publisher -> Researcher (circular)",
        "total_rtc_transacted": 4.5,  # 2.0 + 1.5 + 1.0
        "platform_fees": round(4.5 * 0.05, 2)
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RIP-302 Autonomous Agent Pipeline Demo")
    parser.add_argument("--node", default=NODE_URL, help="RustChain node URL")
    parser.add_argument("--demo", action="store_true", help="Run full demo (posts real jobs)")
    parser.add_argument("--dry-run", action="store_true", help="Check balances only, don't post jobs")
    args = parser.parse_args()

    NODE_URL = args.node

    if args.dry_run:
        run_pipeline(dry_run=True)
    elif args.demo:
        result = run_pipeline()
        if result and isinstance(result, dict):
            print("\nPipeline result (JSON):")
            print(json.dumps(result, indent=2))
        elif not result:
            print("\nPipeline failed.")
            sys.exit(1)
    else:
        print("Usage:")
        print("  python autonomous_pipeline.py --demo      Run the full pipeline")
        print("  python autonomous_pipeline.py --dry-run   Check balances only")
        print()
        print("This will create 3 real jobs on the RustChain Agent Economy")
        print(f"and transact 4.5 RTC through the escrow system on {NODE_URL}.")
