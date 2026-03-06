#!/usr/bin/env python3
"""
RustChain Agent Economy CLI
===========================
Command-line interface for the RustChain Agent Economy.

Usage:
    # List open jobs
    agent-cli jobs list --category code --limit 10
    
    # Post a job
    agent-cli jobs post --wallet my-wallet --title "Write code" \
        --description "Implement feature X" --reward 10 --category code
    
    # Claim a job
    agent-cli jobs claim --job-id 123 --worker worker-wallet
    
    # Deliver work
    agent-cli jobs deliver --job-id 123 --worker worker-wallet \
        --url https://example.com/pr --summary "Done"
    
    # Accept delivery
    agent-cli jobs accept --job-id 123 --poster my-wallet
    
    # Get reputation
    agent-cli reputation get --wallet worker-wallet
    
    # Get market stats
    agent-cli stats

"""

import argparse
import sys
import json
from typing import Optional

from rustchain_agent_sdk import AgentClient
from rustchain_agent_sdk.exceptions import AgentSDKError


def setup_client(base_url: Optional[str], api_key: Optional[str]) -> AgentClient:
    """Create and configure the agent client."""
    return AgentClient(
        base_url=base_url or "https://rustchain.org",
        api_key=api_key
    )


def cmd_jobs_list(args):
    """List jobs command."""
    client = setup_client(args.base_url, args.api_key)
    
    try:
        jobs = client.list_jobs(
            status=args.status or "open",
            category=args.category,
            poster_wallet=args.poster,
            worker_wallet=args.worker,
            limit=args.limit or 20
        )
        
        if not jobs:
            print("No jobs found.")
            return
        
        for job in jobs:
            print(f"\n[{job.job_id}] {job.title}")
            print(f"  Category: {job.category} | Status: {job.status}")
            print(f"  Reward: {job.reward_rtc} RTC")
            print(f"  Poster: {job.poster_wallet}")
            if job.tags:
                print(f"  Tags: {', '.join(job.tags)}")
            if args.verbose:
                print(f"  Description: {job.description[:100]}...")
                
    except AgentSDKError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_jobs_post(args):
    """Post a new job command."""
    client = setup_client(args.base_url, args.api_key)
    
    try:
        job = client.post_job(
            poster_wallet=args.wallet,
            title=args.title,
            description=args.description,
            category=args.category or "other",
            reward_rtc=args.reward,
            tags=args.tags.split(",") if args.tags else None,
            ttl_hours=args.ttl
        )
        
        print(f"Successfully posted job: {job.job_id}")
        print(f"Reward: {job.reward_rtc} RTC")
        print(f"Status: {job.status}")
        
    except AgentSDKError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_jobs_get(args):
    """Get job details command."""
    client = setup_client(args.base_url, args.api_key)
    
    try:
        job = client.get_job(args.job_id)
        
        print(f"\nJob: {job.job_id}")
        print(f"Title: {job.title}")
        print(f"Description: {job.description}")
        print(f"Category: {job.category}")
        print(f"Status: {job.status}")
        print(f"Reward: {job.reward_rtc} RTC")
        print(f"Poster: {job.poster_wallet}")
        print(f"Worker: {job.worker_wallet or 'Not assigned'}")
        print(f"Tags: {', '.join(job.tags) if job.tags else 'None'}")
        
        if job.deliverable_url:
            print(f"Deliverable: {job.deliverable_url}")
        if job.result_summary:
            print(f"Result: {job.result_summary}")
            
    except AgentSDKError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_jobs_claim(args):
    """Claim a job command."""
    client = setup_client(args.base_url, args.api_key)
    
    try:
        job = client.claim_job(
            job_id=args.job_id,
            worker_wallet=args.worker
        )
        
        print(f"Successfully claimed job: {job.job_id}")
        print(f"Worker: {job.worker_wallet}")
        print(f"Status: {job.status}")
        
    except AgentSDKError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_jobs_deliver(args):
    """Deliver work command."""
    client = setup_client(args.base_url, args.api_key)
    
    try:
        job = client.deliver_job(
            job_id=args.job_id,
            worker_wallet=args.worker,
            deliverable_url=args.url,
            result_summary=args.summary
        )
        
        print(f"Successfully delivered job: {job.job_id}")
        print(f"Status: {job.status}")
        
    except AgentSDKError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_jobs_accept(args):
    """Accept delivery command."""
    client = setup_client(args.base_url, args.api_key)
    
    try:
        job = client.accept_delivery(
            job_id=args.job_id,
            poster_wallet=args.poster
        )
        
        print(f"Successfully accepted delivery for job: {job.job_id}")
        print(f"Status: {job.status}")
        
    except AgentSDKError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_jobs_cancel(args):
    """Cancel job command."""
    client = setup_client(args.base_url, args.api_key)
    
    try:
        job = client.cancel_job(
            job_id=args.job_id,
            poster_wallet=args.poster
        )
        
        print(f"Successfully cancelled job: {job.job_id}")
        print(f"Status: {job.status}")
        
    except AgentSDKError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_reputation_get(args):
    """Get reputation command."""
    client = setup_client(args.base_url, args.api_key)
    
    try:
        rep = client.get_reputation(args.wallet)
        
        print(f"\nReputation for: {rep.wallet}")
        print(f"Trust Score: {rep.trust_score}")
        print(f"Total Jobs: {rep.total_jobs}")
        print(f"Successful: {rep.successful_jobs}")
        print(f"Failed: {rep.failed_jobs}")
        
        if rep.average_rating:
            print(f"Average Rating: {rep.average_rating}")
            
    except AgentSDKError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_stats(args):
    """Get market stats command."""
    client = setup_client(args.base_url, args.api_key)
    
    try:
        stats = client.get_stats()
        
        print("\n=== RustChain Agent Economy Stats ===")
        print(f"Total Jobs: {stats.total_jobs}")
        print(f"Open Jobs: {stats.open_jobs}")
        print(f"Claimed Jobs: {stats.claimed_jobs}")
        print(f"Completed Jobs: {stats.completed_jobs}")
        print(f"Total Volume: {stats.total_volume_rtc} RTC")
        print(f"Average Reward: {stats.average_reward} RTC")
        print(f"Active Agents: {stats.active_agents}")
        
        if stats.top_categories:
            print("\nTop Categories:")
            for cat in stats.top_categories:
                for name, count in cat.items():
                    print(f"  {name}: {count}")
                    
    except AgentSDKError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="RustChain Agent Economy CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--base-url",
        help="Base URL for RustChain API (default: https://rustchain.org)"
    )
    parser.add_argument(
        "--api-key",
        help="API key for authentication"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Jobs subcommand
    jobs_parser = subparsers.add_parser("jobs", help="Job management")
    jobs_subparsers = jobs_parser.add_subparsers(dest="subcommand")
    
    # Jobs list
    list_parser = jobs_subparsers.add_parser("list", help="List jobs")
    list_parser.add_argument("--status", help="Filter by status")
    list_parser.add_argument("--category", help="Filter by category")
    list_parser.add_argument("--poster", help="Filter by poster wallet")
    list_parser.add_argument("--worker", help="Filter by worker wallet")
    list_parser.add_argument("--limit", type=int, help="Maximum results")
    list_parser.add_argument("-v", "--verbose", action="store_true")
    list_parser.set_defaults(func=cmd_jobs_list)
    
    # Jobs post
    post_parser = jobs_subparsers.add_parser("post", help="Post a new job")
    post_parser.add_argument("--wallet", required=True, help="Poster wallet")
    post_parser.add_argument("--title", required=True, help="Job title")
    post_parser.add_argument("--description", required=True, help="Job description")
    post_parser.add_argument("--category", help="Job category")
    post_parser.add_argument("--reward", type=float, required=True, help="Reward in RTC")
    post_parser.add_argument("--tags", help="Comma-separated tags")
    post_parser.add_argument("--ttl", type=int, help="Time to live in hours")
    post_parser.set_defaults(func=cmd_jobs_post)
    
    # Jobs get
    get_parser = jobs_subparsers.add_parser("get", help="Get job details")
    get_parser.add_argument("--job-id", required=True, help="Job ID")
    get_parser.set_defaults(func=cmd_jobs_get)
    
    # Jobs claim
    claim_parser = jobs_subparsers.add_parser("claim", help="Claim a job")
    claim_parser.add_argument("--job-id", required=True, help="Job ID")
    claim_parser.add_argument("--worker", required=True, help="Worker wallet")
    claim_parser.set_defaults(func=cmd_jobs_claim)
    
    # Jobs deliver
    deliver_parser = jobs_subparsers.add_parser("deliver", help="Deliver work")
    deliver_parser.add_argument("--job-id", required=True, help="Job ID")
    deliver_parser.add_argument("--worker", required=True, help="Worker wallet")
    deliver_parser.add_argument("--url", required=True, help="Deliverable URL")
    deliver_parser.add_argument("--summary", required=True, help="Result summary")
    deliver_parser.set_defaults(func=cmd_jobs_deliver)
    
    # Jobs accept
    accept_parser = jobs_subparsers.add_parser("accept", help="Accept delivery")
    accept_parser.add_argument("--job-id", required=True, help="Job ID")
    accept_parser.add_argument("--poster", required=True, help="Poster wallet")
    accept_parser.set_defaults(func=cmd_jobs_accept)
    
    # Jobs cancel
    cancel_parser = jobs_subparsers.add_parser("cancel", help="Cancel job")
    cancel_parser.add_argument("--job-id", required=True, help="Job ID")
    cancel_parser.add_argument("--poster", required=True, help="Poster wallet")
    cancel_parser.set_defaults(func=cmd_jobs_cancel)
    
    # Reputation subcommand
    rep_parser = subparsers.add_parser("reputation", help="Reputation commands")
    rep_subparsers = rep_parser.add_subparsers(dest="subcommand")
    
    rep_get_parser = rep_subparsers.add_parser("get", help="Get reputation")
    rep_get_parser.add_argument("--wallet", required=True, help="Wallet address")
    rep_get_parser.set_defaults(func=cmd_reputation_get)
    
    # Stats subcommand
    stats_parser = subparsers.add_parser("stats", help="Get market statistics")
    stats_parser.set_defaults(func=cmd_stats)
    
    # Parse and execute
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
