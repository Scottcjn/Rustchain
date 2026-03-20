# SPDX-License-Identifier: MIT

import argparse
import logging
import os
import sys
from typing import Optional

from .core import BountyVerifier


def setup_logging(level: str = "INFO") -> None:
    """Configure logging for the CLI."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def get_env_config() -> dict:
    """Load configuration from environment variables."""
    return {
        "github_token": os.getenv("GITHUB_TOKEN"),
        "github_owner": os.getenv("GITHUB_OWNER", "Scottcjn"),
        "github_repo": os.getenv("GITHUB_REPO", "Rustchain"),
        "rustchain_node_url": os.getenv("RUSTCHAIN_NODE_URL", "http://localhost:3030"),
        "dry_run": os.getenv("DRY_RUN", "false").lower() == "true",
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
    }


def create_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Bounty Verification Bot - Auto-verify GitHub bounty claims",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m bounty_verifier.cli verify 123
  python -m bounty_verifier.cli verify 123 --comment-id 456789
  python -m bounty_verifier.cli verify 123 --dry-run
  python -m bounty_verifier.cli status --issue 123
        """.strip()
    )

    parser.add_argument(
        "--token",
        help="GitHub API token (or set GITHUB_TOKEN env var)"
    )
    parser.add_argument(
        "--owner",
        default="Scottcjn",
        help="GitHub repository owner (default: %(default)s)"
    )
    parser.add_argument(
        "--repo",
        default="Rustchain",
        help="GitHub repository name (default: %(default)s)"
    )
    parser.add_argument(
        "--node-url",
        default="http://localhost:3030",
        help="RustChain node URL (default: %(default)s)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform verification without posting comments"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: %(default)s)"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    verify_parser = subparsers.add_parser(
        "verify",
        help="Verify bounty claims in an issue"
    )
    verify_parser.add_argument(
        "issue_number",
        type=int,
        help="GitHub issue number to verify"
    )
    verify_parser.add_argument(
        "--comment-id",
        type=int,
        help="Specific comment ID to verify (optional)"
    )

    status_parser = subparsers.add_parser(
        "status",
        help="Show bounty verification status"
    )
    status_parser.add_argument(
        "--issue",
        type=int,
        help="Issue number to check status for"
    )

    return parser


def verify_command(verifier: BountyVerifier, issue_number: int, comment_id: Optional[int] = None) -> int:
    """Execute the verify command."""
    try:
        if comment_id:
            result = verifier.verify_comment(issue_number, comment_id)
            if result:
                logging.info(f"Successfully verified comment {comment_id} on issue {issue_number}")
                return 0
            else:
                logging.warning(f"Verification failed for comment {comment_id} on issue {issue_number}")
                return 1
        else:
            results = verifier.verify_issue(issue_number)
            verified_count = sum(1 for r in results if r.get("success", False))
            total_count = len(results)

            logging.info(f"Verified {verified_count}/{total_count} claims in issue {issue_number}")
            return 0 if verified_count > 0 or total_count == 0 else 1

    except Exception as e:
        logging.error(f"Verification failed: {e}")
        return 1


def status_command(verifier: BountyVerifier, issue_number: Optional[int] = None) -> int:
    """Execute the status command."""
    try:
        if issue_number:
            status = verifier.get_verification_status(issue_number)
            print(f"Issue #{issue_number} verification status:")
            print(f"  Total comments: {status.get('total_comments', 0)}")
            print(f"  Verified claims: {status.get('verified_claims', 0)}")
            print(f"  Failed verifications: {status.get('failed_verifications', 0)}")
            print(f"  Last updated: {status.get('last_updated', 'Never')}")
        else:
            stats = verifier.get_overall_stats()
            print("Overall bounty verification statistics:")
            print(f"  Total issues processed: {stats.get('issues_processed', 0)}")
            print(f"  Total claims verified: {stats.get('claims_verified', 0)}")
            print(f"  Success rate: {stats.get('success_rate', 0):.1%}")

        return 0
    except Exception as e:
        logging.error(f"Status check failed: {e}")
        return 1


def main() -> int:
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    env_config = get_env_config()

    # Override env config with CLI args where provided
    config = {
        "github_token": args.token or env_config["github_token"],
        "github_owner": args.owner or env_config["github_owner"],
        "github_repo": args.repo or env_config["github_repo"],
        "rustchain_node_url": args.node_url or env_config["rustchain_node_url"],
        "dry_run": args.dry_run or env_config["dry_run"],
        "log_level": args.log_level or env_config["log_level"],
    }

    # Validate required configuration
    if not config["github_token"]:
        logging.error("GitHub token is required. Set GITHUB_TOKEN env var or use --token")
        return 1

    setup_logging(config["log_level"])

    verifier = BountyVerifier(
        github_token=config["github_token"],
        github_owner=config["github_owner"],
        github_repo=config["github_repo"],
        rustchain_node_url=config["rustchain_node_url"],
        dry_run=config["dry_run"]
    )

    if args.command == "verify":
        return verify_command(
            verifier=verifier,
            issue_number=args.issue_number,
            comment_id=getattr(args, "comment_id", None)
        )
    elif args.command == "status":
        return status_command(
            verifier=verifier,
            issue_number=getattr(args, "issue", None)
        )
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
