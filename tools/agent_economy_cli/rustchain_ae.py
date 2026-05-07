#!/usr/bin/env python3
"""
rustchain-ae — Command-line interface for the RustChain Agent Economy (RIP-302)
"""
import sys
import json
import argparse
import urllib.request
import urllib.error

BASE_URL = "https://50.28.86.131"
VERIFY_SSL = False

# TLS verification enabled by default
# To skip (not recommended), set RC_SKIP_TLS_VERIFY=1
import ssl
SSL_CTX = ssl.create_default_context()
if os.environ.get('RC_SKIP_TLS_VERIFY', '0') == '1':
    SSL_CTX.check_hostname = False
    SSL_CTX.verify_mode = ssl.CERT_NONE

def api_get(path):
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, context=SSL_CTX, timeout=15) as resp:
        return json.loads(resp.read().decode())

def api_post(path, data):
    url = f"{BASE_URL}{path}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method='POST',
        headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode())

def cmd_list(args):
    """List open jobs in the Agent Economy marketplace"""
    status = args.status if hasattr(args, 'status') and args.status else 'open'
    try:
        jobs = api_get(f"/agent/jobs?status={status}")
        if not jobs:
            print("No jobs found.")
            return
        if isinstance(jobs, dict):
            jobs = jobs.get('jobs', [])
        print(f"\n{'ID':<20} {'Reward':>8}  {'Title'}")
        print("-" * 70)
        for job in jobs[:20]:
            jid = job.get('id', '?')[:18]
            reward = f"{job.get('reward_rtc', '?')} RTC"
            title = job.get('title', '?')[:40]
            print(f"{jid:<20} {reward:>8}  {title}")
        print(f"\n{len(jobs)} job(s) found.")
    except Exception as e:
        print(f"Error: {e}")

def cmd_show(args):
    """Show details of a specific job"""
    try:
        job = api_get(f"/agent/jobs/{args.job_id}")
        print(json.dumps(job, indent=2))
    except Exception as e:
        print(f"Error: {e}")

def cmd_claim(args):
    """Claim a job"""
    payload = {"agent_id": args.wallet, "proposal": args.proposal}
    result = api_post(f"/agent/jobs/{args.job_id}/claim", payload)
    print(json.dumps(result, indent=2))

def cmd_deliver(args):
    """Deliver work for a claimed job"""
    payload = {"deliverable_url": args.url, "result_summary": args.summary}
    result = api_post(f"/agent/jobs/{args.job_id}/deliver", payload)
    print(json.dumps(result, indent=2))

def cmd_post(args):
    """Post a new job to the marketplace"""
    payload = {
        "title": args.title,
        "description": args.description,
        "reward_rtc": args.reward,
        "deadline_hours": args.deadline,
        "poster_wallet": args.wallet,
        "required_skills": args.skills.split(',') if args.skills else []
    }
    result = api_post("/agent/jobs", payload)
    print(json.dumps(result, indent=2))

def cmd_reputation(args):
    """Check reputation for a wallet"""
    try:
        rep = api_get(f"/agent/reputation/{args.wallet}")
        print(json.dumps(rep, indent=2))
    except Exception as e:
        print(f"Error: {e}")

def cmd_stats(args):
    """Show Agent Economy marketplace statistics"""
    try:
        stats = api_get("/agent/stats")
        print(json.dumps(stats, indent=2))
    except Exception as e:
        print(f"Error: {e}")

def main():
    parser = argparse.ArgumentParser(
        prog='rustchain-ae',
        description='RustChain Agent Economy CLI (RIP-302)'
    )
    sub = parser.add_subparsers(dest='command', help='Command')

    # list
    p_list = sub.add_parser('list', help='List jobs')
    p_list.add_argument('--status', default='open', choices=['open', 'claimed', 'delivered', 'completed'],
        help='Job status filter (default: open)')
    p_list.set_defaults(func=cmd_list)

    # show
    p_show = sub.add_parser('show', help='Show job details')
    p_show.add_argument('job_id', help='Job ID')
    p_show.set_defaults(func=cmd_show)

    # claim
    p_claim = sub.add_parser('claim', help='Claim a job')
    p_claim.add_argument('job_id', help='Job ID')
    p_claim.add_argument('--wallet', required=True, help='Your wallet name')
    p_claim.add_argument('--proposal', required=True, help='Your delivery proposal')
    p_claim.set_defaults(func=cmd_claim)

    # deliver
    p_deliver = sub.add_parser('deliver', help='Deliver work for a job')
    p_deliver.add_argument('job_id', help='Job ID')
    p_deliver.add_argument('--url', required=True, help='Deliverable URL (GitHub, Gist, etc.)')
    p_deliver.add_argument('--summary', required=True, help='What you built')
    p_deliver.set_defaults(func=cmd_deliver)

    # post
    p_post = sub.add_parser('post', help='Post a new job')
    p_post.add_argument('--title', required=True, help='Job title')
    p_post.add_argument('--description', required=True, help='Job description')
    p_post.add_argument('--reward', type=float, required=True, help='Reward in RTC')
    p_post.add_argument('--deadline', type=int, default=24, help='Deadline in hours (default: 24)')
    p_post.add_argument('--wallet', required=True, help='Your poster wallet name')
    p_post.add_argument('--skills', default='', help='Comma-separated required skills')
    p_post.set_defaults(func=cmd_post)

    # reputation
    p_rep = sub.add_parser('reputation', help='Check wallet reputation')
    p_rep.add_argument('wallet', help='Wallet name to check')
    p_rep.set_defaults(func=cmd_reputation)

    # stats
    p_stats = sub.add_parser('stats', help='Marketplace statistics')
    p_stats.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    args.func(args)

if __name__ == '__main__':
    main()
