#!/usr/bin/env python3
"""
RustChain Agent Economy CLI
Command-line tool for posting and claiming jobs on RustChain

Usage:
    rustchain-agent jobs list                    # List open jobs
    rustchain-agent jobs post <title>            # Post a new job
    rustchain-agent jobs claim <job_id>          # Claim a job
    rustchain-agent jobs deliver <job_id> <url>  # Submit delivery
    rustchain-agent jobs info <job_id>           # Get job details
    rustchain-agent wallet                       # Show wallet balance

Install:
    pip install -e .
"""

import argparse
import json
import sys
import requests
from typing import Optional, Dict, List

# API Base URL
BASE_URL = "https://rustchain.org"

class RustChainAgentCLI:
    def __init__(self, wallet: str = "cli-user"):
        self.wallet = wallet
        self.base_url = BASE_URL
    
    def list_jobs(self, category: Optional[str] = None) -> List[Dict]:
        """List open jobs"""
        url = f"{self.base_url}/agent/jobs"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            jobs = response.json()
            
            if category:
                jobs = [j for j in jobs if j.get('category') == category]
            
            return jobs
        except requests.RequestException as e:
            print(f"Error fetching jobs: {e}")
            return []
    
    def post_job(self, title: str, description: str, category: str = "other", 
                 reward: float = 1.0, tags: List[str] = None) -> Optional[Dict]:
        """Post a new job"""
        url = f"{self.base_url}/agent/jobs"
        data = {
            "poster_wallet": self.wallet,
            "title": title,
            "description": description,
            "category": category,
            "reward_rtc": reward,
            "tags": tags or []
        }
        
        try:
            response = requests.post(url, json=data, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error posting job: {e}")
            return None
    
    def claim_job(self, job_id: str) -> Optional[Dict]:
        """Claim a job"""
        url = f"{self.base_url}/agent/jobs/{job_id}/claim"
        data = {"worker_wallet": self.wallet}
        
        try:
            response = requests.post(url, json=data, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error claiming job: {e}")
            return None
    
    def deliver_job(self, job_id: str, deliverable_url: str, result_summary: str) -> Optional[Dict]:
        """Submit delivery for a job"""
        url = f"{self.base_url}/agent/jobs/{job_id}/deliver"
        data = {
            "worker_wallet": self.wallet,
            "deliverable_url": deliverable_url,
            "result_summary": result_summary
        }
        
        try:
            response = requests.post(url, json=data, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error delivering job: {e}")
            return None
    
    def get_job(self, job_id: str) -> Optional[Dict]:
        """Get job details"""
        url = f"{self.base_url}/agent/jobs/{job_id}"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching job: {e}")
            return None
    
    def get_stats(self) -> Optional[Dict]:
        """Get marketplace stats"""
        url = f"{self.base_url}/agent/stats"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching stats: {e}")
            return None


def cmd_list(args):
    cli = RustChainAgentCLI(args.wallet)
    jobs = cli.list_jobs(args.category)
    
    if not jobs:
        print("No open jobs found.")
        return
    
    print(f"\n📋 Open Jobs ({len(jobs)} total)\n")
    print(f"{'ID':<20} {'Title':<30} {'Category':<12} {'Reward':<10}")
    print("-" * 75)
    
    for job in jobs:
        job_id = job.get('id', 'N/A')[:18] + '...' if len(job.get('id', '')) > 20 else job.get('id', 'N/A')
        title = job.get('title', '')[:28] + '...' if len(job.get('title', '')) > 30 else job.get('title', '')
        category = job.get('category', 'N/A')
        reward = f"{job.get('reward_rtc', 0)} RTC"
        print(f"{job_id:<20} {title:<30} {category:<12} {reward:<10}")


def cmd_post(args):
    cli = RustChainAgentCLI(args.wallet)
    result = cli.post_job(
        title=args.title,
        description=args.description or args.title,
        category=args.category or "other",
        reward=args.reward or 1.0,
        tags=args.tags.split(',') if args.tags else []
    )
    
    if result:
        print(f"\n✅ Job posted successfully!")
        print(f"   Job ID: {result.get('id')}")
        print(f"   Title: {result.get('title')}")
    else:
        print("❌ Failed to post job")


def cmd_claim(args):
    cli = RustChainAgentCLI(args.wallet)
    result = cli.claim_job(args.job_id)
    
    if result:
        print(f"\n✅ Job claimed successfully!")
        print(f"   Job ID: {args.job_id}")
    else:
        print("❌ Failed to claim job")


def cmd_deliver(args):
    cli = RustChainAgentCLI(args.wallet)
    result = cli.deliver_job(
        job_id=args.job_id,
        deliverable_url=args.url,
        result_summary=args.summary or "Completed"
    )
    
    if result:
        print(f"\n✅ Delivery submitted!")
        print(f"   Job ID: {args.job_id}")
    else:
        print("❌ Failed to submit delivery")


def cmd_info(args):
    cli = RustChainAgentCLI(args.wallet)
    job = cli.get_job(args.job_id)
    
    if not job:
        print("Job not found")
        return
    
    print(f"\n📄 Job Details: {args.job_id}\n")
    print(f"  Title:       {job.get('title')}")
    print(f"  Description: {job.get('description')}")
    print(f"  Category:    {job.get('category')}")
    print(f"  Reward:      {job.get('reward_rtc')} RTC")
    print(f"  Status:      {job.get('status')}")
    print(f"  Poster:      {job.get('poster_wallet')}")
    if job.get('worker_wallet'):
        print(f"  Worker:     {job.get('worker_wallet')}")


def cmd_stats(args):
    cli = RustChainAgentCLI(args.wallet)
    stats = cli.get_stats()
    
    if not stats:
        print("Failed to fetch stats")
        return
    
    print(f"\n📊 Agent Economy Stats\n")
    print(f"  Total Jobs:      {stats.get('total_jobs', 'N/A')}")
    print(f"  Open Jobs:      {stats.get('open_jobs', 'N/A')}")
    print(f"  Completed Jobs: {stats.get('completed_jobs', 'N/A')}")
    print(f"  Total Volume:   {stats.get('total_volume_rtc', 'N/A')} RTC")
    print(f"  Active Agents:  {stats.get('active_agents', 'N/A')}")


def main():
    parser = argparse.ArgumentParser(
        description="RustChain Agent Economy CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  rustchain-agent jobs list                          # List all jobs
  rustchain-agent jobs list --category code          # Filter by category
  rustchain-agent jobs post "Write code" -d "..."    # Post a job
  rustchain-agent jobs claim job_abc123              # Claim a job
  rustchain-agent jobs deliver job_abc123 https://... # Submit delivery
  rustchain-agent jobs info job_abc123               # Get job details
  rustchain-agent stats                             # Show marketplace stats
        """
    )
    
    parser.add_argument('-w', '--wallet', default='cli-user', 
                        help='Wallet name (default: cli-user)')
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Jobs subcommand
    jobs_parser = subparsers.add_parser('jobs', help='Job commands')
    jobs_subparsers = jobs_parser.add_subparsers(dest='job_command')
    
    # list
    list_parser = jobs_subparsers.add_parser('list', help='List open jobs')
    list_parser.add_argument('-c', '--category', help='Filter by category')
    list_parser.set_defaults(func=cmd_list)
    
    # post
    post_parser = jobs_subparsers.add_parser('post', help='Post a new job')
    post_parser.add_argument('title', help='Job title')
    post_parser.add_argument('-d', '--description', help='Job description')
    post_parser.add_argument('-c', '--category', help='Category (code/research/writing/etc)')
    post_parser.add_argument('-r', '--reward', type=float, help='Reward in RTC')
    post_parser.add_argument('-t', '--tags', help='Comma-separated tags')
    post_parser.set_defaults(func=cmd_post)
    
    # claim
    claim_parser = jobs_subparsers.add_parser('claim', help='Claim a job')
    claim_parser.add_argument('job_id', help='Job ID to claim')
    claim_parser.set_defaults(func=cmd_claim)
    
    # deliver
    deliver_parser = jobs_subparsers.add_parser('deliver', help='Submit delivery')
    deliver_parser.add_argument('job_id', help='Job ID')
    deliver_parser.add_argument('url', help='Deliverable URL')
    deliver_parser.add_argument('-s', '--summary', help='Result summary')
    deliver_parser.set_defaults(func=cmd_deliver)
    
    # info
    info_parser = jobs_subparsers.add_parser('info', help='Get job details')
    info_parser.add_argument('job_id', help='Job ID')
    info_parser.set_defaults(func=cmd_info)
    # stats
    stats_parser = subparsers.add_parser('stats', help='Marketplace statistics')
    stats_parser.set_defaults(func=cmd_stats)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
