import requests
import json
from typing import List, Dict

class BountyScanner:
    """
    Scans GitHub repositories for open bounties.
    """
    def __init__(self, token: str):
        self.headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        self.base_url = "https://api.github.com"

    def find_bounties(self, repo: str) -> List[Dict]:
        """Find open issues with the 'bounty' label."""
        url = f"{self.base_url}/repos/{repo}/issues"
        params = {"labels": "bounty", "state": "open"}
        r = requests.get(url, headers=self.headers, params=params)
        r.raise_for_status()
        return r.json()

    def evaluate_difficulty(self, issue: Dict) -> int:
        """
        Heuristic evaluation of issue difficulty (1-10).
        Matches keywords against agent capabilities.
        """
        text = (issue.get('title', '') + issue.get('body', '')).lower()
        score = 5 # Default
        
        # Capability match
        if "python" in text: score -= 2
        if "sdk" in text: score -= 1
        if "vintage" in text or "hardware" in text: score += 4 # Hard for pure AI
        
        return max(1, min(10, score))
