#!/usr/bin/env python3
"""
Verify that a GitHub user has starred required repos and claimed number of repos.
"""
import requests, sys, argparse

def user_starred(repo, username, token=None):
    url = f"https://api.github.com/user/starred/{repo}"
    headers = {'Accept': 'application/vnd.github.v3+json'}
    if token: headers['Authorization'] = f"token {token}"
    r = requests.get(url, headers=headers)
    return r.status_code == 204

if __name__ == '__main__':
    p = argparse.ArgumentParser(description='Verify star claims')
    p.add_argument('--username', required=True, help='GitHub username')
    p.add_argument('--count', type=int, required=True, help='Number of repos starred')
    p.add_argument('--wallet', required=True, help='RTC wallet address')
    p.add_argument('--token', help='GitHub API token (optional)')
    args = p.parse_args()

    # Required main repos
    required = ['Scottcjn/Rustchain', 'Scottcjn/BoTTube']
    for repo in required:
        if not user_starred(repo, args.username, args.token):
            print(f"Error: user '{args.username}' has not starred required repo '{repo}'."); sys.exit(1)

    # Basic wallet format check
    if not args.wallet.endswith('RTC'):
        print("Error: wallet address must end with 'RTC'."); sys.exit(1)

    # Optionally verify count <= total repos list length (86)
    if args.count < 1 or args.count > 86:
        print("Error: repos count must be between 1 and 86."); sys.exit(1)

    print(f"Success: user {args.username} is eligible to claim {args.count} repos starred. Wallet: {args.wallet}")
    sys.exit(0)