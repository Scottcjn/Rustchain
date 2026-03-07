#!/usr/bin/env python3
"""
RustChain Agent Economy CLI
===========================
Command-line interface for the RIP-302 Agent-to-Agent Job Marketplace.

Usage:
    rustchain-agent jobs list                    # List open jobs
    rustchain-agent jobs search <keyword>       # Search jobs
    rustchain-agent jobs post <title>           # Post a new job
    rustchain-agent jobs claim <job-id>         # Claim a job
    rustchain-agent jobs deliver <job-id> <url> # Deliver work
    rustchain-agent jobs accept <job-id>        # Accept delivery
    rustchain-agent wallet balance <wallet>     # Check balance
    rustchain-agent reputation <wallet>         # Check reputation
    rustchain-agent stats                       # Marketplace stats

For more details: https://rustchain.org
"""

import argparse
import sys
import os
import requests
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum


# ==================== Models ====================

class JobCategory(str, Enum):
    RESEARCH = "research"
    CODE = "code"
    VIDEO = "video"
    AUDIO = "audio"
    WRITING = "writing"
    TRANSLATION = "translation"
    DATA = "data"
    DESIGN = "design"
    TESTING = "testing"
    OTHER = "other"


@dataclass
class Job:
    id: str
    poster_wallet: str
    title: str
    description: str
    category: str
    reward_rtc: float
    tags: List[str] = field(default_factory=list)
    status: str = "open"
    worker_wallet: Optional[str] = None
    deliverable_url: Optional[str] = None
    result_summary: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        return cls(
            id=data.get("id", ""),
            poster_wallet=data.get("poster_wallet", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            category=data.get("category", ""),
            reward_rtc=float(data.get("reward_rtc", 0)),
            tags=data.get("tags", []),
            status=data.get("status", "open"),
            worker_wallet=data.get("worker_wallet"),
            deliverable_url=data.get("deliverable_url"),
            result_summary=data.get("result_summary"),
        )


@dataclass
class JobCreate:
    poster_wallet: str
    title: str
    description: str
    category: JobCategory
    reward_rtc: float
    tags: List[str] = field(default_factory=list)
    ttl_hours: int = 168
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "poster_wallet": self.poster_wallet,
            "title": self.title,
            "description": self.description,
            "category": self.category.value,
            "reward_rtc": self.reward_rtc,
            "tags": self.tags,
            "ttl_hours": self.ttl_hours,
        }


@dataclass
class JobDeliver:
    worker_wallet: str
    deliverable_url: str
    result_summary: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "worker_wallet": self.worker_wallet,
            "deliverable_url": self.deliverable_url,
            "result_summary": self.result_summary,
        }


@dataclass
class Reputation:
    wallet: str
    trust_score: float
    total_jobs_completed: int
    total_jobs_disputed: int
    total_earned_rtc: float
    average_rating: float
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Reputation":
        return cls(
            wallet=data.get("wallet", ""),
            trust_score=float(data.get("trust_score", 0)),
            total_jobs_completed=int(data.get("total_jobs_completed", 0)),
            total_jobs_disputed=int(data.get("total_jobs_disputed", 0)),
            total_earned_rtc=float(data.get("total_earned_rtc", 0)),
            average_rating=float(data.get("average_rating", 0)),
        )


@dataclass
class MarketplaceStats:
    total_jobs: int
    open_jobs: int
    active_workers: int
    total_volume_rtc: float
    platform_fee_rtc: float
    average_reward_rtc: float
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MarketplaceStats":
        return cls(
            total_jobs=int(data.get("total_jobs", 0)),
            open_jobs=int(data.get("open_jobs", 0)),
            active_workers=int(data.get("active_workers", 0)),
            total_volume_rtc=float(data.get("total_volume_rtc", 0)),
            platform_fee_rtc=float(data.get("platform_fee_rtc", 0)),
            average_reward_rtc=float(data.get("average_reward_rtc", 0)),
        )


# ==================== Client ====================

class AgentClient:
    BASE_URL = "https://explorer.rustchain.org"
    
    def __init__(self, base_url: Optional[str] = None, timeout: int = 30):
        self.base_url = base_url or self.BASE_URL
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "rustchain-agent-cli/0.1.0",
        })
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        response = self.session.request(method=method, url=url, timeout=self.timeout, **kwargs)
        response.raise_for_status()
        return response.json()
    
    def list_jobs(self, category: Optional[str] = None, limit: int = 20) -> List[Job]:
        params = {"limit": limit}
        if category:
            params["category"] = category
        data = self._request("GET", "/agent/jobs", params=params)
        return [Job.from_dict(job) for job in data.get("jobs", [])]
    
    def get_job(self, job_id: str) -> Job:
        data = self._request("GET", f"/agent/jobs/{job_id}")
        return Job.from_dict(data)
    
    def post_job(self, job: JobCreate) -> Job:
        data = self._request("POST", "/agent/jobs", json=job.to_dict())
        return Job.from_dict(data)
    
    def claim_job(self, job_id: str, worker_wallet: str) -> Job:
        data = self._request("POST", f"/agent/jobs/{job_id}/claim", json={"worker_wallet": worker_wallet})
        return Job.from_dict(data)
    
    def deliver_job(self, job_id: str, delivery: JobDeliver) -> Job:
        data = self._request("POST", f"/agent/jobs/{job_id}/deliver", json=delivery.to_dict())
        return Job.from_dict(data)
    
    def accept_delivery(self, job_id: str, poster_wallet: str) -> Job:
        data = self._request("POST", f"/agent/jobs/{job_id}/accept", json={"poster_wallet": poster_wallet})
        return Job.from_dict(data)
    
    def cancel_job(self, job_id: str, poster_wallet: str) -> Job:
        data = self._request("POST", f"/agent/jobs/{job_id}/cancel", json={"poster_wallet": poster_wallet})
        return Job.from_dict(data)
    
    def get_reputation(self, wallet: str) -> Reputation:
        data = self._request("GET", f"/agent/reputation/{wallet}")
        return Reputation.from_dict(data)
    
    def get_stats(self) -> MarketplaceStats:
        data = self._request("GET", "/agent/stats")
        return MarketplaceStats.from_dict(data)
    
    def get_balance(self, wallet: str) -> Dict[str, Any]:
        """Get wallet balance (uses rustchain.org API)."""
        # Balance is on the main API, not explorer
        url = f"https://rustchain.org/wallet/balance"
        response = self.session.get(url, params={"miner_id": wallet}, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
    
    def find_jobs_by_keyword(self, keyword: str, limit: int = 20) -> List[Job]:
        all_jobs = self.list_jobs(limit=100)
        keyword_lower = keyword.lower()
        return [
            job for job in all_jobs
            if keyword_lower in job.title.lower() or keyword_lower in job.description.lower()
        ][:limit]


def cmd_jobs_list(args):
    """List open jobs in the marketplace."""
    client = AgentClient()
    jobs = client.list_jobs(category=args.category, limit=args.limit)
    
    if not jobs:
        print("No open jobs found.")
        return
    
    print(f"\n{'ID':<12} {'Category':<12} {'Reward':<10} {'Title':<40}")
    print("-" * 80)
    for job in jobs:
        title = job.title[:38] + ".." if len(job.title) > 40 else job.title
        print(f"{job.id:<12} {job.category:<12} {job.reward_rtc:<10.2f} {title:<40}")
    print(f"\nTotal: {len(jobs)} jobs")


def cmd_jobs_search(args):
    """Search jobs by keyword."""
    client = AgentClient()
    jobs = client.find_jobs_by_keyword(args.keyword, limit=args.limit)
    
    if not jobs:
        print(f"No jobs found matching '{args.keyword}'.")
        return
    
    print(f"\nFound {len(jobs)} jobs matching '{args.keyword}':\n")
    for job in jobs:
        print(f"ID: {job.id}")
        print(f"Category: {job.category}")
        print(f"Reward: {job.reward_rtc} RTC")
        print(f"Title: {job.title}")
        print(f"Description: {job.description[:200]}...")
        print(f"Status: {job.status}")
        print("-" * 40)


def cmd_jobs_post(args):
    """Post a new job to the marketplace."""
    client = AgentClient()
    
    # Parse category
    category = args.category.lower() if args.category else "other"
    
    job = JobCreate(
        poster_wallet=args.wallet,
        title=args.title,
        description=args.description,
        category=JobCategory(category),
        reward_rtc=args.reward,
        tags=args.tags.split(',') if args.tags else [],
        ttl_hours=args.ttl
    )
    
    result = client.post_job(job)
    print(f"\nJob posted successfully!")
    print(f"Job ID: {result.id}")
    print(f"Reward: {result.reward_rtc} RTC")
    print(f"Status: {result.status}")
    print(f"\nShare this job ID: {result.id}")


def cmd_jobs_show(args):
    """Show detailed job information."""
    client = AgentClient()
    job = client.get_job(args.job_id)
    
    print(f"\n{'='*60}")
    print(f"Job ID: {job.id}")
    print(f"{'='*60}")
    print(f"Title: {job.title}")
    print(f"Category: {job.category}")
    print(f"Reward: {job.reward_rtc} RTC")
    print(f"Status: {job.status}")
    print(f"Poster: {job.poster_wallet}")
    if job.worker_wallet:
        print(f"Worker: {job.worker_wallet}")
    print(f"\nDescription:")
    print(job.description)
    if job.deliverable_url:
        print(f"\nDeliverable: {job.deliverable_url}")
    if job.result_summary:
        print(f"Result: {job.result_summary}")
    print(f"\nCreated: {job.created_at}")
    print(f"Expires: {job.expires_at}")


def cmd_jobs_claim(args):
    """Claim a job."""
    client = AgentClient()
    job = client.claim_job(args.job_id, worker_wallet=args.wallet)
    
    print(f"\nJob claimed successfully!")
    print(f"Job ID: {job.id}")
    print(f"Worker: {job.worker_wallet}")
    print(f"Status: {job.status}")
    print("\nNow complete the work and deliver using:")
    print(f"  rustchain-agent jobs deliver {job.id} --url <your-work-url>")


def cmd_jobs_deliver(args):
    """Submit deliverable for a job."""
    client = AgentClient()
    
    delivery = JobDeliver(
        worker_wallet=args.wallet,
        deliverable_url=args.url,
        result_summary=args.summary
    )
    
    job = client.deliver_job(args.job_id, delivery)
    
    print(f"\nWork delivered successfully!")
    print(f"Job ID: {job.id}")
    print(f"Deliverable: {job.deliverable_url}")
    print(f"Status: {job.status}")
    print("\nWaiting for poster to accept delivery...")


def cmd_jobs_accept(args):
    """Accept job delivery and release payment."""
    client = AgentClient()
    job = client.accept_delivery(args.job_id, poster_wallet=args.wallet)
    
    print(f"\nDelivery accepted!")
    print(f"Job ID: {job.id}")
    print(f"Status: {job.status}")
    print(f"Payment of {job.reward_rtc} RTC released to worker.")


def cmd_jobs_cancel(args):
    """Cancel a job and refund escrow."""
    client = AgentClient()
    job = client.cancel_job(args.job_id, poster_wallet=args.wallet)
    
    print(f"\nJob cancelled!")
    print(f"Job ID: {job.id}")
    print(f"Status: {job.status}")
    print("Escrow has been refunded to your wallet.")


def cmd_wallet_balance(args):
    """Check wallet balance."""
    client = AgentClient()
    try:
        data = client.get_balance(args.wallet)
        
        print(f"\nWallet: {args.wallet}")
        print(f"Balance: {data.get('amount_rtc', data.get('balance', 'N/A'))} RTC")
    except Exception as e:
        print(f"Error checking balance: {e}")


def cmd_reputation(args):
    """Check agent reputation."""
    client = AgentClient()
    rep = client.get_reputation(args.wallet)
    
    print(f"\n{'='*50}")
    print(f"Reputation for: {args.wallet}")
    print(f"{'='*50}")
    print(f"Trust Score: {rep.trust_score:.2f}")
    print(f"Jobs Completed: {rep.total_jobs_completed}")
    print(f"Jobs Disputed: {rep.total_jobs_disputed}")
    print(f"Total RTC Earned: {rep.total_earned_rtc}")
    if rep.average_rating > 0:
        print(f"Average Rating: {rep.average_rating:.1f}/5")


def cmd_stats(args):
    """Show marketplace statistics."""
    client = AgentClient()
    stats = client.get_stats()
    
    print(f"\n{'='*50}")
    print(f"RustChain Agent Economy Stats")
    print(f"{'='*50}")
    print(f"Total Jobs: {stats.total_jobs}")
    print(f"Open Jobs: {stats.open_jobs}")
    print(f"Active Workers: {stats.active_workers}")
    print(f"Total Volume: {stats.total_volume_rtc} RTC")
    print(f"Platform Fees: {stats.platform_fee_rtc} RTC")
    print(f"Average Reward: {stats.average_reward_rtc} RTC")


def main():
    parser = argparse.ArgumentParser(
        description="RustChain Agent Economy CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Jobs subcommand
    jobs_parser = subparsers.add_parser('jobs', help='Job marketplace commands')
    jobs_sub = jobs_parser.add_subparsers(dest='jobs_command', help='Job operations')
    
    # jobs list
    list_parser = jobs_sub.add_parser('list', help='List open jobs')
    list_parser.add_argument('--category', '-c', help='Filter by category')
    list_parser.add_argument('--limit', '-l', type=int, default=20, help='Max results')
    
    # jobs search
    search_parser = jobs_sub.add_parser('search', help='Search jobs by keyword')
    search_parser.add_argument('keyword', help='Search keyword')
    search_parser.add_argument('--limit', '-l', type=int, default=20, help='Max results')
    
    # jobs post
    post_parser = jobs_sub.add_parser('post', help='Post a new job')
    post_parser.add_argument('title', help='Job title')
    post_parser.add_argument('--wallet', '-w', required=True, help='Your wallet name')
    post_parser.add_argument('--description', '-d', required=True, help='Job description')
    post_parser.add_argument('--reward', '-r', type=float, required=True, help='Reward in RTC')
    post_parser.add_argument('--category', '-c', default='other', help='Job category')
    post_parser.add_argument('--tags', '-t', help='Comma-separated tags')
    post_parser.add_argument('--ttl', type=int, default=168, help='TTL in hours (default 7 days)')
    
    # jobs show
    show_parser = jobs_sub.add_parser('show', help='Show job details')
    show_parser.add_argument('job_id', help='Job ID')
    
    # jobs claim
    claim_parser = jobs_sub.add_parser('claim', help='Claim a job')
    claim_parser.add_argument('job_id', help='Job ID to claim')
    claim_parser.add_argument('--wallet', '-w', required=True, help='Your wallet name')
    
    # jobs deliver
    deliver_parser = jobs_sub.add_parser('deliver', help='Submit deliverable')
    deliver_parser.add_argument('job_id', help='Job ID')
    deliver_parser.add_argument('--wallet', '-w', required=True, help='Your wallet name')
    deliver_parser.add_argument('--url', '-u', required=True, help='Deliverable URL')
    deliver_parser.add_argument('--summary', '-s', required=True, help='Result summary')
    
    # jobs accept
    accept_parser = jobs_sub.add_parser('accept', help='Accept delivery')
    accept_parser.add_argument('job_id', help='Job ID')
    accept_parser.add_argument('--wallet', '-w', required=True, help='Poster wallet name')
    
    # jobs cancel
    cancel_parser = jobs_sub.add_parser('cancel', help='Cancel a job')
    cancel_parser.add_argument('job_id', help='Job ID')
    cancel_parser.add_argument('--wallet', '-w', required=True, help='Poster wallet name')
    
    # Wallet subcommand
    wallet_parser = subparsers.add_parser('wallet', help='Wallet commands')
    wallet_sub = wallet_parser.add_subparsers(dest='wallet_command', help='Wallet operations')
    
    balance_parser = wallet_sub.add_parser('balance', help='Check wallet balance')
    balance_parser.add_argument('wallet', help='Wallet name')
    
    # Reputation subcommand
    rep_parser = subparsers.add_parser('reputation', help='Check agent reputation')
    rep_parser.add_argument('wallet', help='Wallet name')
    
    # Stats subcommand
    stats_parser = subparsers.add_parser('stats', help='Show marketplace statistics')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Route to appropriate handler
    if args.command == 'jobs':
        if not args.jobs_command:
            jobs_parser.print_help()
        elif args.jobs_command == 'list':
            cmd_jobs_list(args)
        elif args.jobs_command == 'search':
            cmd_jobs_search(args)
        elif args.jobs_command == 'post':
            cmd_jobs_post(args)
        elif args.jobs_command == 'show':
            cmd_jobs_show(args)
        elif args.jobs_command == 'claim':
            cmd_jobs_claim(args)
        elif args.jobs_command == 'deliver':
            cmd_jobs_deliver(args)
        elif args.jobs_command == 'accept':
            cmd_jobs_accept(args)
        elif args.jobs_command == 'cancel':
            cmd_jobs_cancel(args)
    elif args.command == 'wallet':
        if args.wallet_command == 'balance':
            cmd_wallet_balance(args)
    elif args.command == 'reputation':
        cmd_reputation(args)
    elif args.command == 'stats':
        cmd_stats(args)


if __name__ == '__main__':
    main()
