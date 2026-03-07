#!/usr/bin/env python3
"""
Command-line interface for bounty verifier.
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List, Optional

from .config import Config, load_config
from .github_client import RateLimitExceeded
from .models import VerificationStatus
from .verifier import BountyVerifier


def setup_logging(level: str) -> None:
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def cmd_verify(
    verifier: BountyVerifier,
    issue_number: int,
    comment_id: Optional[int] = None,
    output_json: bool = False,
) -> int:
    """Verify a specific claim or all claims on an issue."""
    logger = logging.getLogger(__name__)
    
    try:
        if comment_id:
            # Verify specific comment
            if not verifier.github:
                logger.error("GitHub client not configured")
                return 1
            
            comments = verifier.github.get_issue_comments(issue_number)
            claim = next((c for c in comments if c.id == comment_id), None)
            
            if not claim:
                logger.error(f"Comment #{comment_id} not found on issue #{issue_number}")
                return 1
            
            if not verifier.is_claim_comment(claim):
                logger.warning(f"Comment #{comment_id} does not appear to be a claim")
            
            result = verifier.verify_claim(claim, all_comments=comments)
            results = [result]
        else:
            # Verify all claims on issue
            results = verifier.verify_issue_claims(issue_number)
        
        if not results:
            logger.info(f"No claims found on issue #{issue_number}")
            return 0
        
        # Output results
        if output_json:
            output = []
            for r in results:
                output.append({
                    "user": r.claim.user_login,
                    "wallet": r.claim.wallet_address,
                    "status": r.overall_status.value,
                    "payout": r.payout_amount,
                    "coefficient": r.payout_coefficient,
                    "checks": [
                        {
                            "name": c.name,
                            "status": c.status.value,
                            "message": c.message,
                        }
                        for c in r.checks
                    ],
                })
            print(json.dumps(output, indent=2))
        else:
            for result in results:
                status_icon = {
                    VerificationStatus.PASSED: "✅",
                    VerificationStatus.FAILED: "❌",
                    VerificationStatus.ERROR: "⚠️",
                    VerificationStatus.SKIPPED: "⏭️",
                }.get(result.overall_status, "❓")
                
                print(f"\n{status_icon} Claim by @{result.claim.user_login}")
                print(f"   Wallet: {result.claim.wallet_address or 'N/A'}")
                print(f"   Status: {result.overall_status.value.upper()}")
                
                if result.payout_amount > 0:
                    print(f"   Payout: {result.payout_amount:.2f} WRTC (coef: {result.payout_coefficient:.2f})")
                
                for check in result.checks:
                    icon = {
                        VerificationStatus.PASSED: "✓",
                        VerificationStatus.FAILED: "✗",
                        VerificationStatus.ERROR: "!",
                        VerificationStatus.SKIPPED: "-",
                    }.get(check.status, "?")
                    print(f"   [{icon}] {check.name}: {check.message}")
        
        # Post comments if enabled
        if verifier.config.post_comments and not verifier.config.dry_run:
            for result in results:
                try:
                    url = verifier.post_verification_comment(issue_number, result)
                    if url:
                        logger.info(f"Posted verification comment: {url}")
                except Exception as e:
                    logger.error(f"Failed to post comment: {e}")
        
        # Return non-zero if any claims failed
        failed = [r for r in results if r.overall_status == VerificationStatus.FAILED]
        return 1 if failed else 0
        
    except RateLimitExceeded as e:
        logger.error(f"Rate limit exceeded: {e}")
        return 2
    except Exception as e:
        logger.exception(f"Verification failed: {e}")
        return 1


def cmd_check_rate_limit(verifier: BountyVerifier) -> int:
    """Check GitHub API rate limit status."""
    if not verifier.github:
        print("GitHub client not configured")
        return 1
    
    status = verifier.github.get_rate_limit_status()
    
    core = status.get("resources", {}).get("core", {})
    graphql = status.get("resources", {}).get("graphql", {})
    
    print("GitHub API Rate Limit Status:")
    print(f"  Core API: {core.get('remaining', 'N/A')}/{core.get('limit', 'N/A')}")
    print(f"  GraphQL: {graphql.get('remaining', 'N/A')}/{graphql.get('limit', 'N/A')}")
    
    return 0


def cmd_parse_comment(verifier: BountyVerifier, text: str) -> int:
    """Parse a claim comment and extract data."""
    from .models import ClaimComment
    from datetime import datetime
    
    # Create a mock comment
    comment = ClaimComment(
        id=0,
        user_login="test_user",
        user_id=12345,
        body=text,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        issue_number=0,
        html_url="https://github.com/test",
    )
    
    parsed = verifier.parse_claim_comment(comment)
    
    print("Parsed Claim Data:")
    print(f"  Wallet: {parsed.wallet_address or 'N/A'}")
    print(f"  Follow Proof URL: {parsed.follow_proof_url or 'N/A'}")
    print(f"  Star Proof URL: {parsed.star_proof_url or 'N/A'}")
    print(f"  Additional URLs: {parsed.additional_urls or '[]'}")
    print(f"  Is Claim: {verifier.is_claim_comment(comment)}")
    
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="bounty-verifier",
        description="RustChain Bounty Claim Verification Bot",
    )
    
    parser.add_argument(
        "-c", "--config",
        type=Path,
        help="Path to configuration file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without posting comments or making changes",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Verify bounty claims")
    verify_parser.add_argument(
        "issue_number",
        type=int,
        help="GitHub issue number",
    )
    verify_parser.add_argument(
        "--comment-id",
        type=int,
        help="Specific comment ID to verify",
    )
    verify_parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Output results as JSON",
    )
    
    # Rate limit command
    subparsers.add_parser("rate-limit", help="Check GitHub API rate limit")
    
    # Parse command
    parse_parser = subparsers.add_parser("parse", help="Parse a claim comment")
    parse_parser.add_argument(
        "text",
        nargs="+",
        help="Comment text to parse",
    )
    
    args = parser.parse_args(argv)
    
    # Setup logging
    if args.verbose:
        args.log_level = "DEBUG"
    setup_logging(args.log_level)
    
    # Load configuration
    config = load_config(str(args.config) if args.config else None)
    
    # Override with CLI flags
    if args.dry_run:
        config.dry_run = True
    
    # Create verifier
    verifier = BountyVerifier(config)
    
    # Execute command
    if args.command == "verify":
        return cmd_verify(verifier, args.issue_number, args.comment_id, args.output_json)
    elif args.command == "rate-limit":
        return cmd_check_rate_limit(verifier)
    elif args.command == "parse":
        return cmd_parse_comment(verifier, " ".join(args.text))
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
