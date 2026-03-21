# SPDX-License-Identifier: MIT

"""
CLI interface for the bounty verifier tool.
"""

import argparse
import logging
import os
import sys

from .core import BountyVerifier
from .config import VerifierConfig


def setup_logging(level):
    """Set up logging configuration."""
    log_level = getattr(logging, level.upper())
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def cmd_verify(args):
    """Handle verify command."""
    config = VerifierConfig.from_env()
    verifier = BountyVerifier(config)

    try:
        result = verifier.verify_claim(
            issue_number=args.issue_number,
            comment_id=args.comment_id
        )

        if result['success']:
            print(f"Verification completed: {result['message']}")
            return 0
        else:
            print(f"Verification failed: {result['message']}", file=sys.stderr)
            return 1

    except Exception as e:
        print(f"Error during verification: {e}", file=sys.stderr)
        return 1


def cmd_check_config(args):
    """Handle check-config command."""
    try:
        config = VerifierConfig.from_env()
        print("Configuration loaded successfully:")
        print(f"  GitHub Owner: {config.github_owner}")
        print(f"  GitHub Repo: {config.github_repo}")
        print(f"  Node URL: {config.node_url}")
        print(f"  Dry Run: {config.dry_run}")
        print(f"  GitHub Token: {'✓' if config.github_token else '✗'}")
        return 0
    except Exception as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Bounty verification bot for GitHub issues'
    )

    parser.add_argument(
        '--log-level',
        default=os.getenv('LOG_LEVEL', 'INFO'),
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Set logging level'
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Verify command
    verify_parser = subparsers.add_parser('verify', help='Verify bounty claims')
    verify_parser.add_argument(
        'issue_number',
        type=int,
        help='GitHub issue number to process'
    )
    verify_parser.add_argument(
        '--comment-id',
        type=int,
        help='Specific comment ID to verify (optional)'
    )

    # Check config command
    config_parser = subparsers.add_parser('check-config', help='Check configuration')

    args = parser.parse_args()

    setup_logging(args.log_level)

    if args.command == 'verify':
        return cmd_verify(args)
    elif args.command == 'check-config':
        return cmd_check_config(args)
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
