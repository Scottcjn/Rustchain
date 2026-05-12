# SPDX-License-Identifier: MIT

import os
import re
import json
import time
import requests
import yaml
from typing import List, Dict, Any, Optional
from github import Github, GithubException
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configuration
CONFIG = {
    "org": "Scottcjn",
    "repos": ["Rustchain", "rustchain-bounties", "bottube"],
    "miner_node_url": "https://50.28.86.131",
    "star_reward": 1.0,
    "follow_reward": 1.0,
    "star_king_bonus": 25.0,
    "star_king_threshold": 100
}

class BountyVerifier:
    def __init__(self):
        self.gh = Github(os.getenv("GITHUB_TOKEN"))
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = genai.GenerativeModel('gemini-1.5-pro')

    def verify_stars(self, username: str) -> Dict[str, Any]:
        """Verify Scottcjn repos starred by user."""
        try:
            user = self.gh.get_user(username)
            starred = user.get_starred()
            scott_stars = [repo.full_name for repo in starred if repo.owner.login == CONFIG["org"]]
            
            return {
                "count": len(scott_stars),
                "is_star_king": len(scott_stars) >= CONFIG["star_king_threshold"],
                "repos": scott_stars[:10]  # Sample
            }
        except GithubException as e:
            return {"error": str(e), "count": 0}

    def verify_following(self, username: str) -> bool:
        """Check if user follows Scottcjn."""
        try:
            # PyGithub follow check is direct
            user = self.gh.get_user(username)
            return self.gh.get_user(CONFIG["org"]).has_in_followers(user)
        except GithubException:
            return False

    def verify_wallet(self, wallet_name: str) -> Dict[str, Any]:
        """Check wallet existence and balance on RustChain node."""
        try:
            resp = requests.get(
                f"{CONFIG['miner_node_url']}/wallet/balance?miner_id={wallet_name}",
                verify=os.path.expanduser("~/.rustchain/node_cert.pem") if os.path.exists(os.path.expanduser("~/.rustchain/node_cert.pem")) else True,
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                return {"exists": True, "balance": data.get("balance", 0)}
            return {"exists": False, "error": resp.status_code}
        except Exception as e:
            return {"exists": False, "error": str(e)}

    def ai_quality_check(self, content: str) -> Dict[str, Any]:
        """Use Gemini to evaluate article/contribution quality."""
        prompt = f"""
        Evaluate the following technical contribution for the RustChain ecosystem.
        Identify: 1. Technical Depth (0-10), 2. Clarity (0-10), 3. Originality (0-10).
        Return a JSON object with these scores and a short summary.
        
        Contribution Content:
        {content[:4000]}
        """
        try:
            response = self.model.generate_content(prompt)
            # Simple extract JSON from response
            match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if match:
                return json.loads(match.group())
            return {"error": "AI response format invalid"}
        except Exception as e:
            return {"error": str(e)}

    def generate_report(self, username: str, wallet: str, article_url: Optional[str] = None) -> str:
        """Compile a full markdown report."""
        stars = self.verify_stars(username)
        follows = self.verify_following(username)
        wallet_info = self.verify_wallet(wallet)
        
        payout = stars["count"] * CONFIG["star_reward"]
        if follows: payout += CONFIG["follow_reward"]
        if stars["is_star_king"]: payout += CONFIG["star_king_bonus"]
        
        report = f"## 🤖 Automated Verification for @{username}\n\n"
        report += "| Check | Result |\n"
        report += "|-------|--------|\n"
        report += f"| Follows @{CONFIG['org']} | {'✅ Yes' if follows else '❌ No'} |\n"
        report += f"| {CONFIG['org']} repos starred | {stars['count']} |\n"
        report += f"| Wallet \\`{wallet}\\` exists | {'✅ Balance: ' + str(wallet_info['balance']) + ' RTC' if wallet_info['exists'] else '❌ Not found'} |\n"
        
        if article_url:
            # Mock content fetch
            article_status = "✅ Live" if requests.head(article_url).status_code == 200 else "❌ Broken"
            report += f"| Article link | {article_status} |\n"
            
        report += f"\n**Suggested payout**: **{payout} RTC**\n"
        report += "\n---\n*Verified by Bounty Verification Bot PRO 🦾*"
        return report

if __name__ == "__main__":
    # CLI mode
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", required=True)
    parser.add_argument("--wallet", required=True)
    parser.add_argument("--article", required=False)
    args = parser.parse_args()
    
    verifier = BountyVerifier()
    print(verifier.generate_report(args.user, args.wallet, args.article))
