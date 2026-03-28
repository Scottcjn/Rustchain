#!/usr/bin/env python3
"""
agent_economy_cli.py — CLI for the RustChain Agent Economy (RIP-302)

Usage:
    python agent_economy_cli.py [--node URL] [--json] <command> [args...]

Commands:
    list-jobs   [--status open|claimed|delivered]
    view-job    <id>
    post-job    --title TITLE --desc DESC --reward FLOAT --wallet ADDR
    claim-job   <id> --wallet ADDR
    deliver     <id> <url> --wallet ADDR
    accept      <id> --wallet ADDR
    dispute     <id> --reason TEXT --wallet ADDR
    reputation  <wallet>
    stats
"""

import argparse
import json
import sys
from typing import Any

try:
    from agent_economy_sdk import AgentEconomyClient, AgentEconomyError
except ImportError:
    # Allow running from project root
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from agent_economy_sdk import AgentEconomyClient, AgentEconomyError


# ---------------------------------------------------------------------------
# Pretty-print helpers
# ---------------------------------------------------------------------------

def _hr(width: int = 60) -> str:
    return "─" * width


def _print_job(job: dict) -> None:
    print(_hr())
    print(f"  ID       : {job.get('id', 'n/a')}")
    print(f"  Title    : {job.get('title', 'n/a')}")
    print(f"  Status   : {job.get('status', 'n/a')}")
    print(f"  Reward   : {job.get('reward_rtc', 'n/a')} RTC")
    print(f"  Poster   : {job.get('wallet', job.get('poster_wallet', 'n/a'))}")
    if job.get("claimer_wallet"):
        print(f"  Claimer  : {job['claimer_wallet']}")
    if job.get("deliverable_url"):
        print(f"  Delivery : {job['deliverable_url']}")
    if job.get("description"):
        print(f"  Desc     : {job['description']}")
    print(_hr())


def _print_jobs_table(jobs: list) -> None:
    if not jobs:
        print("No jobs found.")
        return
    col_id     = max(len(str(j.get("id", ""))) for j in jobs)
    col_status = max(len(str(j.get("status", ""))) for j in jobs)
    col_reward = max(len(str(j.get("reward_rtc", ""))) for j in jobs)
    col_title  = max(len(str(j.get("title", ""))) for j in jobs)

    col_id     = max(col_id, 8)
    col_status = max(col_status, 8)
    col_reward = max(col_reward, 10)
    col_title  = max(col_title, 20)

    header = (
        f"{'ID':<{col_id}}  {'STATUS':<{col_status}}  "
        f"{'REWARD (RTC)':<{col_reward}}  {'TITLE':<{col_title}}"
    )
    print(_hr(len(header)))
    print(header)
    print(_hr(len(header)))
    for j in jobs:
        print(
            f"{str(j.get('id','')):<{col_id}}  "
            f"{str(j.get('status','')):<{col_status}}  "
            f"{str(j.get('reward_rtc','')):<{col_reward}}  "
            f"{str(j.get('title','')):<{col_title}}"
        )
    print(_hr(len(header)))
    print(f"  {len(jobs)} job(s) listed.")


def _print_stats(stats: dict) -> None:
    print(_hr())
    print("  Agent Economy Marketplace — Statistics")
    print(_hr())
    for k, v in stats.items():
        label = k.replace("_", " ").title()
        print(f"  {label:<30}: {v}")
    print(_hr())


def _print_reputation(rep: dict, wallet: str) -> None:
    print(_hr())
    print(f"  Reputation for {wallet}")
    print(_hr())
    for k, v in rep.items():
        label = k.replace("_", " ").title()
        print(f"  {label:<30}: {v}")
    print(_hr())


def _output(data: Any, as_json: bool) -> None:
    """Print data as JSON or pretty-formatted."""
    if as_json:
        print(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_list_jobs(client: AgentEconomyClient, args: argparse.Namespace) -> None:
    jobs = client.list_jobs(status=args.status)
    if args.json:
        _output(jobs, True)
    else:
        _print_jobs_table(jobs if isinstance(jobs, list) else jobs.get("jobs", [jobs]))


def cmd_view_job(client: AgentEconomyClient, args: argparse.Namespace) -> None:
    job = client.get_job(args.id)
    if args.json:
        _output(job, True)
    else:
        _print_job(job)


def cmd_post_job(client: AgentEconomyClient, args: argparse.Namespace) -> None:
    result = client.post_job(
        title=args.title,
        description=args.desc,
        reward_rtc=args.reward,
        wallet=args.wallet,
    )
    if args.json:
        _output(result, True)
    else:
        print("✅  Job posted successfully!")
        _print_job(result if isinstance(result, dict) else {"id": result})


def cmd_claim_job(client: AgentEconomyClient, args: argparse.Namespace) -> None:
    result = client.claim_job(args.id, args.wallet)
    if args.json:
        _output(result, True)
    else:
        print(f"✅  Job {args.id} claimed by {args.wallet}")
        if isinstance(result, dict):
            _print_job(result)


def cmd_deliver(client: AgentEconomyClient, args: argparse.Namespace) -> None:
    result = client.deliver(args.id, args.url, args.wallet)
    if args.json:
        _output(result, True)
    else:
        print(f"✅  Deliverable submitted for job {args.id}")
        print(f"   URL    : {args.url}")
        print(f"   Wallet : {args.wallet}")


def cmd_accept(client: AgentEconomyClient, args: argparse.Namespace) -> None:
    result = client.accept(args.id, args.wallet)
    if args.json:
        _output(result, True)
    else:
        print(f"✅  Job {args.id} accepted — escrow released!")
        if isinstance(result, dict):
            _print_job(result)


def cmd_dispute(client: AgentEconomyClient, args: argparse.Namespace) -> None:
    result = client.dispute(args.id, args.reason, args.wallet)
    if args.json:
        _output(result, True)
    else:
        print(f"⚠️   Dispute filed for job {args.id}")
        print(f"   Reason : {args.reason}")
        if isinstance(result, dict):
            print(json.dumps(result, indent=2))


def cmd_reputation(client: AgentEconomyClient, args: argparse.Namespace) -> None:
    rep = client.get_reputation(args.wallet)
    if args.json:
        _output(rep, True)
    else:
        _print_reputation(rep, args.wallet)


def cmd_stats(client: AgentEconomyClient, args: argparse.Namespace) -> None:
    stats = client.get_stats()
    if args.json:
        _output(stats, True)
    else:
        _print_stats(stats)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-economy",
        description="CLI for the RustChain Agent Economy marketplace (RIP-302)",
    )
    parser.add_argument(
        "--node",
        default=AgentEconomyClient.DEFAULT_BASE_URL,
        metavar="URL",
        help=f"Node base URL (default: {AgentEconomyClient.DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of formatted tables",
    )
    parser.add_argument(
        "--no-verify-ssl",
        action="store_true",
        default=True,
        help="Skip SSL certificate verification (default for self-signed nodes)",
    )

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # list-jobs
    p_list = sub.add_parser("list-jobs", help="Browse open jobs")
    p_list.add_argument(
        "--status",
        choices=["open", "claimed", "delivered", "completed", "disputed"],
        help="Filter by job status",
    )

    # view-job
    p_view = sub.add_parser("view-job", help="View a specific job")
    p_view.add_argument("id", help="Job ID")

    # post-job
    p_post = sub.add_parser("post-job", help="Post a new job (locks RTC escrow)")
    p_post.add_argument("--title",  required=True, help="Job title")
    p_post.add_argument("--desc",   required=True, help="Job description")
    p_post.add_argument("--reward", required=True, type=float, help="Reward in RTC")
    p_post.add_argument("--wallet", required=True, help="Your RTC wallet address")

    # claim-job
    p_claim = sub.add_parser("claim-job", help="Claim an open job")
    p_claim.add_argument("id", help="Job ID to claim")
    p_claim.add_argument("--wallet", required=True, help="Your RTC wallet address")

    # deliver
    p_deliver = sub.add_parser("deliver", help="Submit a deliverable for a job")
    p_deliver.add_argument("id",  help="Job ID")
    p_deliver.add_argument("url", help="Deliverable URL (PR, IPFS, etc.)")
    p_deliver.add_argument("--wallet", required=True, help="Your RTC wallet address")

    # accept
    p_accept = sub.add_parser("accept", help="Accept delivery and release escrow")
    p_accept.add_argument("id", help="Job ID")
    p_accept.add_argument("--wallet", required=True, help="Your RTC wallet (poster)")

    # dispute
    p_dispute = sub.add_parser("dispute", help="Dispute / reject a delivery")
    p_dispute.add_argument("id", help="Job ID")
    p_dispute.add_argument("--reason", required=True, help="Reason for dispute")
    p_dispute.add_argument("--wallet", required=True, help="Your RTC wallet address")

    # reputation
    p_rep = sub.add_parser("reputation", help="Check reputation for a wallet")
    p_rep.add_argument("wallet", help="RTC wallet address")

    # stats
    sub.add_parser("stats", help="Marketplace-wide statistics")

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

COMMANDS = {
    "list-jobs":  cmd_list_jobs,
    "view-job":   cmd_view_job,
    "post-job":   cmd_post_job,
    "claim-job":  cmd_claim_job,
    "deliver":    cmd_deliver,
    "accept":     cmd_accept,
    "dispute":    cmd_dispute,
    "reputation": cmd_reputation,
    "stats":      cmd_stats,
}


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    client = AgentEconomyClient(
        base_url=args.node,
        verify_ssl=not args.no_verify_ssl,
    )

    handler = COMMANDS.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    try:
        handler(client, args)
    except AgentEconomyError as exc:
        print(f"❌  API error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        print(f"❌  Unexpected error: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
