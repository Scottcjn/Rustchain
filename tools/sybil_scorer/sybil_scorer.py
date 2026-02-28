#!/usr/bin/env python3
"""
Sybil/Farming Risk Scorer for Bounty Claims

Flags likely bounty farming/Sybil behavior in claim triage.

Usage:
    python sybil_scorer.py --claims claims.json --output report.txt
"""

import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from dataclasses import dataclass
import argparse


@dataclass
class Claim:
    """A bounty claim."""
    issue_number: int
    claimant: str
    wallet: str
    timestamp: str
    comment: str
    account_age_days: int = 0
    repo: str = ""


class RiskScorer:
    """Scores claims for farming/Sybil risk."""
    
    def __init__(self):
        self.reason_codes = {}
    
    def score_account_age(self, claim: Claim) -> Tuple[float, str]:
        """Check account age heuristic."""
        if claim.account_age_days < 7:
            return 30.0, "account_age_under_7_days"
        elif claim.account_age_days < 30:
            return 15.0, "account_age_under_30_days"
        return 0.0, ""
    
    def score_claim_velocity(self, claims: List[Claim]) -> Dict[str, Tuple[float, str]]:
        """Check claim velocity heuristic (burst behavior)."""
        if len(claims) < 3:
            return {}
        
        # Sort by timestamp
        sorted_claims = sorted(claims, key=lambda c: c.timestamp)
        
        # Check for multiple claims in short time
        if len(sorted_claims) >= 3:
            first = datetime.fromisoformat(sorted_claims[0].timestamp)
            last = datetime.fromisoformat(sorted_claims[-1].timestamp)
            hours = (last - first).total_seconds() / 3600
            
            if hours < 1 and len(claims) >= 3:
                return {c.claimant: (25.0, "burst_claims_1_hour") for c in claims}
            elif hours < 24 and len(claims) >= 5:
                return {c.claimant: (15.0, "burst_claims_24_hours") for c in claims}
        
        return {}
    
    def score_text_similarity(self, claims: List[Claim]) -> Dict[str, Tuple[float, str]]:
        """Check text similarity/template reuse."""
        texts = [c.comment.lower() for c in claims]
        
        # Simple template detection
        templates = {}
        for i, text in enumerate(texts):
            # Check for common patterns
            if "wallet:" in text and "github:" in text:
                templates[i] = "wallet_github_template"
        
        # Find duplicates
        duplicates = {}
        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                similarity = self._text_similarity(texts[i], texts[j])
                if similarity > 0.8:
                    duplicates[claims[i].claimant] = (20.0, "high_text_similarity")
                    duplicates[claims[j].claimant] = (20.0, "high_text_similarity")
        
        return duplicates
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity."""
        words1 = set(text1.split())
        words2 = set(text2.split())
        if not words1 or not words2:
            return 0.0
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        return intersection / union if union > 0 else 0.0
    
    def score_wallet_pattern(self, claim: Claim) -> Tuple[float, str]:
        """Check wallet/repo cross-pattern."""
        # Check for generic wallet names
        generic_patterns = [
            r'^test\d*$',
            r'^temp\d*$',
            r'^wallet\d*$',
            r'^[a-z]{1,3}$',
        ]
        
        for pattern in generic_patterns:
            if re.match(pattern, claim.wallet.lower()):
                return 10.0, "generic_wallet_name"
        
        return 0.0, ""
    
    def score_duplicate_proof(self, claims: List[Claim]) -> Dict[str, Tuple[float, str]]:
        """Check for duplicate proof links."""
        links = {}
        for claim in claims:
            # Extract URLs from comment
            urls = re.findall(r'https?://[^\s]+', claim.comment)
            for url in urls:
                if url in links:
                    return {claim.claimant: (15.0, "duplicate_proof_link")}
                links[url] = claim.claimant
        
        return {}
    
    def score_all(self, claims: List[Claim]) -> List[Dict]:
        """Score all claims and return results."""
        results = []
        velocity_scores = self.score_claim_velocity(claims)
        similarity_scores = self.score_text_similarity(claims)
        duplicate_scores = self.score_duplicate_proof(claims)
        
        for claim in claims:
            total_score = 0.0
            reasons = []
            
            # Account age
            score, reason = self.score_account_age(claim)
            total_score += score
            if reason:
                reasons.append(reason)
            
            # Claim velocity
            if claim.claimant in velocity_scores:
                score, reason = velocity_scores[claim.claimant]
                total_score += score
                reasons.append(reason)
            
            # Text similarity
            if claim.claimant in similarity_scores:
                score, reason = similarity_scores[claim.claimant]
                total_score += score
                reasons.append(reason)
            
            # Wallet pattern
            score, reason = self.score_wallet_pattern(claim)
            total_score += score
            if reason:
                reasons.append(reason)
            
            # Duplicate proof
            if claim.claimant in duplicate_scores:
                score, reason = duplicate_scores[claim.claimant]
                total_score += score
                reasons.append(reason)
            
            # Determine risk level
            if total_score >= 50:
                risk_level = "high"
            elif total_score >= 25:
                risk_level = "medium"
            else:
                risk_level = "low"
            
            results.append({
                "issue": claim.issue_number,
                "claimant": claim.claimant,
                "wallet": claim.wallet,
                "score": round(total_score, 2),
                "risk_level": risk_level,
                "reasons": reasons
            })
        
        # Sort by score descending
        return sorted(results, key=lambda x: x["score"], reverse=True)
    
    def generate_report(self, results: List[Dict], output_path: str):
        """Generate triage report."""
        with open(output_path, "w") as f:
            f.write("=" * 60 + "\n")
            f.write("SYBIL/FARMING RISK SCORE REPORT\n")
            f.write("=" * 60 + "\n\n")
            
            high = [r for r in results if r["risk_level"] == "high"]
            medium = [r for r in results if r["risk_level"] == "medium"]
            low = [r for r in results if r["risk_level"] == "low"]
            
            f.write(f"Total Claims: {len(results)}\n")
            f.write(f"High Risk: {len(high)}\n")
            f.write(f"Medium Risk: {len(medium)}\n")
            f.write(f"Low Risk: {len(low)}\n\n")
            
            if high:
                f.write("=" * 60 + "\n")
                f.write("HIGH RISK CLAIMS (Review Required)\n")
                f.write("=" * 60 + "\n")
                for r in high:
                    f.write(f"\n#{r['issue']} - {r['claimant']}\n")
                    f.write(f"  Score: {r['score']}\n")
                    f.write(f"  Wallet: {r['wallet']}\n")
                    f.write(f"  Reasons: {', '.join(r['reasons'])}\n")
            
            if medium:
                f.write("\n" + "=" * 60 + "\n")
                f.write("MEDIUM RISK CLAIMS (Monitor)\n")
                f.write("=" * 60 + "\n")
                for r in medium[:10]:  # Top 10
                    f.write(f"  #{r['issue']} - {r['claimant']}: {r['score']}\n")
            
            f.write("\n" + "=" * 60 + "\n")
            f.write("REASON CODES\n")
            f.write("=" * 60 + "\n")
            f.write("account_age_under_7_days: Account < 7 days old\n")
            f.write("account_age_under_30_days: Account < 30 days old\n")
            f.write("burst_claims_1_hour: 3+ claims in 1 hour\n")
            f.write("burst_claims_24_hours: 5+ claims in 24 hours\n")
            f.write("high_text_similarity: >80% text similarity with another claim\n")
            f.write("generic_wallet_name: Generic wallet name pattern\n")
            f.write("duplicate_proof_link: Same proof URL as another claim\n")


def main():
    parser = argparse.ArgumentParser(description="Sybil/Farming Risk Scorer")
    parser.add_argument("--claims", type=str, required=True, help="Input claims JSON file")
    parser.add_argument("--output", type=str, default="risk_report.txt", help="Output report file")
    args = parser.parse_args()
    
    # Load claims
    with open(args.claims) as f:
        claims_data = json.load(f)
    
    claims = [
        Claim(
            issue_number=c["issue"],
            claimant=c["claimant"],
            wallet=c.get("wallet", ""),
            timestamp=c.get("timestamp", datetime.now().isoformat()),
            comment=c.get("comment", ""),
            account_age_days=c.get("account_age_days", 0)
        )
        for c in claims_data
    ]
    
    # Score
    scorer = RiskScorer()
    results = scorer.score_all(claims)
    
    # Report
    scorer.generate_report(results, args.output)
    print(f"Report written to {args.output}")
    print(f"High risk: {len([r for r in results if r['risk_level'] == 'high'])}")


if __name__ == "__main__":
    main()
