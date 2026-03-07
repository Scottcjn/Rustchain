#!/usr/bin/env python3
"""
RustChain Bounty Claims Integration Example

This script demonstrates how to integrate with the RustChain Bounty Claims System
using both direct API calls and the Python SDK.

Requirements:
    - Python 3.8+
    - requests library
    - rustchain-sdk (optional, for SDK example)

Usage:
    python example_bounty_integration.py
"""

import json
import time
import hashlib
import hmac
from typing import Dict, Any, Optional

# Try to import SDK, fall back to direct HTTP
try:
    from rustchain import RustChainClient, BountyError
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    import requests


class BountyClaimsIntegration:
    """
    Integration class for RustChain Bounty Claims System.
    
    Supports both SDK and direct HTTP API usage.
    """
    
    def __init__(self, base_url: str = "https://rustchain.org", admin_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.admin_key = admin_key
        
        if SDK_AVAILABLE:
            self.client = RustChainClient(base_url, verify_ssl=False)
            print(f"✓ Using RustChain SDK")
        else:
            self.client = None
            self.session = requests.Session()
            print(f"✓ Using direct HTTP API")
    
    def list_bounties(self) -> Dict[str, Any]:
        """List all available bounties."""
        if self.client:
            bounties = self.client.list_bounties()
            return {"bounties": bounties, "count": len(bounties)}
        else:
            response = self.session.get(f"{self.base_url}/api/bounty/list")
            response.raise_for_status()
            return response.json()
    
    def submit_claim(
        self,
        bounty_id: str,
        miner_id: str,
        description: str,
        github_pr_url: Optional[str] = None,
        commit_hash: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit a new bounty claim."""
        payload = {
            "bounty_id": bounty_id,
            "claimant_miner_id": miner_id,
            "description": description,
        }
        
        if github_pr_url:
            payload["github_pr_url"] = github_pr_url
        if commit_hash:
            payload["commit_hash"] = commit_hash
        
        if self.client:
            try:
                result = self.client.submit_bounty_claim(**payload)
                return {"success": True, "result": result}
            except BountyError as e:
                return {"success": False, "error": str(e), "response": e.response}
        else:
            response = self.session.post(
                f"{self.base_url}/api/bounty/claims",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            return response.json()
    
    def get_claim(self, claim_id: str) -> Dict[str, Any]:
        """Get claim details."""
        if self.client:
            result = self.client.get_bounty_claim(claim_id)
            return {"success": True, "claim": result}
        else:
            response = self.session.get(f"{self.base_url}/api/bounty/claims/{claim_id}")
            if response.status_code == 404:
                return {"success": False, "error": "Claim not found"}
            response.raise_for_status()
            return {"success": True, "claim": response.json()}
    
    def get_miner_claims(self, miner_id: str, limit: int = 50) -> Dict[str, Any]:
        """Get all claims for a miner."""
        if self.client:
            claims = self.client.get_miner_bounty_claims(miner_id, limit=limit)
            return {"miner_id": miner_id, "claims": claims, "count": len(claims)}
        else:
            response = self.session.get(
                f"{self.base_url}/api/bounty/claims/miner/{miner_id}",
                params={"limit": limit}
            )
            response.raise_for_status()
            return response.json()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get bounty statistics."""
        if self.client:
            stats = self.client.get_bounty_statistics()
            return {"success": True, "statistics": stats}
        else:
            response = self.session.get(f"{self.base_url}/api/bounty/statistics")
            response.raise_for_status()
            return {"success": True, "statistics": response.json()}
    
    # Admin operations
    def update_claim_status(
        self,
        claim_id: str,
        status: str,
        reviewer_notes: Optional[str] = None,
        reward_amount_rtc: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Update claim status (admin only)."""
        if not self.admin_key:
            return {"success": False, "error": "Admin key required"}
        
        payload = {
            "status": status,
        }
        
        if reviewer_notes:
            payload["reviewer_notes"] = reviewer_notes
        if reward_amount_rtc is not None:
            payload["reward_amount_rtc"] = reward_amount_rtc
        
        if self.client:
            # SDK doesn't have admin methods yet, use direct HTTP
            pass
        
        response = self.session.put(
            f"{self.base_url}/api/bounty/claims/{claim_id}/status",
            json=payload,
            headers={"X-Admin-Key": self.admin_key}
        )
        
        if response.status_code == 401:
            return {"success": False, "error": "Unauthorized"}
        response.raise_for_status()
        return {"success": True, "result": response.json()}
    
    def close(self):
        """Clean up resources."""
        if self.client:
            self.client.close()
        else:
            self.session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def example_list_bounties():
    """Example: List all available bounties."""
    print("\n" + "="*60)
    print("EXAMPLE: List Available Bounties")
    print("="*60)
    
    with BountyClaimsIntegration() as integration:
        result = integration.list_bounties()
        
        print(f"\nFound {result['count']} bounties:\n")
        for bounty in result.get("bounties", []):
            print(f"  • {bounty['title']}")
            print(f"    ID: {bounty['bounty_id']}")
            print(f"    Reward: {bounty['reward']}")
            print(f"    Claims: {bounty.get('claim_count', 0)} total, {bounty.get('pending_claims', 0)} pending")
            print()


def example_submit_claim():
    """Example: Submit a bounty claim."""
    print("\n" + "="*60)
    print("EXAMPLE: Submit Bounty Claim")
    print("="*60)
    
    with BountyClaimsIntegration() as integration:
        result = integration.submit_claim(
            bounty_id="bounty_dos_port",
            miner_id="RTC_example_miner_123",
            description="Completed MS-DOS validator with BIOS date entropy and FAT filesystem output. "
                       "The validator runs on FreeDOS 1.2 and generates proof_of_antiquity.json with "
                       "hardware fingerprint including BIOS date, CPU type, and entropy from loop delays.",
            github_pr_url="https://github.com/example/rustchain-dos/pull/1",
            commit_hash="abc1234",
        )
        
        if result.get("success"):
            claim = result.get("result", {})
            print(f"\n✓ Claim submitted successfully!")
            print(f"  Claim ID: {claim.get('claim_id', 'N/A')}")
            print(f"  Status: {claim.get('status', 'N/A')}")
            print(f"  Submitted at: {claim.get('submitted_at', 'N/A')}")
        else:
            print(f"\n✗ Claim submission failed:")
            print(f"  Error: {result.get('error', 'Unknown error')}")


def example_get_statistics():
    """Example: Get bounty statistics."""
    print("\n" + "="*60)
    print("EXAMPLE: Get Bounty Statistics")
    print("="*60)
    
    with BountyClaimsIntegration() as integration:
        result = integration.get_statistics()
        
        if result.get("success"):
            stats = result.get("statistics", {})
            print(f"\n📊 Bounty Claims Statistics:\n")
            print(f"  Total Claims: {stats.get('total_claims', 0)}")
            print(f"  Total Rewards Paid: {stats.get('total_rewards_paid_rtc', 0)} RTC")
            print(f"\n  Status Breakdown:")
            
            status_breakdown = stats.get("status_breakdown", {})
            for status, count in status_breakdown.items():
                print(f"    • {status}: {count}")
            
            print(f"\n  By Bounty:")
            by_bounty = stats.get("by_bounty", {})
            for bounty_id, breakdown in by_bounty.items():
                total = sum(breakdown.values())
                print(f"    • {bounty_id}: {total} claims")
        else:
            print(f"\n✗ Failed to get statistics: {result.get('error', 'Unknown error')}")


def example_miner_dashboard():
    """Example: Create a miner claims dashboard."""
    print("\n" + "="*60)
    print("EXAMPLE: Miner Claims Dashboard")
    print("="*60)
    
    miner_id = "RTC_example_miner_123"
    
    with BountyClaimsIntegration() as integration:
        result = integration.get_miner_claims(miner_id, limit=10)
        
        print(f"\n📋 Claims for {miner_id}:\n")
        
        claims = result.get("claims", [])
        if not claims:
            print("  No claims found.")
            return
        
        for claim in claims:
            status_icon = {
                "pending": "⏳",
                "under_review": "🔍",
                "approved": "✓",
                "rejected": "✗",
            }.get(claim.get("status", ""), "•")
            
            print(f"  {status_icon} {claim.get('claim_id', 'N/A')}")
            print(f"     Bounty: {claim.get('bounty_id', 'N/A')}")
            print(f"     Status: {claim.get('status', 'N/A')}")
            
            if claim.get("github_pr_url"):
                print(f"     PR: {claim['github_pr_url']}")
            
            if claim.get("reward_amount_rtc"):
                print(f"     Reward: {claim['reward_amount_rtc']} RTC")
                if claim.get("reward_paid"):
                    print(f"     Payment: ✓ Paid")
                else:
                    print(f"     Payment: ⏳ Pending")
            
            print()


def main():
    """Run all examples."""
    print("\n" + "="*60)
    print("RustChain Bounty Claims Integration Examples")
    print("="*60)
    print(f"\nSDK Available: {SDK_AVAILABLE}")
    print(f"Base URL: https://rustchain.org")
    
    # Run examples
    # Note: These examples will fail if the node is not running
    # Uncomment to test with a live node:
    
    # example_list_bounties()
    # example_submit_claim()
    # example_get_statistics()
    # example_miner_dashboard()
    
    print("\n" + "="*60)
    print("Examples completed!")
    print("="*60)
    print("\nTo test with a live node, uncomment the example calls in main().")
    print("Make sure to set the correct base_url for your node.")


if __name__ == "__main__":
    main()
